import base64
from pathlib import Path

from extensions import db
from models import HumanReview, User
from tests.test_support import AQITestCase


ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Y9l9O8AAAAASUVORK5CYII="
)


class BlackBoxTests(AQITestCase):
    def test_dashboard_requires_authentication(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_admin_can_create_user(self):
        admin = self.create_user("admin@example.com", "System Administrator")
        self.login_as(admin)

        response = self.client.post(
            "/create_user",
            data={"email": "operator@example.com", "role": "Quality Operator"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            created = User.query.filter_by(username="operator@example.com").first()
            self.assertIsNotNone(created)
            self.assertEqual(created.role, "Quality Operator")

    def test_non_admin_cannot_create_user(self):
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.login_as(operator)

        response = self.client.post(
            "/create_user",
            data={"email": "newuser@example.com", "role": "Quality Operator"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            created = User.query.filter_by(username="newuser@example.com").first()
            self.assertIsNone(created)

    def test_admin_dashboard_shows_system_overview(self):
        admin = self.create_user("admin@example.com", "System Administrator")
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.create_user("engineer@example.com", "Manufacturing Engineer")
        self.create_inspection_run(operator.id)
        self.create_review(predicted_label="GOOD", reviewed=False)
        self.create_review(
            predicted_label="DEFECTIVE",
            reviewed=True,
            is_correct=True,
            human_label="DEFECTIVE",
        )
        self.login_as(admin)

        response = self.client.get("/dashboard")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin System Overview", body)
        self.assertIn("Recent Inspection Activity", body)
        self.assertIn("Role Breakdown", body)
        self.assertIn("Review Queue", body)
        self.assertIn("Change Role", body)
        self.assertIn("operator@example.com", body)

    def test_engineer_dashboard_shows_model_lifecycle_workspace(self):
        engineer = self.create_user("engineer@example.com", "Manufacturing Engineer")
        job = self.create_training_job(engineer.id, item_name="bottle")
        model_path = Path(self.temp_root) / "model_outputs" / "model_registry" / "bottle" / "v1" / "model.pt"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_text("model", encoding="utf-8")
        self.create_model_version(
            item_name="bottle",
            version_number=1,
            model_path=str(model_path),
            active=True,
            training_job_id=job.id,
        )
        self.login_as(engineer)

        response = self.client.get("/dashboard")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Model Lifecycle Workspace", body)
        self.assertIn("Dataset Validation", body)
        self.assertIn("Feedback Retraining Queue", body)
        self.assertIn("Model Registry", body)
        self.assertIn("Training Job History", body)

    def test_engineer_can_validate_dataset_from_server_path(self):
        engineer = self.create_user("engineer@example.com", "Manufacturing Engineer")
        dataset_root = Path(self.temp_root) / "dataset_to_validate"
        item_root = dataset_root / "bottle"
        (item_root / "train" / "good").mkdir(parents=True, exist_ok=True)
        (item_root / "train" / "good" / "000.png").write_bytes(b"fake")
        test_dir = item_root / "test" / "contamination"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "001.png").write_bytes(b"fake")
        mask_dir = item_root / "ground_truth" / "contamination"
        mask_dir.mkdir(parents=True, exist_ok=True)
        (mask_dir / "001_mask.png").write_bytes(b"fake")
        self.login_as(engineer)

        response = self.client.post(
            "/validate_dataset",
            data={"item_name": "bottle", "dataset_path": str(dataset_root)},
        )
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Valid dataset", body)
        self.assertIn("Train good images", body)
        self.assertIn("contamination: 1", body)

    def test_admin_can_update_user_role(self):
        admin = self.create_user("admin@example.com", "System Administrator")
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.login_as(admin)

        response = self.client.post(
            f"/update_user_role/{operator.id}",
            data={"role": "Manufacturing Engineer"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            updated = db.session.get(User, operator.id)
            self.assertEqual(updated.role, "Manufacturing Engineer")

    def test_admin_can_revoke_and_restore_user_access(self):
        admin = self.create_user("admin@example.com", "System Administrator")
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.login_as(admin)

        revoke_response = self.client.post(f"/revoke_user/{operator.id}")
        self.assertEqual(revoke_response.status_code, 302)
        with self.app.app_context():
            revoked = db.session.get(User, operator.id)
            self.assertTrue(revoked.access_revoked)

        restore_response = self.client.post(f"/restore_user/{operator.id}")
        self.assertEqual(restore_response.status_code, 302)
        with self.app.app_context():
            restored = db.session.get(User, operator.id)
            self.assertFalse(restored.access_revoked)

    def test_non_admin_cannot_revoke_user_access(self):
        operator = self.create_user("operator@example.com", "Quality Operator")
        engineer = self.create_user("engineer@example.com", "Manufacturing Engineer")
        self.login_as(operator)

        response = self.client.post(f"/revoke_user/{engineer.id}")

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            unchanged = db.session.get(User, engineer.id)
            self.assertFalse(unchanged.access_revoked)

    def test_admin_cannot_revoke_self(self):
        admin = self.create_user("admin@example.com", "System Administrator")
        self.login_as(admin)

        response = self.client.post(f"/revoke_user/{admin.id}")

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            unchanged = db.session.get(User, admin.id)
            self.assertFalse(unchanged.access_revoked)

    def test_non_admin_cannot_update_user_role(self):
        operator = self.create_user("operator@example.com", "Quality Operator")
        engineer = self.create_user("engineer@example.com", "Manufacturing Engineer")
        self.login_as(operator)

        response = self.client.post(
            f"/update_user_role/{engineer.id}",
            data={"role": "System Administrator"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            unchanged = db.session.get(User, engineer.id)
            self.assertEqual(unchanged.role, "Manufacturing Engineer")

    def test_admin_cannot_demote_last_admin(self):
        admin = self.create_user("admin@example.com", "System Administrator")
        self.login_as(admin)

        response = self.client.post(
            f"/update_user_role/{admin.id}",
            data={"role": "Quality Operator"},
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            unchanged = db.session.get(User, admin.id)
            self.assertEqual(unchanged.role, "System Administrator")

    def test_operator_run_inspection_without_model_is_rejected(self):
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.login_as(operator)

        response = self.client.post(
            "/run_inspection",
            data={"item_name": "bottle", "test_folder": "missing/test/path"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

        with self.client.session_transaction() as session:
            flashes = session.get("_flashes", [])
        self.assertTrue(any("Model not found" in message for _, message in flashes))

    def test_history_detail_is_visible_only_to_owning_operator(self):
        owner = self.create_user("owner@example.com", "Quality Operator")
        other = self.create_user("other@example.com", "Quality Operator")
        run = self.create_inspection_run(owner.id)
        self.create_inspection_result(run.id, img_name="000.png")
        self.create_review(predicted_label="GOOD", reviewed=True, is_correct=True, human_label="GOOD")

        self.login_as(owner)
        allowed = self.client.get(f"/history/{run.id}")
        self.assertEqual(allowed.status_code, 200)

        self.login_as(other)
        denied = self.client.get(f"/history/{run.id}")
        self.assertEqual(denied.status_code, 403)

    def test_false_negative_review_redirects_to_mask_drawing(self):
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.login_as(operator)
        review = self.create_review(predicted_label="GOOD")

        response = self.client.post(
            f"/submit_review/{review.id}",
            data={"is_correct": "no", "correct_label": "DEFECTIVE"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/draw_mask/{review.id}", response.headers["Location"])

    def test_submit_mask_saves_file_and_marks_reviewed(self):
        operator = self.create_user("operator@example.com", "Quality Operator")
        self.login_as(operator)
        review = self.create_review(
            predicted_label="GOOD",
            reviewed=False,
            is_correct=False,
            human_label="DEFECTIVE",
        )

        response = self.client.post(
            f"/submit_mask/{review.id}",
            data={"mask_data": f"data:image/png;base64,{ONE_PIXEL_PNG}"},
        )

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            refreshed = db.session.get(HumanReview, review.id)
            self.assertTrue(refreshed.reviewed)
            self.assertEqual(refreshed.mask_path, f"masks/mask_{review.id}.png")

        saved_mask = Path(self.temp_root) / "static" / "masks" / f"mask_{review.id}.png"
        self.assertTrue(saved_mask.exists())
