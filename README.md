# FinSight AI — Institutional Equity Research & Financial Intelligence

> **AI-Powered Equity Research & Financial Intelligence Platform**  
> Premium institutional financial analytics, valuation modeling, CSV data ingestion, and relational database persistence.

---

## 🏛️ System Architecture (Phase 3: Financial Statements & Ratio Engine)

FinSight AI is built using a decoupled, production-grade architecture combining Next.js 15, FastAPI, and Neon Serverless PostgreSQL:

```
                           ┌───────────────────────────────────────────────┐
                           │          Next.js 15 Frontend (App)            │
                           │  TypeScript + Tailwind CSS + Lucide Icons     │
                           │  • Dark Navy & Gold Institutional Theme       │
                           │  • Financial Statements Module (IS, BS, CF)   │
                           │  • Interactive CSV Import Modal + Preview     │
                           │  • Financial Ratio Engine & Multi-Year Trends │
                           │  • Live Neon Database Status & Search         │
                           └──────────────────────┬────────────────────────┘
                                                  │ HTTP / JSON API (Port 8000)
                                                  ▼
                           ┌───────────────────────────────────────────────┐
                           │            FastAPI Python Backend             │
                           │  • ASGI High-Throughput Engine (Port 8000)    │
                           │  • Pydantic Schemas & Data Sanitization       │
                           │  • CSV Parser, Preview & Transaction Importer │
                           │  • OpenAPI Specification (/docs & /redoc)     │
                           └───────┬──────────────┬──────────────┬─────────┘
                                   │              │              │
                    ┌──────────────▼────┐  ┌──────▼──────┐  ┌────▼─────────────┐
                    │ Financial Engine  │  │ AI Services │  │ SQLAlchemy 2.x   │
                    │ Pure Math (DCF,   │  │ (Dormant    │  │ • Connection Pool│
                    │ Ratios, Margins)  │  │  until      │  │ • Alembic Migrat.│
                    │ app/financial/    │  │  Phase 4)   │  │ • Psycopg 3      │
                    └───────────────────┘  └─────────────┘  └────┬─────────────┘
                                                                 │
                                                                 ▼
                                                  ┌────────────────────────────┐
                                                  │   Neon PostgreSQL (Cloud)  │
                                                  │   • Branch: production     │
                                                  │   • Scale-to-Zero Pooling  │
                                                  │   • Relational Persistence │
                                                  │   • Rev: 6722bd0e29f9      │
                                                  └────────────────────────────┘
```

### 🛡️ Core Architectural Principles
1. **Separation of Concerns:** Financial calculations (`app/financial/metrics.py`) are strictly separated from web routing, database models, and external services.
2. **Demonstration Data Transparency:** All demonstration records are stored with `is_demo_data = true` and `source = "DEMO DATASET"`, visibly flagged in the dashboard.
3. **Missing Data Integrity:** Missing financial figures are never silently converted to `0.0`. They explicitly evaluate to `None` / `N/A`.
4. **Zero Secrets in Frontend:** Database credentials and API keys are strictly server-side, read from `.env`, and never exposed to the client.
5. **Non-Destructive Migrations:** Existing database tables (including legacy tables like `demo_equity_coverage`) are preserved and protected from dropping.

---

## 📁 Project Directory Structure

```text
ilovepdf_pages-to-jpg/
├── .env                              # Master secrets (Git-ignored)
├── .env.example                      # Safe template with placeholder values
├── .gitignore                        # Git ignore rules protecting all secrets
├── package.json                      # Workspace scripts
├── README.md                         # Platform documentation
│
├── frontend/                         # Next.js TypeScript Frontend
│   ├── .env.local                    # Local Next.js environment
│   ├── package.json                  # Frontend dependencies
│   ├── tailwind.config.ts            # Dark navy & institutional gold styling
│   └── src/
│       ├── app/
│       │   ├── api/
│       │   │   ├── companies-db/     # Direct DB search route
│       │   │   └── neon-health/      # Live Neon DB ping & latency route
│       │   ├── globals.css           # Institutional color palette & typography
│       │   ├── layout.tsx            # Root HTML layout & fonts
│       │   └── page.tsx              # Main Institutional Dashboard
│       ├── components/               # Reusable UI Components
│       │   ├── Sidebar.tsx           # 8 Navigation modules + mobile drawer
│       │   ├── Header.tsx            # Search bar, ticker select, live DB status
│       │   ├── KpiCard.tsx           # Metric cards with demo labels & N/A protection
│       │   ├── ChartRevenue.tsx      # Multi-year revenue trajectory chart
│       │   ├── ChartProfitability.tsx# LTM Operating & Net Margin chart
│       │   ├── RecentResearch.tsx    # Analyst research & sentiment briefs
│       │   ├── QuickActions.tsx      # Fast shortcuts to DCF & AI tools
│       │   └── ModulePlaceholder.tsx # Institutional placeholders for modules 2-8
│       └── lib/
│           └── db.ts                 # Safe @neondatabase/serverless helper
│
└── backend/                          # FastAPI Python Backend
    ├── .env                          # Backend secrets (Git-ignored)
    ├── alembic.ini                   # Alembic migration configuration
    ├── requirements.txt              # Python dependencies
    ├── alembic/                      # Database Schema Migrations
    │   ├── env.py                    # Alembic migration runner
    │   └── versions/                 # Versioned migration scripts
    │       └── 6ce003bdab84_create_initial_schema.py
    └── app/
        ├── main.py                   # FastAPI application root & CORS
        ├── api/
        │   ├── endpoints/            # Phase 2 Database REST Endpoints
        │   │   ├── health.py         # /api/health and /api/db/health
        │   │   └── companies.py      # Companies, Statements, Ratios CRUD
        │   └── v1/
        │       ├── endpoints/        # Phase 1 demonstration endpoints
        │       └── router.py         # v1 router aggregator
        ├── core/
        │   └── config.py             # Settings & Psycopg 3 connection URL builder
        ├── db/
        │   ├── base.py               # DeclarativeBase class
        │   ├── session.py            # SQLAlchemy engine, SessionLocal, get_db()
        │   └── seed.py               # Idempotent database demonstration seeder
        ├── financial/
        │   └── metrics.py            # DCF, Gross/Operating/Net margins, ratios
        ├── models/                   # SQLAlchemy ORM Database Models
        │   ├── company.py            # 'companies' table schema
        │   ├── financial_statement.py# 'financial_statements' table schema
        │   ├── financial_ratio.py    # 'financial_ratios' table schema
        │   ├── research_record.py    # 'research_records' table schema
        │   └── uploaded_document.py  # 'uploaded_documents' metadata schema
        ├── schemas/                  # Pydantic validation schemas
        │   ├── company.py            # Request/Response schemas for Company
        │   ├── financial.py          # Dashboard presentation schemas
        │   ├── ratio.py              # Request/Response schemas for Ratios
        │   └── statement.py          # Request/Response schemas for Statements
        ├── services/
        │   └── ai_service.py         # AI service placeholder (dormant until Phase 3)
        └── tests/                    # Automated Test Suite (pytest)
            ├── test_api.py           # Endpoint tests & demo labeling
            ├── test_database.py      # Live DB health, CRUD, conflict tests
            └── test_financial.py     # Math integrity & zero-division safeguards
```

---

## 🗄️ Database Schema (Neon PostgreSQL)

### 1. `companies`
- `id` (PK, Integer, Auto-increment)
- `ticker` (String(20), Unique, Indexed)
- `company_name` (String(255), Not Null)
- `exchange` (String(50), Nullable)
- `sector` (String(100), Nullable)
- `industry` (String(150), Nullable)
- `country` (String(100), Nullable)
- `currency` (String(10), Default 'USD')
- `created_at` / `updated_at` (Timestamps with Timezone)

### 2. `financial_statements`
- `id` (PK, Integer, Auto-increment)
- `company_id` (FK -> companies.id ON DELETE CASCADE)
- `fiscal_year` (Integer, Indexed)
- `fiscal_period` (String(10), Indexed: 'FY', 'Q1', 'Q2', 'Q3', 'Q4')
- `statement_type` (String(50), Not Null)
- Financial Line Items (Numeric(18,2), Nullable):
  `revenue`, `cost_of_revenue`, `gross_profit`, `operating_income`, `ebit`, `net_income`, `total_assets`, `current_assets`, `total_liabilities`, `current_liabilities`, `total_equity`, `cash_and_equivalents`, `inventory`, `total_debt`, `operating_cash_flow`, `capital_expenditure`, `free_cash_flow`, `depreciation_amortization`
- `source` (String(100), Default 'SEC EDGAR')
- `is_demo_data` (Boolean, Default True)
- `created_at` (Timestamp with Timezone)

### 3. `financial_ratios`
- `id` (PK, Integer, Auto-increment)
- `company_id` (FK -> companies.id ON DELETE CASCADE)
- `fiscal_year` / `fiscal_period` (Indexed)
- Ratio Line Items (Numeric(10,4), Nullable):
  `gross_margin`, `operating_margin`, `net_profit_margin`, `current_ratio`, `quick_ratio`, `debt_to_equity`, `return_on_equity`, `return_on_assets`
- `source` (String(100))
- `created_at` (Timestamp with Timezone)

### 4. `research_records`
- `id` (PK, Integer, Auto-increment)
- `company_id` (FK -> companies.id ON DELETE CASCADE)
- `research_title` (String(255), Not Null)
- `research_type` (String(50), Not Null)
- `research_content` (Text, Not Null)
- `source` (String(100))
- `created_at` (Timestamp with Timezone)

### 5. `uploaded_documents`
- `id` (PK, Integer, Auto-increment)
- `company_id` (FK -> companies.id ON DELETE CASCADE)
- `filename` (String(255), Not Null)
- `document_type` (String(50), Not Null)
- `storage_reference` (String(500), Not Null)
- `processing_status` (String(50), Default 'pending')
- `uploaded_at` (Timestamp with Timezone)

---

## ⚡ Quick Start Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+
- Neon PostgreSQL Account (or local PostgreSQL)

### 1. Environment Configuration
Copy the template to your `.env` file:
```powershell
cp .env.example .env
```
Populate `.env` with your Neon credentials:
```ini
DATABASE_URL="postgresql://<user>:<password>@<neon-pooler-host>/neondb?sslmode=require"
DATABASE_URL_UNPOOLED="postgresql://<user>:<password>@<neon-direct-host>/neondb?sslmode=require"
NEON_BRANCH=production
BACKEND_PORT=8000
ENVIRONMENT=development
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 2. Database Migrations (Alembic)
Apply migrations to your Neon database:
```powershell
cd backend
.\venv\Scripts\python.exe -m alembic upgrade head
```

To create a new migration in the future:
```powershell
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe_changes"
.\venv\Scripts\python.exe -m alembic upgrade head
```

To roll back a migration:
```powershell
.\venv\Scripts\python.exe -m alembic downgrade -1
```

### 3. Seed Demonstration Data
Populate institutional sample data for AAPL, NVDA, MSFT, GOOGL, AMZN, and TSLA:
```powershell
cd backend
.\venv\Scripts\python.exe -m app.db.seed
```
*The seed script is idempotent and safe to run multiple times without duplicating data.*

### 4. Start the Backend (FastAPI)
```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Alternative Docs (ReDoc): [http://localhost:8000/redoc](http://localhost:8000/redoc)
- System Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- Neon Database Health Check: [http://localhost:8000/api/db/health](http://localhost:8000/api/db/health)

### 5. Start the Frontend (Next.js)
```powershell
cd frontend
npm run dev
```
- Dashboard Cockpit: [http://localhost:3000](http://localhost:3000)

---

## 📡 REST API Reference

| Method | Endpoint | Description | Status Codes |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System health probe | `200` |
| `GET` | `/api/db/health` | Live Neon PostgreSQL connection check & round-trip latency | `200`, `503` |
| `GET` | `/api/companies` | List all companies (supports pagination `skip`, `limit`, and query `q`) | `200` |
| `POST` | `/api/companies` | Create a new company record (unique ticker enforced) | `201`, `409` |
| `GET` | `/api/companies/{id}` | Retrieve company by ID | `200`, `404` |
| `GET` | `/api/companies/ticker/{ticker}` | Retrieve company by ticker symbol | `200`, `404` |
| `PUT` | `/api/companies/{id}` | Update company metadata | `200`, `404` |
| `DELETE` | `/api/companies/{id}` | Delete company and cascade related records | `204`, `404` |
| `GET` | `/api/companies/{id}/statements` | Retrieve historical financial statements (filters: `year`, `period`, `statement_type`) | `200`, `404` |
| `POST` | `/api/companies/{id}/statements` | Create a financial statement record (auto-recalculates ratios) | `201`, `404` |
| `PUT` | `/api/statements/{id}` | Update a specific financial statement (auto-recalculates ratios) | `200`, `404` |
| `DELETE` | `/api/statements/{id}` | Delete a specific financial statement | `204`, `404` |
| `GET` | `/api/statements/csv-template` | Download standardized CSV template (`combined`, `income_statement`, etc.) | `200` |
| `POST` | `/api/companies/{id}/statements/csv-preview` | Parse & validate CSV, flag duplicates, check schema before DB write | `200`, `400`, `404` |
| `POST` | `/api/companies/{id}/statements/csv-import` | Transaction-safe DB import with rollback & deterministic ratio recalculation | `200`, `400`, `500` |
| `GET` | `/api/companies/{id}/ratios` | Retrieve calculated financial ratios | `200`, `404` |
| `POST` | `/api/companies/{id}/ratios` | Upsert a financial ratio record | `201`, `404` |
| `POST` | `/api/companies/{id}/ratios/recalculate` | Re-compute all ratios deterministically in pure Python from statements | `200`, `404` |
| `GET` | `/api/companies/{id}/financial-trends` | Multi-year historical trends & margins for time-series charts | `200`, `404` |

---

## 🧪 Automated Testing

Run the full automated test suite verifying database connectivity, CRUD lifecycle, conflict validation, financial calculation safeguards, and demo data labeling:
```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests -v
```

### Test Coverage Highlights:
- `test_database.py::test_system_and_db_health` — Live Neon round-trip ping.
- `test_database.py::test_list_companies_and_search` — Company listing and keyword filtering.
- `test_database.py::test_company_crud_lifecycle` — Full lifecycle (Create, Duplicate Conflict 409, Read, Update, Statements, Ratios, Delete, 404 verification).
- `test_financial.py` — DCF valuation, gross margin, operating margin, zero-division protection.
- `test_api.py` — Demonstration data transparency badges and legacy v1 endpoints.

---

## 🔧 Common Troubleshooting Steps

1. **PowerShell Script Execution Policy Error:**
   - *Problem:* `neon : File ... cannot be loaded because running scripts is disabled on this system.`
   - *Solution:* Always run batch scripts directly on Windows: `neon.cmd` and `npm.cmd`.

2. **Psycopg 3 URL Formatting:**
   - *Problem:* SQLAlchemy does not recognize `postgresql://` for Psycopg 3.
   - *Solution:* FinSight AI automatically maps connection URLs to `postgresql+psycopg://` in `backend/app/core/config.py`.

3. **Neon Compute Scale-to-Zero Latency:**
   - *Problem:* First request after inactivity takes 1–3 seconds while Neon wakes up the compute node.
   - *Solution:* Connection pooling with `pool_pre_ping=True` and `pool_recycle=300` automatically handles serverless wakeups safely.

4. **Quotation Marks in Connection URLs:**
   - *Problem:* `.env` files wrapped in double quotes can break connection parsers.
   - *Solution:* `config.py` and `db.ts` strip surrounding quotation marks automatically before passing to drivers.
