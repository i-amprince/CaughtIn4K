# Software Test Plan  
**Module Focus: Human Review, Inference & Feedback Workflow**  
**Version 2.0 | April 2026**

---

## 1. Objective of Testing

The objective of testing the *CaughtIn4K* system is to validate the correctness, reliability, and robustness of the **Human Review, Inference, and Feedback workflow**, which forms the core functionality of the system.

The testing aims to:

- Verify that inspection results are generated correctly using the trained model
- Ensure that inference runs asynchronously without blocking the UI
- Validate that users can review predictions and provide feedback accurately
- Confirm correct redirection to the mask drawing interface for incorrect predictions
- Ensure proper validation of mask submission based on coverage threshold
- Verify that retraining is triggered only after the required number of incorrect reviews
- Detect inconsistencies between review panel data and inspection analytics
- Ensure proper error handling for invalid model paths or missing items

---

## 2. Scope

### In Scope

| Module | Features Covered |
|--------|----------------|
| ML Inference (`/run_inspection`) | Background execution, result generation, model path validation |
| Review Panel (`/review`) | Display predictions, pending reviews, review actions |
| Review Actions | Mark correct/incorrect predictions |
| Mask Drawing (`/draw_mask`) | Draw defect masks, validate coverage |
| Feedback Handling | Store human review and mask data |
| Retraining Logic | Trigger retraining after threshold (e.g., 10 incorrect reviews) |
| Review Analytics | Display review status and inspection results |
| Error Handling | Invalid model path, missing dataset, unsupported item |

---

### Out of Scope

- Authentication and user login system
- Model training algorithm internals
- Hardware/camera input
- Production environment

---

## 3. Types of Testing

| Type | Description |
|------|------------|
| Unit Testing | Testing helper functions like validation, mask processing |
| Integration Testing | Interaction between inference, review, and database |
| System Testing | End-to-end workflow (inspection → review → retrain) |
| Black-box Testing | Testing based on inputs and outputs without internal knowledge |
| UI Testing | Buttons, navigation, and real-time updates |
| Negative Testing | Invalid inputs (wrong label, invalid path, missing model) |
| Performance Testing | Background inference execution without UI blocking |
| Regression Testing | Ensuring updates do not break existing features |

---

## 4. Tools Used

| Tool | Purpose |
|------|--------|
| Python unittest | Automated testing framework |
| Flask Test Client | Simulating backend requests |
| SQLite (in-memory) | Temporary test database |
| Web Browser (Chrome) | Manual UI testing |
| Terminal / Logs | Monitoring execution and errors |

---

## 5. Entry Criteria

Testing will begin when:

- Application runs successfully (`python app.py`)
- Required dependencies and model files are available
- Database is initialized
- Review panel (`/review`) and inspection module are accessible
- Sample images or datasets are available

---

## 6. Exit Criteria

Testing will be considered complete when:

- 8 test cases are executed
- Both successful and failure scenarios are validated
- Real system limitations and defects are identified
- All critical workflows are tested:
  - Inference execution
  - Review process
  - Mask validation
  - Retraining trigger
- Identified defects are documented with proper analysis
- System behavior is consistent across UI and backend (or inconsistencies are reported)

---

## Part B — Test Cases

**Module Under Test:** Human Review, Inference & Feedback Workflow  
(`/run_inspection`, `/review`, `/draw_mask`)

| TC ID | Test Scenario / Description | Input Data | Expected Output | Actual Output | Status |
|------|----------------------------|-----------|----------------|--------------|--------|
| TC-REV-01 | Load review panel with pending items | Open `/review` | Pending images and predictions displayed correctly | Pending reviews displayed correctly with labels and scores | Pass |
| TC-REV-02 | Review panel empty state | No pending reviews available | Message indicating no pending reviews | Proper empty state message displayed | Pass |
| TC-REV-03 | Mark prediction as Correct | Click ✓ Correct on a review item | Review marked correct and removed from queue | Review successfully removed from pending list | Pass |
| TC-REV-04 | Mark prediction as Incorrect | Click ✗ Incorrect | Redirect to `/draw_mask/<id>` | Redirect works correctly to mask editor | Pass |
| TC-REV-05 | Mask submission validation (threshold check) | Draw mask below minimum coverage | Submission should be blocked | Submission correctly blocked until threshold is met | Pass |
| TC-REV-06 | Retraining trigger behavior | Submit only 1 incorrect review | Retraining should trigger immediately | Retraining does NOT trigger until threshold (10) is reached | Fail |
| TC-REV-07 | Invalid review input handling | Enter incorrect/invalid label manually | Should still redirect to mask drawing page | Does not redirect to mask page for invalid input | Fail |
| TC-REV-08 | Review analytics synchronization | Refresh inspection results page | Review status should match review panel | Inconsistency observed between review panel and inspection details | Fail |

---