# Part II — User Access & System Interaction

## How End Users Access the Services

Users access **CaughtIn4K** entirely through a **web browser**, meaning no installation or local setup is required on the user's device.

The **Quality Inspector or Admin** navigates to the hosted URL (for example `https://caughtin4k.app`). This domain resolves to the **Elastic IP address of the AWS EC2 instance** where the application is deployed.

When the browser sends a request:

1. The request reaches the **Nginx web server** running on the EC2 instance.
2. Nginx handles the **HTTPS (TLS 1.3) secure connection**.
3. Nginx then forwards the request internally to the **Flask application running through Gunicorn**.
4. Flask processes the request, communicates with the **ML inference engine**, **AWS RDS database**, and **AWS S3 storage** if necessary.
5. The processed response (HTML page, prediction result, or history record) is returned back through Nginx to the user's browser.

### What the user can do from the browser

| Action | URL Endpoint | Description |
|---|---|---|
| Upload product image | `POST /upload` | Inspector uploads image for inspection |
| View inspection result | `GET /result/<id>` | See defect prediction + Grad-CAM heatmap |
| Submit human feedback | `POST /feedback` | Confirm or correct the model's prediction |
| View inspection history | `GET /history` | Browse past inspection records |
| Trigger model retrain | `POST /retrain` | Admin triggers continual learning update |

> **Important:** Users never interact directly with **AWS S3**, **AWS RDS**, or the **ML engine**.  
> All access is routed through the **Flask API**, which acts as the central controller and gatekeeper of the system.

---

# Pictorial Representation — System Interaction Diagram

## Layer 1 — User to Frontend

                    ┌─────────────────────────────────────┐
                    │           END USER (Browser)         │
                    │   Quality Inspector / Admin          │
                    │   Chrome / Firefox / Mobile          │
                    └──────────────┬──────────────────────┘
                                   │
                                   │  HTTPS (TLS 1.3) — Port 443
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         AWS EC2 — Nginx              │
                    │   • Reverse Proxy                    │
                    │   • SSL Termination                  │
                    │   • Serves static files (CSS/JS)     │
                    │   • Forwards to Gunicorn:5000        │
                    └──────────────┬──────────────────────┘
                                   │
                                   │  Internal HTTP — Port 5000
                                   │
                                   

## Layer 2 — Frontend to Backend (Application Layer)

                    ┌──────────────▼──────────────────────┐
                    │     Flask REST API — app.py          │
                    │         (Gunicorn WSGI)              │
                    │                                      │
                    │  POST /upload                        │
                    │  GET  /result/<id>                   │
                    │  POST /feedback                      │
                    │  GET  /history                       │
                    │  POST /retrain                       │
                    └──────┬──────────────┬───────────────┘
                           │              │
                calls      │              │  queries
                           │              │
           ┌───────────────▼──┐     ┌────▼──────────────────┐
           │  ML Inference    │     │   AWS RDS             │
           │  Engine          │     │   (PostgreSQL)        │
           │                  │     │                       │
           │ • Image         │     │ • inspection_results  │
           │   Preprocessing │     │ • feedback_store      │
           │ • Anomaly Model │     │ • model_registry      │
           │ • Grad-CAM      │     │                       │
           │ • Confidence    │     │                       │
           │   Scoring       │     └───────────────────────┘
           │ • Continual     │
           │   Learning      │
           └───────┬──────────┘
                   │
                   │ boto3 SDK
                   │
           ┌───────▼──────────────────────────────────────┐
           │                  AWS S3                       │
           │                                               │
           │  caughtin4k-uploads/   → product images       │
           │  caughtin4k-models/    → model weights        │
           │  caughtin4k-heatmaps/  → Grad-CAM outputs     │
           └───────────────────────────────────────────────┘

# Layer 3 — Human-in-the-Loop Feedback Cycle

 Inspector views result
         │
         │  Agrees / Disagrees with prediction
         ▼
 POST /feedback  ──►  Flask API  ──►  RDS (save label)
                                           │
                                           ▼
                                  ML Continual Learning
                                  (incremental weight update)
                                           │
                                           ▼
                                  New weights saved to S3
                                           │
                                           ▼
                                  Model improves over time ✓


# Complete End-to-End Interaction Flows

## Flow 1 — Image Upload & Inspection

```

Browser          Nginx           Flask API        ML Engine         S3          RDS
│                │                │                │              │            │
│── POST /upload ──►              │                │              │            │
│                │── forward ────►│                │              │            │
│                │                │── preprocess ─►│              │            │
│                │                │                │── save img ─►│            │
│                │                │◄── score +     │              │            │
│                │                │    heatmap ────│              │            │
│                │                │── store result ──────────────────────────►│
│                │◄── render ─────│                │              │            │
│◄── result page ┤                │                │              │            │

```

## Flow 2 — View Result & Heatmap

```

Browser          Nginx           Flask API                    S3          RDS
│                │                │                         │            │
│── GET /result/<id> ──►          │                         │            │
│                │── forward ────►│                         │            │
│                │                │── fetch prediction ───────────────►│
│                │                │── fetch heatmap URL ──►│            │
│                │◄── render page ┤                         │            │
│◄── heatmap + score ─────────────┤                         │            │

```

## Flow 3 — Human Feedback & Model Update

```

Browser          Flask API         RDS              ML Engine         S3
│                │               │                   │              │
│── POST /feedback ──►           │                   │              │
│                │── store ─────►│                   │              │
│                │               │── trigger learn ─►│              │
│                │               │                   │── save ─────►│
│                │               │                   │   weights    │
│◄── 200 OK ─────┤               │                   │              │

```

## Flow 4 — Inspection History

```

Browser          Nginx           Flask API                         RDS
│                │                │                               │
│── GET /history ──►              │                               │
│                │── forward ────►│                               │
│                │                │── SELECT * FROM results ─────►│
│                │                │◄── return records ────────────│
│                │◄── render table┤                               │
│◄── history page┤                │                               │

```

# Component Interaction Summary

| Component A | Interaction | Component B | Protocol / Method |
|---|---|---|---|
| Browser | sends request to | Nginx | HTTPS / TLS 1.3 |
| Nginx | forwards request to | Flask API (Gunicorn) | Internal HTTP (Port 5000) |
| Flask API | calls | ML Inference Engine | Python function call (same process) |
| Flask API | reads/writes | AWS RDS (PostgreSQL) | SQLAlchemy ORM over TCP |
| Flask API | stores/retrieves files | AWS S3 | boto3 SDK (HTTPS) |
| ML Engine | saves model weights | AWS S3 | boto3 SDK |
| Human Inspector | submits feedback | Flask API | HTTPS POST request |
| Flask API | triggers | Continual Learning module | Internal Python function |
