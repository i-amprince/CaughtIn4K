## Execution of Test Cases and Results

**Module Under Test:** Human Review, Inference & Feedback Workflow  
**Environment:** Localhost (Flask Server)  
**Command Used:** `python app.py`  
**Browser:** Google Chrome  

The following test cases were executed manually using the web interface and verified using terminal logs and UI behavior.

---

| TC ID | Test Scenario | Execution Steps | Expected Output | Actual Output Observed | Status | Evidence |
|------|--------------|----------------|----------------|----------------------|--------|----------|
| TC-REV-01 | Load review panel with pending items | Open `http://127.0.0.1:5000/review` | Pending images and predictions displayed | Review panel displayed correctly with pending items and scores | Pass | Screenshot of review panel showing pending items |
| TC-REV-02 | Review panel empty state | Ensure no pending reviews and open `/review` | Message indicating no pending reviews | Proper empty state message displayed | Pass | Screenshot showing empty review panel message |
| TC-REV-03 | Mark prediction as Correct | Click ✓ Correct on a review item | Item removed from pending list | Item successfully removed from queue | Pass | Screenshot before and after clicking ✓ Correct |
| TC-REV-04 | Mark prediction as Incorrect | Click ✗ Incorrect on a review item | Redirect to `/draw_mask/<id>` | Successfully redirected to mask editor page | Pass | Screenshot of browser URL showing `/draw_mask/<id>` |
| TC-REV-05 | Mask submission validation | Draw mask below minimum coverage and attempt submit | Submission should be blocked | Submission prevented until required coverage is reached | Pass | Screenshot of mask editor showing coverage value and disabled submission |
| TC-REV-06 | Retraining trigger behavior | Submit only one incorrect review | Retraining should trigger immediately | Retraining not triggered (requires threshold of 10 incorrect reviews) | Fail | Terminal logs showing no retraining triggered |
| TC-REV-07 | Invalid review input handling | Enter incorrect/invalid label manually | System should still redirect to mask page | No redirect occurs for invalid input | Fail | Screenshot showing no navigation after invalid input |
| TC-REV-08 | Review analytics synchronization | Refresh inspection results page after review | Status should match review panel | Inconsistent status between review panel and inspection details observed | Fail | Screenshot comparing review panel vs inspection results |

---

## Summary of Execution

- Total Test Cases Executed: **8**
- Passed: **5**
- Failed: **3**

---

## Notes on Evidence Collection

- **Review Panel Screenshot:** Use for TC-REV-01, TC-REV-03  
- **Mask Editor Screenshot (with coverage %):** Use for TC-REV-04, TC-REV-05  
- **Terminal Logs:** Use for retraining behavior (TC-REV-06)  
- **UI Behavior Screenshots:** Use for TC-REV-07 and TC-REV-08 to show incorrect behavior  

---
