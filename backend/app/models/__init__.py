# Import all models so that Base.metadata is fully populated when
# alembic/env.py imports this module.
from app.models.instrument import Instrument          # noqa: F401
from app.models.price import Price                    # noqa: F401
from app.models.fundamental import FundamentalQuarterly, FundamentalAnnual  # noqa: F401
from app.models.institutional import InstitutionalOwnership  # noqa: F401
from app.models.strategy_score import StrategyScore   # noqa: F401
from app.models.consensus_score import ConsensusScore # noqa: F401
from app.models.market_regime import MarketRegime     # noqa: F401
from app.models.etf import EtfConstituent, EtfScore   # noqa: F401
from app.models.alert import Alert                    # noqa: F401
from app.models.snapshot import ScoringSnapshot, DataFreshness  # noqa: F401
