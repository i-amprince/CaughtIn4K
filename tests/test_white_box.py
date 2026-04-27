from pathlib import Path
from unittest.mock import patch

from auth_helpers import is_valid_email, normalize_email
from routes import ml as ml_routes
from routes import review as review_routes
from routes.auth import _is_verified_google_email
from training import _validate_mvtec_item_structure

from extensions import db
from models import HumanReview, User
from tests.test_support import AQITestCase


class WhiteBoxTests(AQITestCase):
    def test_normalize_email_and_validation_branches(self):
        self.assertEqual(normalize_email("  USER@Example.COM "), "user@example.com")
        self.assertTrue(is_valid_email("user@example.com"))
        self.assertFalse(is_valid_email("not-an-email"))

    def test_google_email_verification_handles_bool_and_string(self):
        self.assertTrue(_is_verified_google_email({"email_verified": True}))
        self.assertTrue(_is_verified_google_email({"email_verified": "true"}))
        self.assertFalse(_is_verified_google_email({"email_verified": "false"}))

    def test_revoked_google_account_is_denied_login(self):
        user = self.create_user("revoked@example.com", "Quality Operator")
        with self.app.app_context():
            revoked = db.session.get(User, user.id)
            revoked.access_revoked = True
            db.session.commit()

        with self.client.session_transaction() as session:
            session["google_oauth_state"] = "state-token"

        with patch("routes.auth._exchange_google_code_for_tokens", return_value={"access_token": "token"}):
            with patch(
                "routes.auth._fetch_google_user_info",
                return_value={"email": "revoked@example.com", "email_verified": True},
            ):
                response = self.client.get("/auth/google/callback?state=state-token&code=code")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        with self.client.session_transaction() as session:
            flashes = session.get("_flashes", [])
        self.assertTrue(any("revoked" in message for _, message in flashes))

    def test_resolve_model_path_prefers_primary_then_legacy(self):
        model_path = Path(self.app.config["MODEL_OUTPUT_DIR"]) / "bottle" / "weights" / "torch"
        model_path.mkdir(parents=True, exist_ok=True)
        (model_path / "model.pt").write_text("primary", encoding="utf-8")

        with self.app.app_context():
            resolved = ml_routes._resolve_model_path("bottle")

        self.assertEqual(resolved, str(model_path / "model.pt"))

    def test_infer_item_name_extracts_prefix_from_result_filename(self):
        self.assertEqual(review_routes._infer_item_name("results/bottle_001.png"), "bottle")
        self.assertEqual(review_routes._infer_item_name("results/contamination_sample.png"), "contamination")

    def test_validate_mvtec_item_structure_accepts_valid_dataset(self):
        dataset_root = Path(self.temp_root) / "valid_dataset"
        dataset_root.mkdir(parents=True, exist_ok=True)
        item_root = dataset_root / "bottle"
        (item_root / "train" / "good").mkdir(parents=True, exist_ok=True)
        defect_dir = item_root / "test" / "contamination"
        defect_dir.mkdir(parents=True, exist_ok=True)
        (defect_dir / "001.png").write_bytes(b"fake")
        mask_dir = item_root / "ground_truth" / "contamination"
        mask_dir.mkdir(parents=True, exist_ok=True)
        (mask_dir / "001_mask.png").write_bytes(b"fake")

        result = _validate_mvtec_item_structure(str(dataset_root), "bottle")

        self.assertEqual(result, item_root)

    def test_validate_mvtec_item_structure_rejects_missing_mask(self):
        dataset_root = Path(self.temp_root) / "invalid_dataset"
        dataset_root.mkdir(parents=True, exist_ok=True)
        item_root = dataset_root / "bottle"
        (item_root / "train" / "good").mkdir(parents=True, exist_ok=True)
        defect_dir = item_root / "test" / "contamination"
        defect_dir.mkdir(parents=True, exist_ok=True)
        (defect_dir / "001.png").write_bytes(b"fake")
        (item_root / "ground_truth" / "contamination").mkdir(parents=True, exist_ok=True)

        with self.assertRaisesRegex(ValueError, "Missing ground truth mask files"):
            _validate_mvtec_item_structure(str(dataset_root), "bottle")

    def test_threshold_check_below_limit_does_not_launch_retrain(self):
        self.create_review(
            predicted_label="GOOD",
            reviewed=True,
            is_correct=False,
            retrained=False,
            human_label="DEFECTIVE",
        )

        with self.app.test_request_context("/review"):
            with patch("routes.review._launch_retrain_thread") as launch_mock:
                review_routes._check_and_trigger_batch_retrain()

        launch_mock.assert_not_called()

    def test_threshold_check_marks_items_and_launches_retrain(self):
        for _ in range(review_routes.RETRAIN_THRESHOLD):
            self.create_review(
                predicted_label="GOOD",
                reviewed=True,
                is_correct=False,
                retrained=False,
                human_label="DEFECTIVE",
            )

        with self.app.test_request_context("/review"):
            with patch("routes.review._launch_retrain_thread") as launch_mock:
                review_routes._check_and_trigger_batch_retrain()

        launch_mock.assert_called_once()

        with self.app.app_context():
            pending = HumanReview.query.filter_by(retrained=False).count()
            self.assertEqual(pending, 0)
