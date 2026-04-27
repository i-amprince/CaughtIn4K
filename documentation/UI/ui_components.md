# 1. User Interaction with the System

The following steps describe how a user interacts with the CaughtIn4K interface.

## Step 1 — Upload Product Image

The inspector uploads a product image using the upload interface.

The browser sends a request to the backend:

```
POST /upload
```

The Flask backend receives the image and sends it to the machine learning inference engine for defect detection.

---

## Step 2 — Image Processing

The ML model processes the image and performs:

* Image preprocessing
* Anomaly detection
* Grad-CAM heatmap generation
* Confidence score calculation

The image and heatmap are stored in **AWS S3**, and inspection results are stored in **AWS RDS**.

---

## Step 3 — Display Inspection Result

After processing, the system returns the prediction results to the browser.

The UI displays:

* Defect prediction
* Confidence score
* Grad-CAM heatmap highlighting the defect area

---

## Step 4 - Human Review Feedback

The Quality Operator reviews inspection predictions through the review panel.

The browser sends the feedback request:

```
POST /submit_review/<review_id>
```

If the prediction is correct, the operator clicks **Correct**.
If the prediction is wrong, the operator enters the true label (`GOOD` or `DEFECTIVE`) and clicks **Incorrect - Retrain**.
When the model predicts `GOOD` but the actual product is `DEFECTIVE`, the operator is redirected to the mask drawing page:

```
GET /draw_mask/<review_id>
POST /submit_mask/<review_id>
```

The corrected label and optional mask path are stored in the database and later used for continual model learning.

---

## Step 5 — Viewing Inspection History

Users can view previous inspection records.

The browser sends a request:

```
GET /history
```

The backend retrieves the inspection data from the database and displays it in the history table.

---

## Step 6 - Administrator Dashboard

System Administrators use the dashboard to manage access and monitor system activity.

The admin dashboard shows:

* Active user count
* Role breakdown
* Revoked account count
* Recent inspection activity
* Pending review count
* Review accuracy
* Corrections waiting for retraining

Admins can also change user roles, revoke account access, and restore account access without deleting historical inspection records.

---

# 4. Interaction Summary

Through this UI implementation, users can perform the following actions:

* Upload product images
* Run automated defect detection
* View model predictions and heatmaps
* Provide feedback to improve the model
* Review historical inspection results
* Manage user roles and account access as an administrator

The user interface provides a simple and intuitive way for inspectors to interact with the **CaughtIn4K defect detection system** while the backend services handle machine learning inference and data storage.

```

---
