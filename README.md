# JobPilot

JobPilot is a personal job-application automation system for Gaurav. It discovers relevant AI, Backend, Full-Stack, and Mobile roles across public APIs, search engine dorks, scraped platforms, and company career pages. Discovered roles are scored for relevance against Gaurav's skills profile. If they qualify, a tailored resume is generated. The system pre-builds application payloads and pre-fills application forms, holding them in a "Ready to Apply" queue. Applying requires an explicit, manual tap from Gaurav via the Telegram bot or web dashboard; nothing is ever submitted automatically.

## Project Structure

The project is structured as a monorepo:
- `api/` - FastAPI backend handling the REST API, database access, and schema definition.
- `workers/` - Background processes for discovery, matching, resume tailoring, form filling, and contact verification.
- `bot/` - Telegram bot (`aiogram`) for application review and control.
- `web/` - Next.js 15 web dashboard.
- `docs/` - Project documentation and design specs.

## Setup Instructions

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 20+

### 1. Environment Setup
Copy the example environment file and fill in the necessary keys:
```bash
cp .env.example .env
```

Make sure to populate:
- `GEMINI_API_KEY` for embedding generation.
- `CLAUDE_API_KEY` for resume tailoring and matching.
- `ENCRYPTION_KEY` for encrypting Tier B platform credentials at rest (run `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` to generate one).

### 2. Run Database & Cache Services
Spin up PostgreSQL (with pgvector) and Redis using Docker Compose:
```bash
docker compose up -d postgres redis
```

### 3. Run Database Migrations
Run the Alembic migrations to initialize the database schema:
```bash
cd api
pip install -r requirements.txt
alembic upgrade head
```

### 4. Seed the Resume Profile
Seed the database with the initial resume profile and generate its embedding:
```bash
cd ..
python scripts/seed_resume.py
```
*(Make sure to update the email, phone, and linkedin URL fields inside the script or your environment variables first!)*
