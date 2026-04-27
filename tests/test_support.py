import shutil
import tempfile
import unittest
from pathlib import Path

from flask import Flask
from sqlalchemy import inspect as sqlalchemy_inspect

from extensions import db, login_manager
from models import HumanReview, InspectionImageResult, InspectionRun, ModelVersion, TrainingJob, User
from routes import register_blueprints

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_TEMP_ROOT = REPO_ROOT / ".tmp_test_runs"


def create_test_app(temp_root: str) -> Flask:
    app = Flask(
        "caughtin4k_test_app",
        root_path=temp_root,
        template_folder=str(REPO_ROOT / "templates"),
        static_folder=str(REPO_ROOT / "static"),
    )
    app.config.update(
        SECRET_KEY="test-secret",
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        GOOGLE_CLIENT_ID="",
        GOOGLE_CLIENT_SECRET="",
        GOOGLE_OAUTH_REDIRECT_URI="http://localhost/auth/google/callback",
        GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS=[],
        MODEL_OUTPUT_DIR=str(Path(temp_root) / "model_outputs"),
        LEGACY_MODEL_OUTPUT_DIR=str(Path(temp_root) / "legacy_model_outputs"),
        USER_UPLOAD_ROOT=str(Path(temp_root) / "uploaded_folders"),
        DATASET_ROOT=str(Path(temp_root) / "dataset_root"),
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    register_blueprints(app)
    return app


class AQITestCase(unittest.TestCase):
    def setUp(self):
        TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp_root = str(TEST_TEMP_ROOT / f"{self.__class__.__name__}_{self._testMethodName}")
        shutil.rmtree(self.temp_root, ignore_errors=True)
        Path(self.temp_root).mkdir(parents=True, exist_ok=True)
        Path(self.temp_root, "model_outputs").mkdir(parents=True, exist_ok=True)
        Path(self.temp_root, "legacy_model_outputs").mkdir(parents=True, exist_ok=True)
        Path(self.temp_root, "uploaded_folders").mkdir(parents=True, exist_ok=True)
        Path(self.temp_root, "dataset_root").mkdir(parents=True, exist_ok=True)
        Path(self.temp_root, "static", "results").mkdir(parents=True, exist_ok=True)
        Path(self.temp_root, "static", "masks").mkdir(parents=True, exist_ok=True)
        self.app = create_test_app(self.temp_root)
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def create_user(self, username: str, role: str) -> User:
        with self.app.app_context():
            user = User(username=username, password="pw", role=role)
            db.session.add(user)
            db.session.commit()
            _ = user.id
            db.session.expunge(user)
            return user

    def login_as(self, user: User) -> None:
        identity = sqlalchemy_inspect(user).identity
        user_id = identity[0] if identity else user
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def create_inspection_run(self, operator_id: int, item_name: str = "bottle") -> InspectionRun:
        with self.app.app_context():
            run = InspectionRun(
                item_name=item_name,
                test_folder="sample/test/folder",
                total_images=2,
                defective_count=1,
                good_count=1,
                avg_latency=120.5,
                fps=8.3,
                total_time_sec=0.24,
                operator_id=operator_id,
            )
            db.session.add(run)
            db.session.commit()
            _ = run.id
            db.session.expunge(run)
            return run

    def create_inspection_result(self, run_id: int, img_name: str = "000.png") -> InspectionImageResult:
        with self.app.app_context():
            result = InspectionImageResult(
                inspection_run_id=run_id,
                img_name=img_name,
                defect_category="good",
                score=0.12,
                status="GOOD",
                heatmap_url="results/good_000.png",
            )
            db.session.add(result)
            db.session.commit()
            _ = result.id
            db.session.expunge(result)
            return result

    def create_review(
        self,
        predicted_label: str = "GOOD",
        reviewed: bool = False,
        is_correct=None,
        retrained: bool = False,
        human_label=None,
        item_name: str = "bottle",
    ) -> HumanReview:
        with self.app.app_context():
            review = HumanReview(
                img_path="results/sample.png",
                img_name="sample.png",
                predicted_label=predicted_label,
                confidence=0.87,
                item_name=item_name,
                human_label=human_label,
                is_correct=is_correct,
                reviewed=reviewed,
                retrained=retrained,
            )
            db.session.add(review)
            db.session.commit()
            _ = review.id
            db.session.expunge(review)
            return review

    def create_training_job(
        self,
        user_id: int | None,
        item_name: str = "bottle",
        status: str = "completed",
        model_path: str = "model.pt",
    ) -> TrainingJob:
        with self.app.app_context():
            job = TrainingJob(
                item_name=item_name,
                dataset_path="sample/dataset",
                source_mode="upload",
                status=status,
                requested_by_id=user_id,
                model_path=model_path,
                message="Training completed.",
            )
            db.session.add(job)
            db.session.commit()
            _ = job.id
            db.session.expunge(job)
            return job

    def create_model_version(
        self,
        item_name: str = "bottle",
        version_number: int = 1,
        model_path: str = "model.pt",
        active: bool = True,
        training_job_id: int | None = None,
    ) -> ModelVersion:
        with self.app.app_context():
            version = ModelVersion(
                item_name=item_name,
                version_number=version_number,
                model_path=model_path,
                active=active,
                training_job_id=training_job_id,
            )
            db.session.add(version)
            db.session.commit()
            _ = version.id
            db.session.expunge(version)
            return version
