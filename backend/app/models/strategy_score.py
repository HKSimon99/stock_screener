from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class StrategyScore(Base):
    """
    Per-instrument daily scores for all 5 strategies + technical composite.
    Each strategy column holds a 0-100 normalized score.
    Detail columns hold the raw values that produced the score (audit trail).
    """
    __tablename__ = "strategy_scores"

    id = Column(Integer, primary_key=True)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=False)
    score_date = Column(Date, nullable=False)

    # ── CANSLIM (Section 3.1) ────────────────────────────────────────────────
    canslim_score = Column(Numeric(5, 2))
    canslim_c = Column(Numeric(5, 2))               # Current earnings sub-score
    canslim_a = Column(Numeric(5, 2))               # Annual earnings sub-score
    canslim_n = Column(Numeric(5, 2))               # New highs / base sub-score
    canslim_s = Column(Numeric(5, 2))               # Supply/demand sub-score
    canslim_l = Column(Numeric(5, 2))               # Leader/RS sub-score
    canslim_i = Column(Numeric(5, 2))               # Institutional sub-score
    canslim_detail = Column(JSONB)                  # Raw values behind each sub-score

    # ── Piotroski F-Score (Section 3.2) ─────────────────────────────────────
    piotroski_score = Column(Numeric(5, 2))         # Normalized 0–100
    piotroski_f_raw = Column(Integer)               # Raw 0–9 F-score
    piotroski_detail = Column(JSONB)                # F1–F9 individual pass/fail

    # ── Minervini Trend Template (Section 3.3) ───────────────────────────────
    minervini_score = Column(Numeric(5, 2))
    minervini_criteria_count = Column(Integer)      # How many of 8 criteria pass
    minervini_detail = Column(JSONB)                # T1–T8 individual pass/fail

    # ── Weinstein Stage Analysis (Section 3.4) ───────────────────────────────
    weinstein_score = Column(Numeric(5, 2))
    weinstein_stage = Column(String(20))            # '1'|'2_early'|'2_mid'|'2_late'|'3'|'4'
    weinstein_detail = Column(JSONB)                # ma_slope, price_vs_ma, cross_count

    # ── Dual Momentum (Section 3.5) ─────────────────────────────────────────
    dual_mom_score = Column(Numeric(5, 2))
    dual_mom_abs = Column(Boolean)                  # Absolute momentum pass
    dual_mom_rel = Column(Boolean)                  # Relative momentum pass
    dual_mom_detail = Column(JSONB)                 # ret_12m, benchmark_ret, risk_free

    # ── Technical Composite (Section 4) ─────────────────────────────────────
    technical_composite = Column(Numeric(5, 2))
    patterns = Column(JSONB)                        # List of detected patterns + confidence
    rs_rating = Column(Numeric(5, 2))               # IBD-style RS rating (1–99)
    rs_line_new_high = Column(Boolean)
    ad_rating = Column(String(2))                   # 'A+'|'A'|'B'|'C'|'D'|'E'
    bb_squeeze = Column(Boolean)
    technical_detail = Column(JSONB)                # All indicator values

    # ── Metadata ─────────────────────────────────────────────────────────────
    market_regime = Column(String(30))              # Regime at time of scoring
    data_freshness = Column(JSONB)                  # Per-factor data age in days
    score_version = Column(Integer, default=1, nullable=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "score_date",
            name="uq_strategy_score_instrument_date"
        ),
    )
