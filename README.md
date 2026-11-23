# FinSight AI — Institutional Equity Research & Financial Intelligence Platform

[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Neon Postgres](https://img.shields.io/badge/Neon-PostgreSQL-00E599?style=for-the-badge&logo=postgresql&logoColor=black)](https://neon.tech/)
[![pgvector](https://img.shields.io/badge/pgvector-Embeddings-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Vercel](https://img.shields.io/badge/Vercel-Production-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com/)
[![Render](https://img.shields.io/badge/Render-Backend-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com/)

> **FinSight AI** is a full-stack, institutional-grade equity research terminal and automated valuation platform engineered for investment analysts, portfolio managers, and sophisticated retail investors. 
> Built on a decoupled Next.js 15 (Obsidian / Koyfin-modern theme) and FastAPI microservice architecture, it combines real-time multi-market coverage (301+ NSE & global equities), GAAP/Ind-AS 3-statement waterfalls with Wall Street accounting formatting, dynamic DCF valuation modeling, 4-pillar forensic risk intelligence, 1-click formula-driven multi-tab Excel (`.xlsx`) / PDF reporting, and grounded RAG financial research powered by Google Gemini.

---

### 🌐 Live Deployments & Endpoints

| Resource | Target URL | Status | Description |
| :--- | :--- | :---: | :--- |
| **Live Web Terminal** | [https://finsight-ai-neon.vercel.app](https://finsight-ai-neon.vercel.app) | ![Production](https://img.shields.io/badge/Status-Live-emerald?style=flat-square) | Production Next.js 15 UI hosted on Vercel Edge |
| **Production API Health** | [https://finsight-ai-0712.onrender.com/health](https://finsight-ai-0712.onrender.com/health) | ![Healthy](https://img.shields.io/badge/API-Healthy-emerald?style=flat-square) | FastAPI production health probe on Render |
| **Interactive API Docs** | [https://finsight-ai-0712.onrender.com/docs](https://finsight-ai-0712.onrender.com/docs) | ![Swagger](https://img.shields.io/badge/OpenAPI-Swagger-blue?style=flat-square) | Interactive Swagger REST specification |
| **ReDoc Specification** | [https://finsight-ai-0712.onrender.com/redoc](https://finsight-ai-0712.onrender.com/redoc) | ![ReDoc](https://img.shields.io/badge/API-ReDoc-indigo?style=flat-square) | Human-readable API documentation |

---

## 🏛️ System Architecture

FinSight AI employs a decoupled, production-hardened pipeline separating high-speed client presentation, pure financial computational engines, persistent relational & vector caching, and multi-source market ingestion:

```mermaid
flowchart TD
    subgraph Client ["Client Presentation Layer (Vercel)"]
        UI["Next.js 15 Web Application<br/>(Obsidian / Koyfin-Modern Design System)"]
        Tape["Live Market Tape Ribbon<br/>(NIFTY 50, SENSEX, S&P 500, NASDAQ, VIX)"]
        Workspaces["Institutional Workspaces<br/>(Overview, Statements, Ratios, Peers, DCF, Risk, AI Research)"]
        ExportActions["1-Click Model Exporters<br/>(Formula-Driven .xlsx & ReportLab PDF)"]
    end

    subgraph API ["High-Throughput API Engine (Render)"]
        FastAPI["FastAPI ASGI Server (Python 3.11)"]
        RateLimiter["SlowAPI Distributed Rate Limiter"]
        Routers["REST API Routers<br/>(/api/companies, /export, /ask)"]
        
        subgraph Engines ["Computational & Synthesis Engines"]
            AutoFetcher["Auto-Fetcher & Ingestion Pipeline<br/>(Schema Normalization & Ingestion)"]
            ValuationEngine["DCF & Valuation Multiples Engine<br/>(Closed-Form Math & Sensitivity)"]
            RiskEngine["4-Pillar Risk Engine<br/>(Forensic Scores & Heuristic Checks)"]
            ExcelEngine["Excel & PDF Generation Engine<br/>(openpyxl Live Formula Exporter)"]
            RAGEngine["Grounded RAG Analyst<br/>(Context Pruning & Multi-Model Fallback)"]
        end
    end

    subgraph Persistence ["Serverless Storage (Neon Cloud)"]
        NeonDB[("Neon PostgreSQL<br/>(Serverless Branch: production)")]
        PGVector["pgvector Extension<br/>(Financial Text & Ratio Embeddings)"]
        CompanyCache["301+ Pre-Seeded NSE & Global Equities Cache<br/>(Zero-Upload Instant Profiling)"]
        FinancialTables["Normalized 3-Statement & Ratio Tables<br/>(GAAP / Ind-AS Normalized Relational Schema)"]
    end

    subgraph External ["External Data & Intelligence"]
        MarketData["Market Providers<br/>(Yahoo Finance API & US SEC EDGAR)"]
        GeminiAI["Google Gemini 3.8 / 2.5 Flash<br/>(google-genai Modern SDK)"]
        DailyCron["GitHub Actions Daily Cron<br/>(Daily Market Sync & Cache Refresh)"]
    end

    UI -->|"HTTPS / JSON"| FastAPI
    Tape -->|"Quotes & Indices"| FastAPI
    FastAPI --> RateLimiter --> Routers
    Routers --> AutoFetcher & ValuationEngine & RiskEngine & ExcelEngine & RAGEngine

    AutoFetcher <-->|"Live Quotes & Statements"| MarketData
    AutoFetcher -->|"Idempotent Upsert & Cache"| NeonDB
    ValuationEngine & RiskEngine -->|"Read Historical Statements"| NeonDB
    RAGEngine <-->|"Cosine Similarity Search"| PGVector
    RAGEngine <-->|"Grounded Analytical Synthesis"| GeminiAI
    ExcelEngine -->|"Stream BytesIO (.xlsx / .pdf)"| ExportActions
    DailyCron -->|"Scheduled Sync & Warmup"| FastAPI
```

---

## ⚡ Shipped Institutional Modules

FinSight AI replicates the analytical depth and visual polish of premier institutional terminals (Bloomberg, FactSet, Koyfin) across 9 core modules:

### 1. 📈 Live Market Tape & Indices
- **Multi-Market Ticker Ribbon:** Persistent ticker tape displaying real-time quotes, point movements, and percentage changes across benchmark Indian and global indices: **NIFTY 50**, **BSE SENSEX**, **BANK NIFTY**, **S&P 500**, **NASDAQ 100**, and **CBOE Volatility Index (VIX)**.
- **Market Sentiment Gauge:** Real-time visual sentiment indicator tracking broader market breadth and volatility regimes.

### 2. ⚡ Zero-Upload Search + Dual-Format CSV Import
- **Zero-Upload Instant Profiling:** Instant coverage across **301+ pre-seeded NSE large/mid-cap equities** and global leaders. Selecting any ticker generates a full institutional research dossier within milliseconds from Neon PostgreSQL without requiring manual uploads.
- **Dual-Format CSV Ingestion:** Ingest custom financial datasets supporting both:
  - **Screener.in Standard Exports:** Multi-year Indian GAAP / Ind-AS statement formats.
  - **US SEC EDGAR & Yahoo Finance Exports:** 10-K / 10-Q multi-period statements.
- **Transaction-Safe Pre-Import Preview:** Pre-validates schema structure, flags duplicate fiscal periods, calculates line item differences, and guarantees transactional database imports with automated rollback on error.

### 3. 📑 3-Statement Waterfall + Common-Size %
- **GAAP / Ind-AS 3-Statement Waterfall:** 4-year annual historical statements (`FY2023`–`FY2026`) and 5 quarters (`Q1`–`Q5`) covering **Income Statement**, **Balance Sheet**, and **Cash Flow Statement**.
- **Wall Street Accounting Formatting:** All deductions, expenses, and cash outflows render using strict Wall Street accounting parentheses `( ... )` in subtle muted rose/slate with tabular numbers (e.g., `(₹1,228.85 Cr)` or `($12.40B)`).
- **Institutional Line-Item Completeness:**
  - *Income Statement:* Revenue, Cost of Goods Sold (COGS), Gross Profit, Operating Expenses, D&A breakdown, Operating Income (EBIT), Net Financing Income/Expenses, Other Income, EBT, Tax Expense, and Net Income.
  - *Balance Sheet:* Current vs. Non-Current Assets, Total Debt, Cash & Equivalents, Net Working Capital (NWC), Net Debt, and Invested Capital.
  - *Cash Flow:* Operating Cash Flow (CFO), Capital Expenditures (CapEx), Free Cash Flow (FCF), CFO/EBITDA %, Cash from Investing, and Cash from Financing.
- **Dynamic Common-Size %:** Instant toggle between absolute values and Common-Size percentages (% of Revenue for Income Statement, % of Total Assets for Balance Sheet).

### 4. 📊 Institutional Ratios, DuPont ROE & CAGRs
- **Comprehensive Financial Ratio Engine:**
  - *Valuation Multiples:* Trailing P/E, Forward P/E, EV/EBITDA, Price/Book (P/B), Price/Sales (P/S), and EV/FCF.
  - *Profitability & Returns:* Gross Margin, Operating Margin (OPM), Net Margin, EBITDA Margin, Return on Equity (ROE), Return on Capital Employed (ROCE), and Return on Invested Capital (ROIC).
  - *DuPont 3-Stage Decomposition:* Decomposes ROE into Net Profit Margin × Asset Turnover × Financial Leverage.
  - *Solvency & Liquidity:* Current Ratio, Quick Ratio, Debt-to-Equity, Net Debt/EBITDA, Interest Coverage, and Cash Conversion Cycle (CCC).
- **Multi-Year Historical CAGRs:** Compound Annual Growth Rates across 3-Year and 5-Year horizons for Revenue, EBIT, Net Income, EPS, and Free Cash Flow.
- **Annual vs. Quarterly Toggle:** Dedicated `Annual (4Y)` and `Quarterly (5Q)` toggle pills preventing horizontal table clipping and data crowding.

### 5. 👥 Market-Cap Sector Peers & Side-by-Side Benchmarking
- **Granular Peer Discovery:** Peers are filtered strictly within the same operating **currency** and matched by **sub-industry & sector**, ranked by **closest Market Capitalization** (`ABS(peer.market_cap - active.market_cap)`).
- **Institutional Comparative Metrics:** Side-by-side comparison grid including Market Cap, Enterprise Value (EV), P/E, EV/EBITDA, EBITDA Margin %, Operating Margin %, ROE, and Debt/Equity.
- **Live Benchmark Summaries:** Automatic `=AVERAGE(...)` and `=MEDIAN(...)` benchmark rows to identify valuation premiums or discounts against peer groups.

### 6. 🧮 Interactive DCF Valuation + 5×5 Sensitivity Matrix
- **Unlevered Free Cash Flow (UFCF) Model:** 5-to-10 year multi-stage discounted cash flow projection engine.
- **Interactive Assumption Sliders:** Real-time frontend sliders for **Revenue / FCF Growth Rate (%)**, **Weighted Average Cost of Capital (WACC %)**, **Terminal Growth Rate (%)**, and **Projection Horizon (5–10 Years)**.
- **Full Equity Bridge:** Detailed reconciliation from Present Value of Cash Flows + Terminal Value = Enterprise Value (+ Cash - Total Debt) = Implied Equity Value / Diluted Shares = **Intrinsic Value per Share**.
- **Closed-Form 5×5 Sensitivity Grid:** 25-cell WACC (rows) vs. Terminal Growth (columns) sensitivity matrix computed using closed-form financial math (zero volatile Excel arrays), highlighting current market price vs. implied valuation.

### 7. 🛡️ 4-Pillar Risk Intelligence & Forensic Quality
- **Automated Forensic Risk Engine:** Quantitative evaluation across 4 discrete risk pillars (scored 0–100):
  1. **Leverage & Liquidity:** Debt/Equity, Net Debt/EBITDA, Current Ratio, Interest Coverage.
  2. **Cash Flow Stability:** Operating Cash Flow volatility, FCF/Net Income conversion, CapEx intensity.
  3. **Valuation Stretch:** P/E and EV/EBITDA multiples relative to historical 5-year averages and sector peers.
  4. **Earnings Quality:** Accruals Ratio, Cash Flow to EBITDA alignment, and heuristic indicators derived from the Beneish M-Score and Altman Z-Score.
- **Composite Institutional Rating:** Categorizes companies into **Low Risk (Green)**, **Moderate Risk (Amber)**, **Elevated Risk (Orange)**, or **High Risk (Rose)** with automated AI-assisted qualitative risk watchpoints.

### 8. 📥 1-Click Institutional Excel (`.xlsx`) & PDF Research Reports
- **Multi-Tab Live Formula Excel Workbook (`openpyxl`):**
  - **Tab 1: Executive Summary:** Company profile, cross-sheet formula-linked valuation summary from Tab 4, risk scorecard, and research disclaimers.
  - **Tab 2: 3-Statement Financials:** 4-year historical statements with dynamic Excel formulas for Gross Profit, EBITDA, EBIT, EBT, Net Income, Net Debt, NWC, Invested Capital, and FCF.
  - **Tab 3: Ratios & Peers:** Cross-sheet formula-linked historical ratios, multi-year averages, medians, and sector peer tables with `=AVERAGE(...)` and `=MEDIAN(...)` formulas.
  - **Tab 4: DCF Valuation:** Editable blue-font assumptions block (`#0000FF`), formula-driven 5–10Y projection schedule, equity bridge, and a formula-driven 5×5 `=NPV(...)` sensitivity matrix.
  - **Wall Street Styling Standards:** Obsidian headers (`#0F172A`), accounting format `_(* #,##0.00_);_(* (#,##0.00);_(* "-"??_);_(@_)`, auto-fitting column widths, frozen panes, and formula-injection defenses.
- **Publication-Grade PDF Tear Sheet (`ReportLab`):** Vector-rendered analyst research report featuring executive summary, financial tables, risk breakdown, and valuation targets.

### 9. 🤖 Grounded RAG AI Research Analyst
- **Context-Enriched Retrieval:** Connects to **Google Gemini** (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-flash-latest`) via the official modern `google-genai` SDK.
- **Strict Grounding Context:** Injects live Cash Flow (OCF, CapEx, FCF), Balance Sheet (Total Debt, Net Debt, Cash, Current Ratio), and 4-Pillar Risk scores directly into the model prompt, pruning empty/null periods to eliminate hallucinations.
- **Resilient Multi-Model Fallback:** Multi-tier fallback architecture that gracefully transitions between frontier and flash models during rate limits, backed by a deterministic template engine.
- **Dark-Theme Markdown Rendering:** Formatted chat workspace rendering headings, bold financial metrics, bulleted evidence points, and interactive quick-prompt analyst chips (*"Is cash generation healthy?"*, *"Summarize key financial risks"*, *"Explain valuation vs peers"*).

---

## 🛠️ Tech Stack & Libraries

| Domain | Technology / Library | Purpose |
| :--- | :--- | :--- |
| **Frontend Framework** | **Next.js 15 (App Router)** | High-performance server-rendered and client-hydrated web UI |
| **UI & Styling** | **Tailwind CSS + Lucide Icons** | Institutional Obsidian/Koyfin dark-theme fintech terminal |
| **Markdown Typography** | **react-markdown** | Clean dark-theme prose and financial AI chat rendering |
| **Backend Microservice**| **FastAPI 0.115 (ASGI)** | High-throughput asynchronous Python web framework |
| **Database & Pooling** | **Neon PostgreSQL (Serverless)**| Cloud Postgres with scale-to-zero compute and connection pooling |
| **Vector Search** | **pgvector** | High-dimensional financial document and statement embeddings |
| **ORM & Migrations** | **SQLAlchemy 2.0 + Alembic** | Type-safe database queries and automated schema migrations |
| **Database Driver** | **Psycopg 3 (`postgresql+psycopg`)**| Asynchronous, high-performance PostgreSQL driver |
| **Excel Generation** | **openpyxl 3.1.5** | Native multi-tab Excel models with live formulas and IB styling |
| **PDF Generation** | **ReportLab** | High-resolution PDF tear sheets and institutional reports |
| **AI & Inference** | **Google Gemini (google-genai)** | Grounded RAG synthesis, financial Q&A, and risk intelligence |
| **Market Ingestion** | **Yahoo Finance API + SEC EDGAR** | Multi-market quote streaming and 10-K statement ingestion |
| **Rate Limiting** | **SlowAPI** | Endpoint-level distributed throttling protection |
| **Testing** | **pytest + pytest-anyio** | Unit, integration, formula validation, and API test suites |

---

## ⚙️ Local Development Setup

Follow these steps to run FinSight AI locally on your development machine.

### Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** 18.x or 20.x+ (with `npm`)
- **Git**
- **Neon PostgreSQL Account:** (Free tier supported at [neon.tech](https://neon.tech)) or a local PostgreSQL 15+ database with `pgvector`.

---

### 1. Clone the Repository
```bash
git clone https://github.com/rohitkumardhawan/finsight-ai.git
cd finsight-ai
```

---

### 2. Configure Environment Variables
FinSight AI uses an environment variable pattern that strictly protects credentials. Copy `.env.example` to `.env`:

```bash
# Windows (PowerShell or Command Prompt)
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

#### `.env.example` Reference Guide (Zero Secrets)
| Variable | Description | Default / Example Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | Pooled Neon PostgreSQL connection URL | `postgresql://user:password@ep-pooler.aws.neon.tech/neondb?sslmode=require` |
| `DATABASE_URL_UNPOOLED` | Direct (unpooled) Neon PostgreSQL connection URL | `postgresql://user:password@ep-direct.aws.neon.tech/neondb?sslmode=require` |
| `NEON_BRANCH` | Active Neon Git-style branch | `production` |
| `BACKEND_PORT` | Port for the FastAPI ASGI server | `8000` |
| `ENVIRONMENT` | Operational environment flag | `development` / `production` |
| `NEXT_PUBLIC_API_URL` | Public API endpoint for frontend requests | `http://localhost:8000/api` |
| `NEXT_PUBLIC_BACKEND_URL` | Base backend URL for assets/health probes | `http://localhost:8000` |
| `FRONTEND_ORIGIN` | Allowed CORS origin for backend API | `http://localhost:3000` |
| `ADMIN_API_KEY` | Header key for admin/refresh operations | `dev_admin_secret_key_change_in_production` |
| `GEMINI_API_KEY` | Google AI Studio Gemini API Key | `AIzaSy...` (Get from [aistudio.google.com](https://aistudio.google.com)) |
| `SEC_USER_AGENT` | User agent header for SEC EDGAR requests | `FinSightAI research@finsight.local` |
| `SENTRY_DSN` | *(Optional)* Sentry monitoring DSN | *Leave blank for local dev* |

---

### 3. Backend Setup (FastAPI & Python 3.11)

1. **Navigate to the backend directory and create a virtual environment:**
   ```bash
   cd backend
   python -m venv venv
   ```

2. **Activate the virtual environment:**
   - **Windows:**
     ```powershell
     .\venv\Scripts\Activate.ps1
     # Or in Command Prompt:
     venv\Scripts\activate.bat
     ```
   - **macOS / Linux:**
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Apply Database Migrations (Alembic):**
   ```bash
   alembic upgrade head
   ```

5. **Start the FastAPI Backend Server:**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   - API Root: [http://localhost:8000](http://localhost:8000)
   - Swagger Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
   - Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### 4. Frontend Setup (Next.js 15)

1. **Open a new terminal window, navigate to `frontend/`, and install packages:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure Frontend Environment:**
   Create `frontend/.env.local` (or copy from `.env.local.example`):
   ```ini
   NEXT_PUBLIC_API_URL=http://localhost:8000/api
   NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
   ```

3. **Start the Next.js Development Server:**
   ```bash
   npm run dev
   ```
   - Web Terminal Cockpit: [http://localhost:3000](http://localhost:3000)

---

## 🧪 Testing & Verification

FinSight AI maintains rigorous automated test suites across both backend calculations and frontend builds.

### Backend Automated Tests (`pytest`)
Run the test suite verifying mathematical integrity, DCF calculations, closed-form sensitivity matrices, Excel model generation, and injection defenses:

```bash
# Navigate to backend directory
cd backend

# Run the test suite with verbose output
python -m pytest tests/ -v
```

*Key Test Suites:*
- `tests/test_excel_export.py` — Validates formula-driven 4-tab workbook generation, formula injection defenses, and custom DCF parameter overrides.
- `tests/test_live_discrepancies_fix.py` — Validates sector peer discovery, market-cap sorting, DuPont decomposition, and 3-statement line items.
- `tests/test_financial.py` — Validates DCF valuation math, zero-division safeguards, and margin formulas.
- `tests/test_database.py` — Verifies Neon PostgreSQL connection health, CRUD lifecycle, and conflict handling.

### Frontend Production Build Verification
Ensure all TypeScript types, React 19 hooks, and Next.js 15 route segments compile cleanly:

```bash
# Navigate to frontend directory
cd frontend

# Run production build
npm run build
```

Expected output:
```text
✓ Compiled successfully
✓ Generating static pages (5/5)
✓ Finalizing page optimization
Exit code: 0
```

---

## 🔒 Security & Financial Integrity Principles

1. **Formula Injection Sanitization:** All text inputs exported into Excel workbooks are scrubbed through a strict sanitization barrier to prevent spreadsheet formula execution vulnerabilities (`=`, `+`, `-`, `@`).
2. **Missing Data Integrity:** Missing financial data points are never converted into misleading `0.0` values; they evaluate strictly to `None` / `—` to preserve analytic fidelity.
3. **Deterministic Math:** Valuation models, ratios, and sensitivity calculations execute deterministically in pure Python without reliance on non-deterministic LLM arithmetic.
4. **Zero Client Secrets:** Database URLs, pooler keys, and AI credentials are strictly confined to server-side environments and never leaked to the client bundle.

---

## 📄 License

This project is licensed under the **ISC License** — see [package.json](package.json) for details.

---

<div align="center">
  <sub>Engineered with precision for institutional finance. Powered by <b>Next.js 15</b>, <b>FastAPI</b>, <b>Neon PostgreSQL</b>, and <b>Google Gemini</b>.</sub>
</div>
