## Defect Identification and Analysis

The following defects were identified during the execution of test cases in the Human Review, Inference & Feedback workflow.

---

### BUG-01: Retraining Not Triggered for Single Incorrect Review

- **Related Test Case:** TC-REV-06  

#### Description
Retraining is not triggered immediately after marking a prediction as incorrect. The system waits until a threshold (10 incorrect reviews) is reached.

#### Steps to Reproduce
1. Run the application (`python app.py`)
2. Perform inspection and open `/review`
3. Mark one prediction as **Incorrect**
4. Observe system behavior

#### Expected Result
- Retraining should trigger immediately after incorrect feedback

#### Actual Result
- Retraining does not trigger until 10 incorrect reviews are accumulated

#### Severity
 Low

#### Analysis
- This is a **design-based limitation**, not a crash
- Causes confusion to users expecting immediate feedback loop

#### Suggested Fix
- Provide UI feedback such as:
  - “Retraining will start after 10 incorrect reviews”
- OR allow optional immediate retraining for single feedback

---

### BUG-02: Invalid Input Does Not Trigger Mask Workflow

- **Related Test Case:** TC-REV-07  

#### Description
When invalid or unexpected input (e.g., incorrect/false text) is entered instead of using predefined actions, the system does not redirect to the mask drawing page.

#### Steps to Reproduce
1. Open `/review`
2. Attempt to provide incorrect input manually instead of using buttons
3. Submit action

#### Expected Result
- System should either:
  - Validate input and reject it  
  - OR redirect to `/draw_mask/<id>`

#### Actual Result
- No redirection occurs
- System does not handle invalid input properly

#### Severity
Medium

#### Root Cause
- Lack of input validation and strict UI control

#### Suggested Fix
```python
# Enforce allowed inputs only
if action not in ["correct", "incorrect"]:
    return "Invalid action", 400
````

* Disable manual input and enforce button-based actions

---

### BUG-03: Review Analytics Synchronization Issue

* **Related Test Case:** TC-REV-08

#### Description

After submitting reviews, the status displayed in the inspection results page does not always match the review panel.

#### Steps to Reproduce

1. Perform inspection
2. Review items in `/review`
3. Refresh inspection results page
4. Compare statuses

#### Expected Result

* Review status should be consistent across:

  * Review panel
  * Inspection results

#### Actual Result

* Mismatch observed between pages
* Review panel shows updated status, but inspection details sometimes show outdated data

#### Severity

  Medium

#### Root Cause

* Possible delay in database commit or caching issue
* UI not refreshing latest state

#### Suggested Fix

* Ensure DB session commit after review submission:

```python
db.session.commit()
```

* Reload latest data on page refresh
* Avoid caching stale data in frontend

---

## Summary of Defects

| Bug ID | Issue                          | Severity |
| ------ | ------------------------------ | -------- |
| BUG-01 | Delayed retraining trigger     | Low   |
| BUG-02 | Invalid input not handled      | Medium   |
| BUG-03 | Review analytics inconsistency | Medium    |

---


