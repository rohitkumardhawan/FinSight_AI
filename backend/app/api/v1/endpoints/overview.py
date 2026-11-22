from fastapi import APIRouter, HTTPException
from app.schemas.financial import DashboardData, CompanyOverview, MetricCard, ChartDataPoint, ResearchNote
from app.financial.metrics import calculate_gross_margin, calculate_net_margin

router = APIRouter()

# Structured Institutional Demonstration Dataset
DEMO_DATABASE = {
    "AAPL": {
        "company": CompanyOverview(
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics & Services",
            price=232.50,
            change_percent=1.45,
            market_cap="$3.54 Trillion",
            pe_ratio=33.8,
            ev_ebitda=24.6,
            fcf_yield="3.8%",
            roe="147.2%",
            summary="[DEMO DATA] Leading consumer electronics, services, and ecosystem provider with recurring high-margin services expansion.",
            is_demo_data=True
        ),
        "kpis": [
            MetricCard(label="Market Capitalization", value="$3.54T", change="+12.4% YoY", is_positive=True, subtext="Class A Common Stock"),
            MetricCard(label="Enterprise Value / EBITDA", value="24.6x", change="-1.2x QoQ", is_positive=True, subtext="LTM Institutional Multiple"),
            MetricCard(label="Trailing P/E Ratio", value="33.8x", change="+2.1x vs Peer Median", is_positive=False, subtext="Premium Sector Multiple"),
            MetricCard(label="Free Cash Flow Yield", value="3.82%", change="+45 bps QoQ", is_positive=True, subtext="LTM FCF: $108.8B"),
        ],
        "revenue_trend": [
            ChartDataPoint(period="FY21", revenue=365.8, gross_profit=152.8, net_income=94.7),
            ChartDataPoint(period="FY22", revenue=394.3, gross_profit=170.8, net_income=99.8),
            ChartDataPoint(period="FY23", revenue=383.3, gross_profit=169.1, net_income=97.0),
            ChartDataPoint(period="FY24", revenue=391.0, gross_profit=180.7, net_income=101.2),
            ChartDataPoint(period="FY25E", revenue=418.5, gross_profit=197.5, net_income=111.4),
        ],
        "recent_research": [
            ResearchNote(
                id="RN-001",
                title="Services Supercycle & Margin Accretion",
                ticker="AAPL",
                analyst="FinSight Institutional Equities",
                date="Nov 2026",
                sentiment="Bullish",
                target_price="$260.00",
                summary="Services division accounts for over 25% of gross revenues with 74% gross margin profile."
            ),
            ResearchNote(
                id="RN-002",
                title="Hardware Replacement Cycle Momentum",
                ticker="AAPL",
                analyst="Global Tech Research",
                date="Nov 2026",
                sentiment="Neutral",
                target_price="$245.00",
                summary="AI silicon capabilities driving replacement intent across institutional and consumer cohorts."
            )
        ]
    },
    "NVDA": {
        "company": CompanyOverview(
            ticker="NVDA",
            name="NVIDIA Corporation",
            sector="Technology",
            industry="Semiconductors & Accelerated Compute",
            price=142.10,
            change_percent=3.20,
            market_cap="$3.48 Trillion",
            pe_ratio=42.1,
            ev_ebitda=31.2,
            fcf_yield="2.9%",
            roe="115.4%",
            summary="[DEMO DATA] Dominant accelerated computing platform powering global hyperscale AI infrastructure and enterprise inference.",
            is_demo_data=True
        ),
        "kpis": [
            MetricCard(label="Market Capitalization", value="$3.48T", change="+88.2% YoY", is_positive=True, subtext="Hyperscaler Market Leader"),
            MetricCard(label="Enterprise Value / EBITDA", value="31.2x", change="-4.5x QoQ", is_positive=True, subtext="Accelerated Growth Multiple"),
            MetricCard(label="Trailing P/E Ratio", value="42.1x", change="-15.4x YoY", is_positive=True, subtext="Earnings Expansion Compression"),
            MetricCard(label="Free Cash Flow Yield", value="2.90%", change="+90 bps QoQ", is_positive=True, subtext="LTM FCF: $61.2B"),
        ],
        "revenue_trend": [
            ChartDataPoint(period="FY22", revenue=26.9, gross_profit=17.5, net_income=9.8),
            ChartDataPoint(period="FY23", revenue=27.0, gross_profit=15.4, net_income=4.4),
            ChartDataPoint(period="FY24", revenue=60.9, gross_profit=44.3, net_income=29.8),
            ChartDataPoint(period="FY25", revenue=120.4, gross_profit=90.2, net_income=65.1),
            ChartDataPoint(period="FY26E", revenue=165.0, gross_profit=124.0, net_income=92.0),
        ],
        "recent_research": [
            ResearchNote(
                id="RN-003",
                title="Blackwell Architecture Hyperscale Demand",
                ticker="NVDA",
                analyst="Semiconductor Strategy Desk",
                date="Nov 2026",
                sentiment="Bullish",
                target_price="$165.00",
                summary="Hyperscale CapEx budgets remain elevated with high visibility into compute cluster buildouts."
            )
        ]
    }
}

@router.get("/overview/{ticker}", response_model=DashboardData)
async def get_overview(ticker: str):
    ticker_upper = ticker.upper()
    data = DEMO_DATABASE.get(ticker_upper)
    
    if not data:
        # Fallback dynamic generator with clear demo labeling
        return DashboardData(
            company=CompanyOverview(
                ticker=ticker_upper,
                name=f"{ticker_upper} Corporation",
                sector="Diversified Equities",
                industry="Financial Intelligence Demonstration",
                price=185.00,
                change_percent=0.75,
                market_cap="$1.20 Trillion",
                pe_ratio=26.5,
                ev_ebitda=18.4,
                fcf_yield="4.1%",
                roe="28.4%",
                summary=f"[DEMO DATA] Synthesized financial model overview for {ticker_upper}. Real-time financial feeds connect in Phase 2.",
                is_demo_data=True
            ),
            kpis=[
                MetricCard(label="Market Capitalization", value="$1.20T", change="+4.2% YoY", is_positive=True, subtext="Synthesized Equity Valuation"),
                MetricCard(label="EV / EBITDA", value="18.4x", change="-0.5x QoQ", is_positive=True, subtext="Institutional Multiple"),
                MetricCard(label="P/E Ratio", value="26.5x", change="+1.1x vs Sector", is_positive=False, subtext="Standardized Model"),
                MetricCard(label="FCF Yield", value="4.10%", change="+30 bps QoQ", is_positive=True, subtext="Generated Cash Metric"),
            ],
            revenue_trend=[
                ChartDataPoint(period="2022", revenue=100.0, gross_profit=45.0, net_income=22.0),
                ChartDataPoint(period="2023", revenue=115.0, gross_profit=52.0, net_income=26.0),
                ChartDataPoint(period="2024", revenue=132.0, gross_profit=61.0, net_income=31.0),
                ChartDataPoint(period="2025E", revenue=150.0, gross_profit=70.0, net_income=37.0),
            ],
            recent_research=[
                ResearchNote(
                    id=f"RN-{ticker_upper}",
                    title=f"{ticker_upper} Fundamental Positioning & Multiple Analysis",
                    ticker=ticker_upper,
                    analyst="FinSight Equity Desk",
                    date="Nov 2026",
                    sentiment="Bullish",
                    target_price="$210.00",
                    summary="[DEMO DATA] Baseline institutional review highlighting healthy balance sheet liquidity."
                )
            ]
        )
    
    return DashboardData(
        company=data["company"],
        kpis=data["kpis"],
        revenue_trend=data["revenue_trend"],
        recent_research=data["recent_research"]
    )
