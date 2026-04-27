# Automated Quality Inspection Test Cases

This project implements an Automated Quality Inspection (AQI) system described in [SRS/SRS.tex](/d:/SEMVI/SE/CaughtIn4K/SRS/SRS.tex:43). The main test targets mapped from the SRS are:

- user authentication and role-based access
- administrator dashboard and account-access management
- model training for a product/item
- model lifecycle management for manufacturing engineers
- batch inspection and anomaly classification
- review workflow for human-in-the-loop correction
- mask capture for missed defects
- history and audit visibility
- threshold-based retraining

## White-Box Testing

White-box testing in this project focuses on internal logic, branch conditions, helper functions, and control flow.

| ID | Module | Internal path tested | Expected result |
|---|---|---|---|
| WB-01 | `auth_helpers.py` | email normalization and validation branches | valid emails pass, malformed emails fail |
| WB-02 | `routes/auth.py` | verified-email handling for `True`, `"true"`, and false values | only verified Google accounts are accepted |
| WB-03 | `routes/auth.py` | revoked Google account after OAuth callback | login is denied and user returns to login page |
| WB-04 | `routes/ml.py` | model-path resolution across primary and legacy output folders | correct `.pt` file path is returned |
| WB-05 | `routes/review.py` | item-name inference from saved result filename | prefix is extracted correctly |
| WB-06 | `training.py` | MVTec dataset validation for valid item structure | valid dataset passes validation |
| WB-07 | `training.py` | MVTec dataset validation when a defect image has no ground-truth mask | validation raises `ValueError` |
| WB-08 | `routes/review.py` | retrain threshold logic when pending corrections are below threshold | retraining is not started |
| WB-09 | `routes/review.py` | retrain threshold logic when pending corrections reach threshold | items are marked retrained and background launch is triggered |
| WB-10 | `routes/ml.py` | model-path resolution when an active registered model version exists | active registry version is used for inference |

## Black-Box Testing

Black-box testing in this project focuses on user-visible behavior without depending on internal code knowledge.

| ID | Feature | Input / action | Expected result |
|---|---|---|---|
| BB-01 | Dashboard access | open `/dashboard` while logged out | redirect to login page |
| BB-02 | User management | admin submits valid email and role | user is created/authorized successfully |
| BB-03 | User management security | non-admin submits create-user form | request is rejected and no user is created |
| BB-04 | Admin dashboard overview | admin opens dashboard | system overview, recent inspection activity, role breakdown, and review queue are visible |
| BB-05 | Role change | admin changes a user's role | user's stored role is updated |
| BB-06 | Access revocation | admin revokes and restores a user | `access_revoked` toggles correctly |
| BB-07 | Access revocation security | non-admin attempts to revoke a user | request is rejected and access remains active |
| BB-08 | Admin self-protection | admin attempts to revoke own account | request is rejected and access remains active |
| BB-09 | Last-admin protection | only admin attempts to demote self | request is rejected and role remains System Administrator |
| BB-10 | Inspection workflow | operator starts inspection for an item without trained weights | redirected with model-not-found error |
| BB-11 | History access control | owner opens their run history; another operator opens same run | owner allowed, other operator gets `403` |
| BB-12 | Review workflow | operator marks `GOOD` prediction as actually `DEFECTIVE` | system redirects to mask drawing page |
| BB-13 | Mask submission | operator submits a valid defect mask | mask file is saved and review is marked complete |
| BB-14 | Engineer dashboard | manufacturing engineer opens `/dashboard` | model lifecycle workspace, validation, registry, retraining queue, history, and logs are visible |
| BB-15 | Dataset validation | engineer submits item name and valid dataset path | validation report is rendered with image/category counts |

## Executed Automated Tests

The executable test suite for these cases is stored in:

- [tests/test_white_box.py](/d:/SEMVI/SE/CaughtIn4K/tests/test_white_box.py:1)
- [tests/test_black_box.py](/d:/SEMVI/SE/CaughtIn4K/tests/test_black_box.py:1)

Run command:

```powershell
python -m unittest discover -s tests -v
```

Latest local execution result:

- Date: 2026-04-27
- Total executed tests: 26
- Status: 26 passed, 0 failed
- Notes: the run completed successfully in the local development environment using Python `unittest`
