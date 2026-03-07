# Part I — Hosting & Deployment on AWS

## I. Host Site — Target Server/Cloud for Each Component

| Component | AWS Service | Details |
|---|---|---|
| Web UI (Flask Templates / HTML) | **AWS EC2** (t2.micro, Ubuntu 22.04) | Serves the Flask app via Nginx reverse proxy |
| Flask REST API (`app.py`) | **AWS EC2** (same instance) | Gunicorn WSGI server behind Nginx on port 80/443 |
| ML Inference Engine (`image_preprocessing.py`, anomaly model) | **AWS EC2** (same instance) | Runs as part of the Flask process; can be offloaded to AWS Lambda if model is lightweight |
| Database | **AWS RDS** (PostgreSQL, free tier) | Separate managed DB instance in the same AWS region |
| Uploaded Images & Model Weights | **AWS S3** | Persistent object storage — two buckets: `caughtin4k-uploads` and `caughtin4k-models` |
| Static Assets (CSS, JS, Heatmap outputs) | **AWS S3** | Fast global delivery of static content |

---

## II. Deployment Strategy — Step-by-Step

### Step 1 — Provision EC2 Instance
- Launch a `t2.micro` Ubuntu 22.04 instance on AWS (free tier eligible)
- Configure a **Security Group** to allow:
  - Port **22** (SSH — from your IP only)
  - Port **80** (HTTP)
  - Port **443** (HTTPS)
- Assign an **Elastic IP** so the server address stays fixed after reboots

### Step 2 — Server Setup
- SSH into the EC2 instance
- Install required packages:
  ```bash
  sudo apt update
  sudo apt install python3 python3-pip nginx git -y
  pip install gunicorn
  ```
- Clone the repository:
  ```bash
  git clone https://github.com/i-amprince/CaughtIn4K
  cd CaughtIn4K
  pip install -r requirements.txt
  ```

### Step 3 — Configure Gunicorn
- Create a **systemd service** so Gunicorn starts automatically on reboot:
  ```bash
  gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
  ```
- This keeps the Flask app running as a background process on internal port 5000

### Step 4 — Configure Nginx as Reverse Proxy
- Set up Nginx to listen on **port 80/443** and forward requests to Gunicorn on port 5000
- Nginx also serves static files (CSS, heatmap images) directly for better performance
- This is the **public-facing entry point** — Flask is never directly exposed to the internet

### Step 5 — Connect to AWS RDS (PostgreSQL)
- Create an **RDS PostgreSQL** instance in the same AWS region (e.g., `ap-south-1`)
- Configure the **RDS Security Group** to allow inbound connections **only from the EC2 instance's private IP**
- Store the DB connection string as an environment variable:
  ```bash
  export DATABASE_URL="postgresql://user:password@rds-endpoint:5432/caughtin4k"
  ```
- SQLAlchemy in `app.py` connects to RDS automatically via this variable

### Step 6 — Connect to AWS S3 for File Storage
- Configure **boto3** (AWS Python SDK) in the Flask app
- Uploaded product images are saved to `s3://caughtin4k-uploads/`
- Model weights and Grad-CAM heatmap outputs are stored in `s3://caughtin4k-models/`
- EC2 accesses S3 via an **IAM Role** attached to the instance — no hardcoded AWS keys needed

### Step 7 — Enable HTTPS with SSL Certificate
- Install **Certbot (Let's Encrypt)** on the EC2 instance:
  ```bash
  sudo apt install certbot python3-certbot-nginx -y
  sudo certbot --nginx -d yourdomain.com
  ```
- Configure Nginx to **redirect all HTTP traffic to HTTPS** on port 443 automatically

### Step 8 — API Communication Between Components

| From | To | Method |
|---|---|---|
| Browser | Nginx (port 443) | HTTPS request |
| Nginx | Gunicorn / Flask | Internal forward to port 5000 |
| Flask API | ML Inference Engine | Direct Python function call (same process) |
| Flask API | AWS S3 | `boto3` SDK (save/retrieve images & weights) |
| Flask API | AWS RDS | SQLAlchemy ORM (store results & feedback) |
| `POST /retrain` | AWS S3 | Updated model weights pushed back to S3 |

### Step 9 — Auto-restart & Monitoring
- Enable **systemd** service for Gunicorn so it restarts automatically on crash
- Enable **AWS CloudWatch** for:
  - Application logs
  - CPU and memory usage alerts
  - Inference latency tracking
  - Error rate monitoring

---

## III. Security Measures

### Firewall — AWS Security Groups
- EC2 Security Group only allows:
  - **Port 22** — SSH from your IP only
  - **Port 80** — HTTP (redirected to HTTPS)
  - **Port 443** — HTTPS public traffic
- RDS Security Group only allows inbound from the **EC2 instance's private IP** — never publicly exposed

### HTTPS / Encryption in Transit
- All user traffic encrypted via **TLS 1.3**
- HTTP automatically redirected to HTTPS via Nginx configuration

### IAM Roles — No Hardcoded Credentials
- EC2 accesses S3 and other AWS services through an **IAM Role** with least-privilege permissions
- No AWS access keys are stored in code or `.env` files

### Encryption at Rest
- S3 buckets configured with **SSE-S3** (server-side encryption)
- RDS storage encryption enabled at instance creation

### Input Validation
- Flask enforces **file type whitelist** (JPG/PNG only)
- Maximum upload file size enforced
- **CSRF protection** on all form submissions via Flask-WTF
- **Parameterised SQL queries** via SQLAlchemy — prevents SQL injection attacks
