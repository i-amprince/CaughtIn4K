# Business Logic Layer (BLL) – AQI System

## Q1. Core Functional Modules of the Business Logic Layer

The AQI (Automated Quality Inspection) system follows a layered architecture where the Business Logic Layer (BLL) acts as an intermediary between the presentation layer (Flask-based UI) and the data layer (SQLAlchemy database models). The core functional modules are as follows:

---

### 1. Inspection Execution Module

* **Description:**
  This module is responsible for executing the anomaly detection model on a batch of input images. It processes images, generates anomaly scores, classifies them as *GOOD* or *DEFECTIVE*, and produces corresponding heatmaps.

* **Implementation:**
  Implemented in `run_model.py` using the function `run_inferencer_batch()`.

* **Interaction with Presentation Layer:**
  Triggered through the dashboard interface when the user initiates inspection. The results are displayed in tabular format on the dashboard and detailed view pages.

* **Example:**
  An input image is processed and classified as:

  ```
  020.png → DEFECTIVE (score: 1.0)
  ```

---

### 2. Human Review Module (Human-in-the-Loop)

* **Description:**
  This module allows a Quality Operator to validate model predictions. The operator can mark predictions as correct or incorrect and provide corrected labels if necessary. In the current implementation, the supported review labels are `GOOD` and `DEFECTIVE`.

* **Implementation:**
  Implemented in `routes/review.py` through the `submit_review()` function.

* **Interaction with Presentation Layer:**
  Accessible via the `/review` page. Users interact through form inputs and buttons to submit their evaluation. Review items are grouped by inspection run so operators can process one run at a time.

* **Example:**

  * Model prediction: DEFECTIVE
  * Human correction: GOOD
  * Stored as:

    ```
    is_correct = False
    human_label = GOOD
    ```

  If the model predicts `GOOD` but the product is actually defective, the operator enters `DEFECTIVE`; the system then redirects to the mask drawing page so the missed defect region can be captured.

---

### 3. Inspection History and Analytics Module

* **Description:**
  This module maintains records of inspection runs and displays detailed results, including human review outcomes and performance metrics such as accuracy.

* **Implementation:**
  Implemented in `routes/dashboard.py` via the `history_detail()` function.

* **Interaction with Presentation Layer:**
  Users access this through the dashboard’s "Recent Inspection History" section.

* **Example:**
  Accuracy is computed as:

  ```
  Accuracy = (Correct Predictions / Total Reviewed) × 100
  ```

---

### 4. User and Role Management Module

* **Description:**
  Handles authentication and authorization, ensuring that users can only access functionalities permitted by their roles. The administrator can authorize Google accounts, change roles, revoke access, and restore access.

* **Implementation:**
  Defined in `models.py`, `routes/admin.py`, `routes/auth.py`, and managed using Flask-Login.

* **Interaction with Presentation Layer:**
  Login interface determines user access and redirects to appropriate dashboard views. The administrator dashboard also displays active users, role breakdown, revoked accounts, recent inspection activity, and review queue metrics.

* **Example:**
  Only users with the role *Quality Operator* can access the review panel.
  If a user's `access_revoked` flag is set, Google OAuth login is blocked even if the email exists in the database.

---

### 5. Model Training Module

* **Description:**
  Enables Manufacturing Engineers to train anomaly detection models using specified datasets.

* **Implementation:**
  Implemented in `routes/ml.py`.

* **Interaction with Presentation Layer:**
  Accessible via a form on the dashboard for engineers.

---

### Interaction Flow

```
Presentation Layer (UI)
        ↓
Business Logic Layer (Routes, Processing Modules)
        ↓
Data Layer (Database Models)
```

---

## Q2A. Business Rules Implementation

Business rules define how the system processes data and enforces constraints.

---

### 1. Role-Based Access Control

* Only authorized users can perform specific actions.
* Administrators can create users, change roles, revoke access, and restore access.
* The system prevents revoking the current administrator's own account and prevents removing the last active System Administrator.
* Example:

  ```python
  if current_user.role != "Quality Operator":
      abort(403)
  ```

---

### 2. Review Decision Rule

* The system updates fields based on user input:

  * If prediction is correct:

    ```
    is_correct = True
    human_label = predicted_label
    ```
  * If incorrect:

    ```
    is_correct = False
    human_label = user-provided label
    ```

* For current project usage:

  ```text
  Predicted GOOD but actual defective -> enter DEFECTIVE, then draw mask
  Predicted DEFECTIVE but actual good -> enter GOOD, no mask required
  ```

---

### 3. Classification Rule

* The model classifies images based on anomaly score:

  ```
  score > threshold → DEFECTIVE
  else → GOOD
  ```

---

### 4. Data Access Rule

* Users can only view inspection runs they initiated:

  ```python
  if run.operator_id != current_user.id:
      abort(403)
  ```

---

### 5. Review Filtering Rule

* Only unreviewed items are shown in the review panel:

  ```python
  HumanReview.query.filter_by(reviewed=False)
  ```

* Pending and recently reviewed records are grouped by `inspection_run_id`.
* Legacy records without a run link are shown as unlinked reviews.

---

## Q2B. Validation Logic

Validation ensures that only correct and meaningful data enters the system.

---

### 1. Input Field Validation

* Ensures required fields are provided in forms:

  ```html
  <input type="text" name="item_name" required>
  ```

---

### 2. Dataset Validation

* Ensures that the provided dataset path contains valid images:

  ```python
  if not image_paths:
      raise ValueError("No images found!")
  ```

---

### 3. Review Input Validation

* Ensures that a corrected label is provided when marking a prediction as incorrect.

---

### 4. Authentication Validation

* Ensures that only authenticated users can access protected routes:

  ```python
  @login_required
  ```

* Ensures revoked accounts cannot complete Google OAuth login:

  ```python
  if user.access_revoked:
      redirect(url_for("auth.login"))
  ```

---

### 5. Database Validation

* Ensures that schema constraints are maintained (e.g., valid boolean fields, non-null paths).

---

## Q2C. Data Transformation

Data transformation ensures compatibility between the data layer and presentation layer.

---

### 1. Model Output Transformation

* Raw model output (boolean or tensor) is converted into human-readable labels:

  ```
  True → DEFECTIVE
  False → GOOD
  ```

---

### 2. Image Path Transformation

* Stored paths are converted into URLs for display:

  ```python
  url_for('static', filename=result.heatmap_url)
  ```

---

### 3. Numerical Formatting

* Scores are formatted for readability:

  ```python
  round(score, 4)
  ```

---

### 4. Review Mapping Transformation

* Review data is mapped using image names for efficient lookup:

  ```python
  review_map[img_name] = review
  ```

---

### 5. Analytical Data Transformation

* Raw counts are converted into performance metrics:

  ```
  Accuracy = (Correct / Reviewed) × 100
  ```

* The administrator dashboard transforms stored data into summary metrics such as active users, role counts, revoked accounts, inspection totals, pending reviews, review accuracy, and corrections awaiting retraining.

---

### Example Transformation Flow

```
Model Output (Tensor)
    → NumPy Conversion
        → Label Conversion
            → Database Storage
                → UI Rendering
```

---

## Conclusion

The AQI system effectively implements a structured Business Logic Layer that:

* Enforces domain-specific business rules,
* Validates incoming data,
* Transforms data for user-friendly presentation,
* Integrates human feedback into the inspection pipeline.

This layered design enhances system reliability, maintainability, and scalability.
