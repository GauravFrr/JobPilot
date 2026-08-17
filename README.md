# 🚀 JobPilot — Job Application Automation System

JobPilot is a personal job-application automation system designed to discover, score, match, and tailor resumes for AI, Backend, Full-Stack, and Mobile engineering roles. 

By scraping public APIs, company career pages, and hiring platforms, JobPilot identifies potential target jobs, screens them using vector embeddings against your active profile, tailors your experience highlights using LLMs, and prepares application drafts (form screenshots, payloads) for review. 

> [!IMPORTANT]
> **No Auto-Submit Rule**: JobPilot will **never** automatically submit an application. All tailored matches are held in a "Ready to Apply" queue, requiring a manual, single-tap confirmation via the Telegram bot or Next.js Web Dashboard.

---

## 🗺️ System Architecture

```mermaid
graph TD
    subgraph Data Sources
        T1["Tier A: Public APIs (RemoteOK, WWR, Remotive) & Serper Dorks"]
        T2["Tier B: Playwright scrapers (LinkedIn, Naukri, Wellfound, Instahyre)"]
        T3["Tier C: Playwright ATS crawler (Company Career Pages & Greenhouse/Lever/Ashby detection)"]
    end
    
    subgraph Background Workers (Scheduler Container)
        S["APScheduler Loop"] --> Crawler["Discovery Pipelines"]
        Crawler --> Deduplicator["Deduplication Engine"]
        Deduplicator --> PG[("PostgreSQL + pgvector")]
        PG --> Matcher["gemini-embedding-2 Cosine Score + Claude Reranker"]
        Matcher --> Tailorer["Claude resume bullet tailoring & PDF Renderer"]
        Tailorer --> Prebuilder["Playwright Form Pre-filler & Screenshot Grabber"]
    end
    
    subgraph Control Interfaces
        Bot["Telegram Bot (aiogram)"]
        Web["Next.js Web Dashboard"]
        API["FastAPI Gateway Router"]
    end
    
    API --> PG
    Bot --> API
    Web --> API
```

---

## 📂 Project Structure

```text
jobpilot/
├── api/                                # FastAPI backend gateway
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                     # App bootstrap & CORS config
│   │   ├── config.py                   # Environment variable mappings
│   │   ├── db.py                       # SQLAlchemy session & pgvector engine
│   │   ├── models/                     # SQLAlchemy DB schemas
│   │   ├── routes/                     # REST routers (jobs, settings, stats)
│   │   └── schemas/                    # Pydantic validation schemas
│   └── tests/                          # API unit & integration tests
│
├── workers/                            # Background processing tasks
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── scheduler.py                    # APScheduler daemon runner
│   ├── discovery/                      # Discovery adapters (Tiers A, B, C)
│   ├── matching/                       # Similarity scoring & LLM reranking
│   ├── tailoring/                      # Resume bullet rewriting & PDF compilation
│   ├── applying/                       # Playwright form-filling and screenshot hooks
│   └── contacts/                       # Recruiter contact & weekly metrics generation
│
├── bot/                                # Telegram bot interface (aiogram)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                         # Command handlers & Alert listener
│
├── web/                                # Frontend dashboard (Next.js 14 standalone)
│   ├── Dockerfile
│   ├── next.config.js                  # Routing proxy configuration
│   └── src/                            # Tailwind & SWR data-fetch pages
│
├── scripts/                            # DB seeding, backups, and helpers
└── storage_state/                      # Git-ignored local DB backups & files
```

---

## 🛠️ Setup & Local Installation

### Prerequisites
* **Docker & Docker Compose** (Desktop or CLI)
* **Python 3.11+** (for local scripts/tests)
* **Node.js 20+**

### 1. Environment Variable Setup
Copy the example environment file:
```powershell
cp .env.example .env
```

Open `.env` and fill in the required keys:
* `DATABASE_URL`: PostgreSQL database link (e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/jobpilot`).
* `GEMINI_API_KEY`: Required for generating 768-dimensional job vector embeddings (`gemini-embedding-2`).
* `CLAUDE_API_KEY`: API key or custom endpoint URL supporting LLM reranking and visual resume tailoring.
* `ENCRYPTION_KEY`: Used to encrypt your Tier B platform credentials at rest. Generate one using:
  ```powershell
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
* `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: Pair the Telegram bot with your account.
* `GOOGLE_SEARCH_API_KEY` & `GOOGLE_SEARCH_CX`: Required for Serper/Google Dork searches (Tier A+).

---

### 2. Run Database & Cache Services
Spin up the database (equipped with the `pgvector` extension) and cache:
```powershell
docker compose up -d postgres redis
```

---

### 3. Run Database Migrations
Run the Alembic migrations to construct the SQL schemas:
```powershell
cd api
pip install -r requirements.txt
alembic upgrade head
cd ..
```

---

### 4. Seed Profile & Target Companies
Seeding is critical to boot the discovery scheduler and scoring filters.

1. **Seed Resume Profile**:
   Edit `scripts/seed_resume.py` with your personal contact info, career highlights, and skills, then execute:
   ```powershell
   python scripts/seed_resume.py
   ```
2. **Seed Target Companies**:
   Seed targets for the company career page crawler (Tier C):
   ```powershell
   python scripts/seed_target_companies.py
   ```

---

### 5. Launch the JobPilot Stack
Run Docker Compose to build and start the API, Next.js frontend, Telegram bot, and background scheduler containers:
```powershell
docker compose up -d --build
```

Access the systems:
* **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
* **API Endpoints Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ⚙️ Core Modules & Scripts

### Self-Healing Scheduler Queue
The background scheduler (`jobpilot-workers-1`) runs every 2 hours and automatically processes jobs in a transactional queue:
1. **Scrapes new roles** from discovery adapters (APIs, search dorks, career pages).
2. **Scores `"discovered"` jobs**: Runs similarity matching against your profile embedding. Stuck or rate-limited items automatically remain in `"discovered"` status and are re-evaluated during the next run.
3. **Tailors `"matched"` jobs**: Automatically rewrites experience bullets using your active template profile.
4. **Pre-builds `"tailored"` payloads**: For Tier B jobs, Playwright launches a browser session, pre-fills the form fields, grabs a screenshot, and moves the status to `"ready_to_apply"`.

### Database Backups
A nightly cron backup runs automatically and generates rotated SQL dump files inside `storage_state/backups/`. To manually backup your database immediately:
```powershell
./scripts/backup_db.sh
```

### Visual Resume Editor
Modify your primary skills, experience bullets, and custom project highlights directly in the web dashboard at `http://localhost:3000/settings`. Changes are synced and hot-reloaded into the tailoring workers instantly.
