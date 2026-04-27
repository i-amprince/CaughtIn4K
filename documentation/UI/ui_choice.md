# Choice of User Interface for Our Project

For our software engineering project **CaughtIn4K**, we chose to implement a **Direct Manipulation Web Interface**.

CaughtIn4K is designed to help **quality inspectors detect defects in product images using a machine learning model**. Because the system will be used by inspectors and administrators who may not have technical expertise, we decided to build a **graphical web interface** that allows users to interact with the system using buttons, image uploads, and visual outputs.

Instead of requiring users to type commands, the interface allows them to perform actions such as uploading images, viewing predictions, and submitting feedback through simple interactions in the browser.

---

# Interface Style Used in Our System

Our system uses a **Direct Manipulation Interface**.

In a direct manipulation interface, users interact directly with objects on the screen rather than issuing textual commands. The system responds immediately to user actions, making the interaction intuitive and easy to understand.

In **CaughtIn4K**, direct manipulation occurs through the following interactions:

- Uploading product images using the image upload component
- Clicking buttons to initiate defect inspection
- Viewing prediction results directly on the screen
- Visualizing **Grad-CAM heatmaps** highlighting defect regions
- Providing feedback on model predictions
- Drawing masks for missed defects
- Managing users and roles through admin dashboard controls

These actions are performed using graphical controls such as buttons, upload boxes, and result displays, allowing users to interact naturally with the system.

---

# Justification for Our UI Choice

We selected a **Direct Manipulation Interface** for the following reasons:

1. **Ease of Use**

   Our primary users are **quality inspectors in manufacturing environments**.  
   A graphical interface allows them to interact with the system easily without needing technical knowledge or command-line skills.

2. **Efficient Interaction**

   The inspection process needs to be fast and straightforward.  
   Direct manipulation allows users to quickly upload images, start inspections, and view results using simple clicks.

3. **Visual Representation of Results**

   Our system generates **Grad-CAM heatmaps** that highlight defective regions in product images.  
   A direct manipulation interface makes it easy for users to visually interpret these results.

4. **Immediate Feedback**

   Direct manipulation interfaces provide immediate system responses when users perform actions.  
   When an inspection is run in CaughtIn4K, the system processes the selected test folder and displays prediction results, heatmaps, review status, and dashboard metrics.

5. **Web-Based Accessibility**

   Since the interface is web-based, users can access the system from any device with a browser, such as desktops, laptops, or tablets, without installing additional software.

For these reasons, we concluded that a **Direct Manipulation Web Interface** is the most suitable UI design for the CaughtIn4K system.
