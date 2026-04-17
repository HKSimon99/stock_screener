from pydantic import BaseModel, Field
from typing import Optional

class PortfolioPosition(BaseModel):
    ticker: str
    entry_price: float = Field(..., gt=0)
    shares: int = Field(..., gt=0)
    market: str = Field(default="US")

class PortfolioRequest(BaseModel):
    account_id: str
    total_equity: float = Field(..., gt=0)
    positions: list[PortfolioPosition]

class PositionRiskAnalysis(BaseModel):
    ticker: str
    current_price: Optional[float] = None
    percent_return: Optional[float] = None
    atr_14: Optional[float] = None
    recommended_position_size: Optional[int] = None
    stop_loss_hit: bool = False
    stop_loss_price: float
    alerts: list[str] = []

class ConcentrationRisk(BaseModel):
    sector_warnings: list[str] = []
    exchange_warnings: list[str] = []

class PortfolioRiskResponse(BaseModel):
    total_positions: int
    total_exposure: float
    cash_percentage: float
    positions_analysis: list[PositionRiskAnalysis]
    concentration: ConcentrationRisk
