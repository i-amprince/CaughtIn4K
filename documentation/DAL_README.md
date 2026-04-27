# Data Access Layer (DAL) - CaughtIn4K

## 1. What is the Data Access Layer?

The **Data Access Layer (DAL)** is the part of the system responsible for:

- connecting the application to the database,
- defining the database schema through models,
- creating, reading, updating, and deleting persistent data,
- and hiding low-level database operations from the rest of the application.

In simple words:

> The DAL is the layer that stores and retrieves application data.

For this project, the DAL manages persistent information such as:

- users,
- inspection runs,
- image-level inspection results,
- and human review / correction records.

---

## 2. DAL in This Project

According to the layered architecture document, the Data Access / Persistence Layer includes:

- `models.py`
- `extensions.py`
- `bootstrap.py`

That is the **core DAL foundation**.

However, in the current implementation, some database queries and commits are also written directly inside:

- `routes/review.py`
- `routes/ml.py`
- `routes/dashboard.py`
- `routes/auth.py`
- `routes/admin.py`
- `auth_helpers.py`

So the practical explanation for viva is:

> The project has a defined persistence layer based on SQLAlchemy models and DB setup, but some repository-style operations are still implemented inside helper and route files instead of a separate `repository/` or `dao/` package.

This is a valid explanation because it reflects the codebase accurately.

---

## 3. Technologies Used for DAL

The Data Access Layer is implemented using:

- **Flask-SQLAlchemy** for ORM-based database access
- **SQLite** as the configured database backend in development
- **Flask-Login** for user session loading support

The configured database URI is set in:

- `app.py`

Current configuration:

- `SQLALCHEMY_DATABASE_URI = "sqlite:///users.db"`

This means SQLAlchemy maps Python classes to tables inside the SQLite database.

---

## 4. What Is Defined Where

### 4.1 `extensions.py`

This file defines the shared framework-level database objects:

- `db = SQLAlchemy()`
- `login_manager = LoginManager()`

Responsibilities:

- creates the SQLAlchemy database object used across the app,
- creates the Flask-Login manager,
- allows these shared objects to be initialized inside `app.py`.

Why it belongs to DAL:

- every model depends on `db`,
- every database operation uses the SQLAlchemy session from `db.session`.

---

### 4.2 `models.py`

This file defines the **database schema** through ORM models.

It contains four major entities:

#### `User`

Fields:

- `id`
- `username`
- `password`
- `role`
- `access_revoked`

Purpose:

- stores application users,
- supports login and role-based access,
- supports revoking/restoring account access without deleting historical inspection data,
- identifies who is a Quality Operator, Manufacturing Engineer, or System Administrator.

#### `InspectionRun`

Fields include:

- `id`
- `item_name`
- `test_folder`
- `total_images`
- `defective_count`
- `good_count`
- `avg_latency`
- `fps`
- `total_time_sec`
- `created_at`
- `operator_id`

Purpose:

- stores one complete inspection session,
- records summary statistics for that session,
- links the run to the operator who performed it.

Relationship:

- `operator` links each run to a `User`
- `results` links each run to many `InspectionImageResult` rows

#### `InspectionImageResult`

Fields:

- `id`
- `inspection_run_id`
- `img_name`
- `defect_category`
- `score`
- `status`
- `heatmap_url`

Purpose:

- stores per-image results for a given inspection run,
- keeps the model output for each image,
- stores the heatmap path shown in the UI.

#### `HumanReview`

Fields include:

- `id`
- `img_path`
- `img_name`
- `inspection_run_id`
- `predicted_label`
- `confidence`
- `item_name`
- `human_label`
- `is_correct`
- `reviewed`
- `mask_path`
- `retrained`

Purpose:

- stores human validation of model predictions,
- links review items back to the inspection run that generated them,
- tracks whether the operator accepted or corrected the prediction,
- stores a drawn mask for false-negative defect corrections,
- tracks whether the correction has already been used for retraining.

Also defined in `models.py`:

- `load_user(user_id)` for Flask-Login

Why this is part of DAL:

- it defines the structure of stored data,
- it defines relationships between records,
- it is the main mapping between Python objects and database tables.

---

### 4.3 `bootstrap.py`

This file handles initial persistence setup.

Main responsibilities:

- calls `db.create_all()` to create database tables,
- ensures small SQLite schema compatibility updates such as the `User.access_revoked` column,
- creates bootstrap admin users using `sync_bootstrap_admins(...)`,
- creates required directories such as results and model output folders.

Why it belongs to DAL:

- it initializes the database schema,
- it ensures the persistence layer is ready before the app is used.

---

### 4.4 `app.py`

Strictly speaking, `app.py` is the application/configuration layer, not the DAL itself.
But it is closely related because it wires the DAL into the Flask app.

DAL-related responsibilities in this file:

- sets `SQLALCHEMY_DATABASE_URI`,
- sets `SQLALCHEMY_TRACK_MODIFICATIONS`,
- calls `db.init_app(app)`,
- calls `login_manager.init_app(app)`.

So in viva you can say:

> `app.py` does not implement the DAL, but it configures and initializes it.

---

### 4.5 `auth_helpers.py`

This file acts like a small **repository/helper layer** for user data.

Important functions:

- `normalize_email(email)`
- `is_valid_email(email)`
- `get_user_by_email(email)`
- `upsert_google_user(email, role)`
- `sync_bootstrap_admins(admin_emails)`

DAL-style responsibilities here:

- searching users by email,
- creating users,
- updating user role records,
- restoring access when a previously revoked Google account is authorized again,
- committing bootstrap admin users.

Why this matters:

- although not placed in a separate `repositories/` folder,
- this file already behaves like a lightweight user data-access component.

---


- core DAL foundation in `extensions.py`, `models.py`, and `bootstrap.py`,
- actual CRUD/query usage partly inside route/controller files.


---

## 6. Route Files That Currently Perform Data Access

### 6.1 `routes/review.py`

This file performs review-related reads and writes such as:

- fetching pending review items,
- fetching recently reviewed items,
- counting false classifications awaiting retraining,
- updating `HumanReview` fields,
- saving `mask_path`,
- committing review decisions,
- marking items as retrained before background retraining begins.

Examples of DAL-style operations in this file:

- `HumanReview.query.filter_by(...)`
- `HumanReview.query.get_or_404(...)`
- `db.session.commit()`

So although `review.py` is part of the controller layer, it currently contains direct persistence logic.

---

### 6.2 `routes/ml.py`

This file performs inspection-result persistence.

DAL-style responsibilities here:

- creating a new `InspectionRun`,
- saving many `InspectionImageResult` records,
- committing the inspection transaction,
- rolling back when an exception occurs.

Important persistence operations:

- `db.session.add(inspection_run)`
- `db.session.flush()`
- `db.session.add(InspectionImageResult(...))`
- `db.session.commit()`
- `db.session.rollback()`

This file also includes model-path resolution logic, which is not database access, but is still a type of persistence lookup because it reads saved model artifacts from the filesystem.

---

### 6.3 `routes/dashboard.py`

This file reads persistent data for dashboard rendering.

Examples:

- fetches all users for the administrator dashboard,
- calculates administrator overview metrics,
- fetches recent inspection activity across operators for administrators,
- fetches recent `InspectionRun` rows for the current operator,
- fetches review records for images shown in inspection history.

Typical operations:

- `User.query...`
- `InspectionRun.query...`
- `HumanReview.query...`

This is read-only DAL usage from the UI side.

---

### 6.4 `routes/auth.py`

This file handles authentication flow, but it also performs some persistence actions.

Examples:

- finds users by email using `get_user_by_email(...)`,
- creates a bootstrap Google user if needed,
- commits the created user.

So the route uses DAL helpers plus direct transaction control through `db.session.commit()`.

---

### 6.5 `routes/admin.py`

This file supports administrator-driven user creation / authorization and access management.

DAL-style operations:

- validates and normalizes email,
- creates or updates user records through `upsert_google_user(...)`,
- updates user roles,
- sets `access_revoked=True` when access is revoked,
- sets `access_revoked=False` when access is restored,
- commits changes with `db.session.commit()`.

This is another example where controller logic and data persistence are combined.

---

## 7. Main DAL Entities and Their Relationships

The most important stored entities are:

### `User`

Represents a system user.

Connected to:

- many `InspectionRun` records through `operator_id`

Important account-management detail:

- users are revoked by setting `access_revoked=True`, not by deleting the row
- this preserves old inspection history and foreign-key references

### `InspectionRun`

Represents one inspection session.

Connected to:

- one `User`
- many `InspectionImageResult` rows

### `InspectionImageResult`

Represents one inspected image inside a run.

Connected to:

- one `InspectionRun`

### `HumanReview`

Represents human validation/correction of a model prediction.

Connected logically to:

- image results and inspection history through `img_name` / `img_path`
- its parent inspection batch through `inspection_run_id`

Note:

`HumanReview` is linked to `InspectionRun` with `inspection_run_id`, but it is not currently enforced through a formal SQL foreign key to `InspectionImageResult`.
Individual image-level review matching still uses image names and paths at the application level.

This is a good viva point because it shows awareness of the current design.

---

## 8. Common DAL Responsibilities in This Project

The DAL in this system handles the following categories of work:

### 8.1 User Data Management

- create users,
- update user roles,
- revoke user access,
- restore user access,
- fetch users by email,
- load users for login sessions.

Relevant files:

- `models.py`
- `auth_helpers.py`
- `routes/auth.py`
- `routes/admin.py`

### 8.2 Inspection Data Storage

- create an inspection run,
- save summary metrics,
- save image-wise results,
- retrieve run history for operators.

Relevant files:

- `models.py`
- `routes/ml.py`
- `routes/dashboard.py`

### 8.3 Human Review Persistence

- fetch unreviewed review items,
- save review decisions,
- store corrected labels,
- store defect masks,
- track retraining eligibility.

Relevant files:

- `models.py`
- `routes/review.py`
- `run_model.py`

### 8.4 Database Initialization

- create schema,
- prepare initial admin data.

Relevant files:

- `bootstrap.py`
- `app.py`

---
