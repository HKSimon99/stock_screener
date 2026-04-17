"""
POST /api/v1/risk/analyze-portfolio

Submit a list of positions and entry prices to get 
stop loss alerts, position sizing recommendations, and concentration warnings.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import ClerkAuthUser, get_clerk_user
from app.api.deps import get_db
from app.schemas.risk import PortfolioRequest, PortfolioRiskResponse
from app.services.risk.analyzer import RiskAnalyzer

router = APIRouter()

@router.post("/analyze-portfolio", response_model=PortfolioRiskResponse, summary="Analyze portfolio risk")
async def analyze_portfolio(
    body: PortfolioRequest,
    db: AsyncSession = Depends(get_db),
    current_user: ClerkAuthUser = Depends(get_clerk_user),
) -> PortfolioRiskResponse:
    """
    Evaluates risk for a given portfolio:
    - 7% stop loss limit
    - ATR-based sizing checker
    - Sector & Exchange concentration limits
    """
    _ = current_user
    analyzer = RiskAnalyzer(db)
    return await analyzer.analyze_portfolio(body)
