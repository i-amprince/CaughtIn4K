# CaughtIn4K Project Memory Prompt

Use the following prompt when you want another AI/chat to quickly understand this project before answering questions, writing reports, adding features, or explaining code.

```text
You are helping me with my software engineering project called "CaughtIn4K".

Project identity:
- Project name: CaughtIn4K
- Domain: Automated Quality Inspection (AQI) for manufacturing
- Goal: inspect product images, detect anomalies/defects, highlight suspicious regions, let humans review/correct results, and improve the system over time
- Main idea: the system learns what normal products look like and flags deviations as defects

What the project is about:
- This is an industrial quality inspection web application
- It automates visual inspection of manufactured items using computer vision and anomaly detection
- It supports explainability through heatmaps
- It supports human-in-the-loop review so operators can confirm or correct predictions
- It supports threshold-based retraining / continual learning using accumulated human corrections

Actual implementation summary:
- Language: Python
- Web framework: Flask
- Authentication/session: Flask-Login
- Database: SQLite through Flask-SQLAlchemy
- ML/anomaly detection: anomalib PatchCore pipeline with Torch export/inference
- Vision/image processing: OpenCV
- Model inference wrapper: TorchInferencer from anomalib.deploy
- Frontend: Flask templates + static CSS/JS
- Environment: currently developed on Windows

Important note about documentation vs code:
- Some older documentation/README sections mention TensorFlow/Keras or Grad-CAM generically
- The current codebase actually uses anomalib + PatchCore + Torch model export/inference
- When answering questions, prefer the current code implementation over older generic descriptions

Core user roles:
- System Administrator
  - can authorize/create users and assign roles
  - can view system-wide admin overview metrics
  - can change user roles
  - can revoke and restore user access without deleting historical records
- Manufacturing Engineer
  - can start training for an item/model
- Quality Operator
  - can run inspection, review results, submit corrections, draw defect masks, and view own inspection history

Main system workflow:
1. User logs in
2. Manufacturing Engineer trains an anomaly model for a product/item using an MVTec-style dataset
3. Quality Operator starts inspection on a test folder
4. The system runs batch anomaly inference on images
5. Each image gets:
   - predicted label: GOOD or DEFECTIVE
   - anomaly/confidence score
   - saved heatmap/superimposed output
6. Results are stored in the database
7. HumanReview entries are also stored for later validation
8. Operator opens review page and marks predictions as correct or incorrect
9. If model predicted GOOD but human says DEFECTIVE, the operator draws a defect mask
10. After enough false classifications are collected, background retraining starts

Architecture style:
- Layered architecture
- Presentation layer:
  - Flask templates and static frontend files
- Application layer:
  - Flask routes/blueprints coordinating flows
- Business logic layer:
  - inference, validation, review logic, retraining logic
- Data layer:
  - SQLite database, saved heatmaps, saved masks, dataset folders, model output folders

Key Flask files and responsibilities:
- app.py
  - creates Flask app
  - loads environment variables from .env
  - configures database and paths
  - registers blueprints
- extensions.py
  - initializes SQLAlchemy and Flask-Login
- models.py
  - defines User, InspectionRun, InspectionImageResult, HumanReview
- bootstrap.py
  - creates initial DB tables and bootstrap admin users
  - performs small schema compatibility checks for local SQLite columns such as User.access_revoked
- auth_helpers.py
  - email normalization/validation and Google-user creation/update helpers

Main route modules:
- routes/auth.py
  - login flow
  - Google OAuth support
  - blocks login for revoked accounts
  - logout
- routes/admin.py
  - create/authorize users with roles
  - update user roles
  - revoke and restore user access
- routes/dashboard.py
  - main dashboard
  - admin system overview
  - recent inspection activity for administrators
  - recent history for operators
  - history detail page with review mapping
- routes/ml.py
  - start_training
  - training_status
  - run_inspection
  - inspection_status
  - background-thread execution for long ML tasks
- routes/review.py
  - review page
  - submit review
  - draw mask page
  - submit mask
  - retrain status
  - threshold-based batch retraining trigger

Database model details:
- User
  - id
  - username
  - password
  - role
  - access_revoked

- InspectionRun
  - one row per inspection batch/run
  - stores item_name, test_folder, total_images, defective_count, good_count, avg_latency, fps, total_time_sec, created_at, operator_id

- InspectionImageResult
  - one row per inspected image
  - stores inspection_run_id, img_name, defect_category, score, status, heatmap_url

- HumanReview
  - one row per image available for human review
  - stores img_path, img_name, inspection_run_id, predicted_label, confidence, item_name, human_label, is_correct, reviewed, mask_path, retrained

How data is stored:
- SQLite DB URI in app.py:
  - sqlite:///users.db
- Saved inspection result images / heatmaps:
  - static/results/
- Saved operator-drawn masks:
  - static/masks/
- Dataset root:
  - configured by DATASET_ROOT env var
  - expected to follow MVTec-style structure
- Trained model outputs:
  - MODEL_OUTPUT_DIR under local app data
  - fallback LEGACY_MODEL_OUTPUT_DIR inside project

Relevant config values in app.py:
- SECRET_KEY
- SQLALCHEMY_DATABASE_URI
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- GOOGLE_OAUTH_REDIRECT_URI
- GOOGLE_OAUTH_BOOTSTRAP_ADMIN_EMAILS
- MODEL_OUTPUT_DIR
- LEGACY_MODEL_OUTPUT_DIR
- DATASET_ROOT

Expected dataset format:
- MVTec-like directory structure per item/category
- Example:
  - dataset_root/
    - bottle/
      - train/good/
      - test/good/
      - test/<defect_type>/
      - ground_truth/<defect_type>/
- training.py validates:
  - dataset root exists
  - item folder exists
  - train/good exists
  - test exists
  - each abnormal defect folder has corresponding ground-truth masks

How training works:
- Implemented mainly in training.py
- Uses PatchCore from anomalib.models
- Uses MVTec datamodule from anomalib.data
- Trains on normal/good products
- Exports Torch model to:
  - <MODEL_OUTPUT_DIR>/<item_name>/weights/torch/model.pt
- Training is started by POST /start_training
- It runs in a background thread
- Progress is checked by /training_status

How inspection/inference works:
- Implemented mainly in run_model.py and routes/ml.py
- Quality Operator submits item_name and test_folder
- routes/ml.py resolves the model path for that item
- run_model.py loads the TorchInferencer
- It scans image files under test_folder/*/*.png
- For each image it:
  - predicts anomaly map, mask, score, label
  - builds a heatmap
  - overlays it on the original image
  - saves the output inside static/results
  - creates a HumanReview row
  - accumulates per-image results
- After batch completion it creates:
  - one InspectionRun
  - many InspectionImageResult rows
- Inspection is started by POST /run_inspection
- It runs in a background thread
- Progress is checked by /inspection_status

Human review workflow:
- Review page shows unreviewed and recently reviewed items grouped by inspection run
- Legacy review rows without inspection_run_id are shown under an unlinked reviews section
- If operator marks prediction as correct:
  - is_correct = True
  - human_label = predicted_label
  - reviewed = True
- If operator marks prediction as incorrect:
  - is_correct = False
  - human_label = corrected label
- Current supported review labels are GOOD and DEFECTIVE
- If the model predicted GOOD but the product is actually defective:
  - the operator enters DEFECTIVE and submits Incorrect
  - the app redirects to the mask drawing page
- If the model predicted DEFECTIVE but the product is actually good:
  - the operator enters GOOD and submits Incorrect
  - no mask is required
- Special false-negative flow:
  - if model predicted GOOD but human says DEFECTIVE
  - operator is redirected to draw_mask page
  - mask PNG is submitted as base64 data
  - mask file is saved under static/masks/
  - review is marked reviewed

Retraining logic:
- RETRAIN_THRESHOLD in routes/review.py is 10
- The system counts reviewed=false? No: it counts reviewed=True, is_correct=False, retrained=False
- If false classifications are below threshold:
  - correction is saved and system waits for more
- If threshold is reached:
  - pending items are marked retrained=True
  - a background retrain thread starts
- Batch retraining uses retrain.py
- For false positives:
  - corrected image is added to train/good
- For false negatives:
  - corrected image is added to test/correction_defects
  - operator mask is used if available, otherwise fallback all-ones mask is created
- Then model retraining runs once per unique item_name in the batch

Access control/business rules:
- /dashboard requires login
- Only System Administrator can create users
- Only System Administrator can update roles
- Only System Administrator can revoke or restore account access
- Revoked accounts cannot sign in through Google OAuth
- The app prevents revoking the current admin's own account
- The app prevents removing the last active System Administrator
- Only Manufacturing Engineer can start training
- Only Quality Operator can run inspection
- Only Quality Operator can view their own inspection history details
- Review pages/actions require login

Admin dashboard features:
- Shows active user count, inspection run count, image count, pending review count, and review accuracy
- Shows role breakdown and revoked account count
- Shows review queue metrics such as reviewed items, incorrect reviews, corrections awaiting retrain, and legacy unlinked reviews
- Shows recent inspection activity across operators
- Allows administrators to change a user's role
- Allows administrators to revoke or restore account access

Main folders in the repo:
- app.py
- models.py
- auth_helpers.py
- training.py
- run_model.py
- retrain.py
- routes/
- templates/
- static/
- mvtec_anomaly_detection/
- SRS/
- documentation/
- tests/

Important templates:
- templates/login.html
- templates/dashboard.html
- templates/review.html
- templates/draw_mask.html
- templates/history_detail.html

Important static files:
- static/js/dashboard.js
- static/js/login.js
- static/css/dashboard.css
- static/css/login.css

SRS / academic intent:
- The SRS describes the system as an Automated Quality Inspection system using self-supervised anomaly detection, explainable AI, human-in-the-loop feedback, and continual learning
- Functional requirements include:
  - accept product images
  - preprocess images
  - perform anomaly detection
  - localize defects
  - generate visual explanations
  - provide confidence scores
  - store feedback and inspection history
  - classify items as defective or non-defective
- Non-functional requirement example:
  - target inspection time <= 2 seconds per image

Current automated testing added to the repo:
- White-box and black-box tests were added
- Test files:
  - tests/test_support.py
  - tests/test_white_box.py
  - tests/test_black_box.py
- Test case document:
  - documentation/testing/aqi_test_cases.md
- Current local result:
  - 23 tests passed, 0 failed
- Test command:
  - python -m unittest discover -s tests -v

White-box test coverage currently includes:
- email normalization and validation
- verified Google email logic
- revoked Google account login denial
- model path resolution
- item-name inference from saved filenames
- MVTec dataset validation
- retrain-threshold branch behavior

Black-box test coverage currently includes:
- dashboard access requiring login
- admin user creation
- non-admin restriction for user creation
- admin dashboard overview rendering
- admin role changes
- user access revoke and restore
- protection against non-admin revocation
- protection against self-revocation / removing last active admin
- inspection request without trained model
- operator-only history visibility
- false-negative review redirect to mask drawing
- mask submission and review completion

Known implementation details / caveats:
- Current code uses background threads for training, inspection, and retraining
- Shared job state in routes/ml.py is stored in module-level dictionaries protected by locks
- Google OAuth exists in code, but it depends on environment configuration
- Some code still uses legacy Query.get() and datetime.utcnow() patterns, which currently produce warnings but do not stop the app
- There may be older docs describing the concept at a higher level than the actual implementation

When answering my future questions about this project:
- assume I want answers tailored to this exact repository, not generic AQI advice
- prefer the real Python/Flask/anomalib implementation over abstract textbook explanations
- if I ask about reports, viva, documentation, SRS, testing, design, or code changes, answer in the context of this project
- if I ask for features, mention which files/routes/models/templates would likely change
- if I ask for data flow, explain both DB storage and file-system storage
- if I ask for testing, separate white-box and black-box perspectives
- if I ask for architecture, describe it as layered Flask web app + ML workflow + persistent storage

If needed, you can summarize the project in one line as:
"CaughtIn4K is a Flask-based automated quality inspection system that uses anomaly detection to inspect manufacturing images, explain defects with heatmaps, collect human corrections, and retrain itself over time."
```

Quick use:
- Paste the big block above into any new chat first
- Then ask things like:
  - "Explain my project architecture"
  - "Write viva questions and answers for this project"
  - "Suggest new features for my current codebase"
  - "Write white-box and black-box test cases for my project"
  - "Explain how retraining works in my project"
  - "Which files change if I add role-based analytics?"
