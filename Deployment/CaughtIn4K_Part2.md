# Part II — User Access & System Interaction

## 1. How End Users Access the Services

End users access the **CaughtIn4K application through a web browser**.  
The application is hosted on an **AWS EC2 cloud server**, which serves both the web interface and the backend API.

A user (Quality Inspector or Admin) opens the application by visiting the hosted URL (for example `https://caughtin4k.app`). The request is received by the **Nginx web server**, which securely forwards the request to the **Flask backend application** running on the server.

The backend processes the request, interacts with the **machine learning inference engine**, and retrieves or stores data in **AWS RDS (PostgreSQL)** and **AWS S3 storage**.

Finally, the processed result is returned to the browser and displayed to the user.

### Actions Performed by the User

| Action | Endpoint | Description |
|------|------|------|
| Upload product image | `/upload` | User uploads a product image for inspection |
| View inspection result | `/result/<id>` | Displays prediction and defect heatmap |
| Submit feedback | `/feedback` | User confirms or corrects prediction |
| View inspection history | `/history` | Shows past inspection records |
| Retrain model | `/retrain` | Admin triggers model retraining |

All communication between the user and the system happens **through the Flask backend API**, which acts as the central controller of the system.

---

# 2. Pictorial Representation of System Interaction

## Overall System Architecture

```

```
               +----------------------+
               |        User          |
               |    (Web Browser)    |
               +----------+-----------+
                          |
                          | HTTPS Request
                          v
               +----------------------+
               |      Nginx Server    |
               |   (AWS EC2 Instance) |
               +----------+-----------+
                          |
                          | Forward Request
                          v
               +----------------------+
               |     Flask Backend    |
               |       REST API       |
               +----+-----------+-----+
                    |           |
                    |           |
                    v           v
          +---------------+   +------------------+
          | ML Inference  |   | AWS RDS Database |
          | Engine        |   | (PostgreSQL)     |
          +-------+-------+   +------------------+
                  |
                  |
                  v
            +------------+
            |   AWS S3   |
            | Image &    |
            | Model Data |
            +------------+
```

```

---

# 3. Interaction Between Components

The interaction between different system components occurs as follows:

1. The **user uploads an image** using the web interface.
2. The request is sent to the **Nginx server** hosted on AWS EC2.
3. Nginx forwards the request to the **Flask backend API**.
4. The Flask API sends the image to the **ML inference engine** for defect detection.
5. The image and generated heatmap are stored in **AWS S3**.
6. Inspection results and metadata are stored in **AWS RDS PostgreSQL database**.
7. The prediction result and heatmap are returned to the user’s browser.

---

# 4. Feedback and Continuous Learning Interaction

The system also includes a **human-in-the-loop feedback mechanism**.

1. The inspector views the prediction result.
2. The user submits feedback using the `/feedback` endpoint.
3. The feedback is stored in **AWS RDS**.
4. The ML engine uses this feedback during retraining to improve the model.
5. Updated model weights are saved to **AWS S3**, allowing the system to improve future predictions.
```
