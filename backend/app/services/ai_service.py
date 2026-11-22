"""
FinSight AI — AI Intelligence Service (Phase 2 Ready)
=====================================================
Integrates with Google Gemini API using @google/genai patterns.
In Phase 1, this service is staged and provides safe deterministic responses
without consuming live external paid credits until explicitly enabled in Phase 2.
"""

from typing import Dict, Any
from app.core.config import settings

class AIService:
    def __init__(self):
        self.api_key_configured = bool(settings.GEMINI_API_KEY)
        self.client = None
        
        # When Gemini SDK is ready and key is set:
        if self.api_key_configured:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            except Exception:
                self.client = None

    async def generate_equity_brief(self, ticker: str) -> Dict[str, Any]:
        """Generate AI equity research brief (demonstration preview in Phase 1)"""
        return {
            "ticker": ticker.upper(),
            "status": "Phase 1 Demonstration Staging",
            "executive_summary": (
                f"[DEMO DATA] {ticker.upper()} displays resilient free cash flow margins, "
                "supported by strong recurring enterprise revenue and margin expansion. "
                "Catalysts include operating leverage and market share accretion."
            ),
            "bull_case": "[DEMO DATA] Accelerated cloud migration and multiple expansion.",
            "bear_case": "[DEMO DATA] Macroeconomic softening and valuation compression.",
            "is_demo_data": True
        }

ai_service = AIService()
