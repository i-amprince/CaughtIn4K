# Layered Architecture

## 1. Presentation Layer
Handles user interface and client-side behavior.

Files:
- `templates/login.html`
- `templates/dashboard.html`
- `static/css/login.css`
- `static/css/dashboard.css`
- `static/js/login.js`
- `static/js/dashboard.js`

## 2. Controller / Routing Layer
Handles HTTP requests, role checks, and route flow.

Files:
- `routes/auth.py`
- `routes/dashboard.py`
- `routes/admin.py`
- `routes/ml.py`

## 3. Business Logic / Service Layer
Handles core application logic such as preprocessing, training, and inference.

Files:
- `training.py`
- `run_model.py`
- `image_preprocessing.py`
- `preprocess.py`

## 4. Data Access / Persistence Layer
Handles database models, DB connection, and initial data setup.

Files:
- `models.py`
- `extensions.py`
- `bootstrap.py`

## 5. Application / Configuration Layer
Initializes the Flask app and connects all layers.

Files:
- `app.py`
