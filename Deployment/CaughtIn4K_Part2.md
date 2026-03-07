# Part II — User Access & System Interaction

## How End Users Access the Services

Users access CaughtIn4K entirely through a **web browser** — no installation or setup required on the user's side. The Quality Inspector navigates to the hosted URL (e.g., `https://caughtin4k.app`), which resolves to the **Elastic IP** of the AWS EC2 instance. From there, Nginx handles the HTTPS connection and serves the Flask-rendered pages back to the browser.

### What the user can do from the browser:

| Action | URL Endpoint | Description |
|---|---|---|
| Upload product image | `POST /upload` | Inspector uploads image for inspection |
| View inspection result | `GET /result/<id>` | See defect prediction + Grad-CAM heatmap |
| Submit human feedback | `POST /feedback` | Confirm or correct the model's prediction |
| View inspection history | `GET /history` | Browse past inspection records |
| Trigger model retrain | `POST /retrain` | Admin triggers continual learning update |

> **Key point:** Users never interact with S3, RDS, or the ML engine directly. All access goes through the Flask API, which acts as the sole gatekeeper.

---

## Pictorial Representation — System Interaction Diagram

### Layer 1 — User to Frontend

```
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
                                       │  Internal — Port 5000
                                       │
```

---

### Layer 2 — Frontend to Backend (Application Layer)

```
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
               │ • Preprocessing  │     │ • inspection_results  │
               │ • Anomaly Model  │     │ • feedback_store      │
               │ • Grad-CAM       │     │ • model_registry      │
               │ • Confidence     │     │                       │
               │   Scoring        │     └───────────────────────┘
               │ • Continual      │
               │   Learning       │
               └───────┬──────────┘
                       │
                       │  boto3 SDK
                       │
               ┌───────▼──────────────────────────────────────┐
               │                  AWS S3                       │
               │                                               │
               │  caughtin4k-uploads/   → product images       │
               │  caughtin4k-models/    → model weights        │
               │  caughtin4k-heatmaps/  → Grad-CAM outputs     │
               └───────────────────────────────────────────────┘
```

---

### Layer 3 — Human-in-the-Loop Feedback Cycle

```
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
```

---

## Complete End-to-End Interaction Flows

### Flow 1 — Image Upload & Inspection

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

---

### Flow 2 — View Result & Heatmap

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

---

### Flow 3 — Human Feedback & Model Update

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

---

### Flow 4 — Inspection History

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

---

## Component Interaction Summary

| Component A | Interaction | Component B | Protocol / Method |
|---|---|---|---|
| Browser | sends request to | Nginx | HTTPS / TLS 1.3 |
| Nginx | forwards to | Flask API (Gunicorn) | HTTP internal (port 5000) |
| Flask API | calls | ML Inference Engine | Python function call (same process) |
| Flask API | reads/writes | AWS RDS (PostgreSQL) | SQLAlchemy ORM over TCP |
| Flask API | stores/retrieves files | AWS S3 | boto3 SDK (HTTPS) |
| ML Engine | saves model weights | AWS S3 | boto3 SDK |
| Human Inspector | submits feedback | Flask API | HTTPS POST request |
| Flask API | triggers | Continual Learning | Internal Python call |
