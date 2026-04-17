from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.instrument import Instrument
from app.models.strategy_score import StrategyScore
from app.models.price import Price
from app.models.alert import Alert
from app.schemas.risk import PortfolioRequest, PortfolioRiskResponse, PositionRiskAnalysis, ConcentrationRisk
from app.services.risk.position_sizer import PositionSizer
from app.services.risk.stop_loss import StopLossChecker
from app.services.risk.concentration import ConcentrationChecker


class RiskAnalyzer:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sizer = PositionSizer()
        self.stop_checker = StopLossChecker()
        self.conc_checker = ConcentrationChecker()

    async def analyze_portfolio(self, req: PortfolioRequest) -> PortfolioRiskResponse:
        total_equity = req.total_equity
        positions_analysis = []
        concentration_inputs = []
        
        total_exposure = 0.0

        for pos in req.positions:
            # 1. Fetch instrument to get sector and ID
            instr_q = await self.db.execute(
                select(Instrument).where(
                    func.upper(Instrument.ticker) == pos.ticker.upper(),
                    Instrument.market == pos.market
                )
            )
            instr = instr_q.scalars().first()
            if not instr:
                continue

            # 2. Get latest price
            price_q = await self.db.execute(
                select(Price).where(Price.instrument_id == instr.id)
                .order_by(desc(Price.trade_date)).limit(1)
            )
            latest_price = price_q.scalars().first()
            current_price = float(latest_price.close) if latest_price else pos.entry_price

            # 3. Get latest technical detail for ATR
            ss_q = await self.db.execute(
                select(StrategyScore).where(StrategyScore.instrument_id == instr.id)
                .order_by(desc(StrategyScore.score_date)).limit(1)
            )
            ss = ss_q.scalars().first()
            
            atr = 0.0
            if ss and ss.technical_detail:
                indicators = ss.technical_detail.get("indicators", {})
                atr = indicators.get("ATR_14", 0.0)

            # Calculate position value
            val = current_price * pos.shares
            total_exposure += val
            
            concentration_inputs.append({
                "sector": instr.sector,
                "market": instr.market,
                "value": val
            })

            # Check stop loss
            stop_res = self.stop_checker.check_position(pos.entry_price, current_price)
            
            # Guidelines from Sizer
            rec_shares = self.sizer.calculate_position_size(total_equity, current_price, atr)
            
            alerts = []
            alert_generated = False
            if stop_res["hit"]:
                alerts.append(f"CRITICAL: Stop loss hit! Drop: {stop_res['drop_pct']:.1%}")
                # Store in DB
                alert = Alert(
                    instrument_id=instr.id,
                    market=instr.market,
                    alert_type="STOP_LOSS",
                    severity="CRITICAL",
                    title=f"{instr.ticker} hit 7% stop-loss",
                    detail=f"Entry: {pos.entry_price}, Current: {current_price}, Drop: {stop_res['drop_pct']:.2%}",
                    threshold_value=stop_res["stop_price"],
                    actual_value=current_price,
                    created_at=datetime.now(tz=timezone.utc),
                )
                self.db.add(alert)
                alert_generated = True
                
            if pos.shares > rec_shares and rec_shares > 0:
                alerts.append(f"WARNING: Oversized position. Have {pos.shares}, rec {rec_shares}.")
                
            positions_analysis.append(PositionRiskAnalysis(
                ticker=pos.ticker,
                current_price=current_price,
                percent_return=(current_price - pos.entry_price) / pos.entry_price if pos.entry_price else 0.0,
                atr_14=atr,
                recommended_position_size=rec_shares,
                stop_loss_hit=stop_res["hit"],
                stop_loss_price=stop_res["stop_price"],
                alerts=alerts
            ))

        # Check Concentration
        conc_res = self.conc_checker.check_portfolio(total_equity, concentration_inputs)
        
        # Store concentration alerts optionally
        for warn in conc_res["sector_warnings"] + conc_res["exchange_warnings"]:
            alert = Alert(
                market="US",  # Defaulting or aggregate
                alert_type="SECTOR_CONCENTRATION",
                severity="WARNING",
                title="Concentration Risk",
                detail=warn,
                created_at=datetime.now(tz=timezone.utc),
            )
            self.db.add(alert)
            alert_generated = True

        if alert_generated:
            await self.db.commit()

        cash_percentage = max(0.0, (total_equity - total_exposure) / total_equity)

        return PortfolioRiskResponse(
            total_positions=len(positions_analysis),
            total_exposure=total_exposure,
            cash_percentage=cash_percentage,
            positions_analysis=positions_analysis,
            concentration=ConcentrationRisk(
                sector_warnings=conc_res["sector_warnings"],
                exchange_warnings=conc_res["exchange_warnings"]
            )
        )
