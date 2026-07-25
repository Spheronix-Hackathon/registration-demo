# Hackathon Management Web Application

Production-ready FastAPI + MongoDB hackathon platform with Google OAuth login, individual/team registration, Cashfree payment verification, and IST-standardized timestamps.

For a complete production runbook (OAuth registration, Cashfree setup, server hardening, SSL, and go-live checklist), see `PRODUCTION_DEPLOYMENT.md`.

## 1. Current Architecture (After Refactor)

### Backend
- `app/main.py`: FastAPI app bootstrap, middleware, router registration, lifecycle hooks.
- `app/routers/auth.py`: Google OAuth login + callback.
- `app/routers/students.py`: registration APIs and duplicate checks.
- `app/routers/payments.py`: Cashfree order, verify, webhook.
- `app/routers/teams.py`: team leader metadata APIs.
- `app/routers/colleges.py`: college list endpoint.
- `app/services/*`: business logic (registration flow, Cashfree integration, receipt generation).
- `app/core/*`: shared timezone and logging utilities.
- `app/models/schemas.py`: Pydantic request/response models.
- `app/database/mongodb.py`: sync + async MongoDB clients, indexes, seed data.
- `config/settings.py`: centralized environment configuration.

### Frontend / Static
- `static/index.html`: user registration UI.
- `static/script.js`: frontend logic and API calls.
- `static/style.css`: styling.

### Deployment / Ops
- `scripts/start.sh`: production startup command using Gunicorn + Uvicorn worker.
- `scripts/start.ps1`: Windows equivalent runner.
- `scripts/hackathon.service`: systemd service template.
- `.env.example`: required environment variables.
- `.gitignore`: excludes secrets and virtual environments.

## 2. Data Flow

1. User opens `index.html` from static hosting.
2. Google OAuth (`/api/auth/login`, `/api/auth/callback`) identifies user.
3. Frontend calls duplicate-check endpoints.
4. Frontend creates payment order (`/api/payment/order`).
5. Frontend verifies payment (`/api/payment/verify`) after checkout.
6. Frontend submits registration (`/api/register`).
7. Backend verifies payment again and stores registration/team/payment documents in MongoDB.
8. Backend stores registration and payment data in a single MongoDB registration document.

## 3. Project Structure

```text
hackathon-project/
  app/
    main.py
    routers/
      auth.py
      students.py
      teams.py
      colleges.py
      payments.py
    services/
      cashfree_client.py
      payment_service.py
      registration_service.py
    models/
      schemas.py
    database/
      mongodb.py
  config/
    settings.py
  static/
    index.html
    contact.html
    terms-and-conditions.html
    refund-policy.html
    script.js
    style.css
    css/
    js/
    images/
  templates/
  scripts/
    start.sh
    start.ps1
    hackathon.service
  requirements.txt
  .env.example
  .gitignore
  main.py
```

## 4. Environment Configuration

Create `.env` from `.env.example` and set values:

```env
APP_ENV=production
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=hackathon_db

CORS_ORIGINS=https://your-domain.com

SECRET_KEY=replace-with-long-random-value
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://your-domain.com/api/auth/callback

CASHFREE_APP_ID=
CASHFREE_SECRET_KEY=
CASHFREE_ENVIRONMENT=PRODUCTION
CASHFREE_ALLOW_MOCK_ON_BLOCK=false

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
MAIL_FROM=
```

Email deliverability (important):
- `MAIL_FROM` must use the same sending domain as `SMTP_USER`.
- Publish SPF for your domain to authorize your SMTP provider.
- Enable DKIM signing in your mail provider and publish DKIM DNS records.
- Publish DMARC policy for the same domain as `MAIL_FROM`.
- Use a real production domain mailbox (avoid free/test sender addresses for production).

Recommended DNS records (example pattern):
```dns
yourdomain.com.                 TXT   "v=spf1 include:_spf.your-mail-provider.com ~all"
selector1._domainkey.yourdomain.com. TXT "v=DKIM1; k=rsa; p=<provider-public-key>"
_dmarc.yourdomain.com.          TXT   "v=DMARC1; p=quarantine; adkim=s; aspf=s; rua=mailto:dmarc@yourdomain.com"
```

Notes:
- Replace provider placeholders with values from your SMTP vendor dashboard.
- Without SPF/DKIM/DMARC alignment, emails may still land in Spam even with correct app code.

Notes:
- Legacy env vars `MONGO_URI` and `DB_NAME` are still supported for backward compatibility.
- Do not commit `.env` to version control.

## 5. Local Run

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## 6. Production Run Command

```bash
gunicorn -k uvicorn.workers.UvicornWorker app.main:app
```

Recommended:

```bash
./scripts/start.sh
```

## 7. AWS EC2 Deployment Guide (Ubuntu 22.04, t2.micro)

### Step 1: Create EC2 Instance
- Launch AWS EC2 instance: `Ubuntu Server 22.04 LTS`, `t2.micro`.
- Allow inbound ports: `22` (SSH), `80` (HTTP), `443` (HTTPS).
- Attach Elastic IP (recommended).

### Step 2: Server Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git nginx
```

### Step 3: Clone Project

```bash
git clone <repository>
cd <project-folder>
```

### Step 4: Setup Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure Environment

```bash
cp .env.example .env
nano .env
```

Set production MongoDB URI, Cashfree production keys, OAuth redirect URL, SMTP credentials, and a strong secret key.

### Step 6: Run FastAPI (Smoke Test)

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:
- `http://<EC2_PUBLIC_IP>:8000/api/health`

### Step 7: Configure Nginx Reverse Proxy

Create Nginx site:

```bash
sudo nano /etc/nginx/sites-available/hackathon
```

Add:

```nginx
server {
    listen 80;
    server_name domain.com www.domain.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/hackathon /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 8. Systemd Service (Permanent App Process)

Copy service template:

```bash
sudo cp scripts/hackathon.service /etc/systemd/system/hackathon.service
```

Edit paths/user if needed:

```bash
sudo nano /etc/systemd/system/hackathon.service
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hackathon
sudo systemctl start hackathon
sudo systemctl status hackathon
```

Logs:

```bash
sudo journalctl -u hackathon -f
```

## 9. Security Improvements Implemented

- Centralized secret loading via environment variables (`config/settings.py`).
- `.gitignore` now excludes `.env` and virtual environments.
- Configurable CORS allowlist (`CORS_ORIGINS`) instead of hardcoded wildcard.
- Request validation through strict Pydantic models.
- Payment verification performed server-side before registration is accepted.
- Basic global exception handler with controlled error responses.

## 10. Performance Improvements Implemented

- Modularized architecture for faster maintainability and targeted optimization.
- Async MongoDB operations retained for registration/payment critical paths.
- Indexed MongoDB collections initialized automatically.
- Query projections used in many read operations.
- Gunicorn + Uvicorn worker support added for production concurrency.

## 11. Final Testing Checklist

Validate these flows before go-live:

- User registration (individual) end-to-end.
- User registration (team) with member inheritance rules.
- Google OAuth login callback success/failure.
- Payment order creation, payment verify, registration persist.
- Duplicate protection: email/mobile/roll number/GitHub.
- Team registration with 2-5 members including leader.
- Terms acceptance gate before payment.
- MongoDB writes for `users`, `registrations`, and `teams`.

## 12. Important Operational Note

If credentials were ever committed to the repository, rotate all exposed secrets immediately:
- MongoDB user/password
- Google OAuth client secret
- Cashfree keys
- SMTP app passwords
- JWT/SESSION secret keys
"# registration-demo" 
