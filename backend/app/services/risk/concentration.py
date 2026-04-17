from collections import defaultdict

class ConcentrationChecker:
    def __init__(self, max_sector_pct: float = 0.25, max_exchange_pct: float = 0.50):
        """
        max_sector_pct: Max percentage of portfolio in a single sector (25% default).
        max_exchange_pct: Max percentage of portfolio in a single market/exchange (50% default).
        """
        self.max_sector_pct = max_sector_pct
        self.max_exchange_pct = max_exchange_pct

    def check_portfolio(self, total_equity: float, positions: list[dict]) -> dict:
        """
        positions: list of dicts with {"sector": "Tech", "market": "US", "value": 10000.0}
        """
        sector_exposure = defaultdict(float)
        exchange_exposure = defaultdict(float)
        
        for p in positions:
            val = p.get("value", 0.0)
            sector_exposure[p.get("sector", "Unknown")] += val
            exchange_exposure[p.get("market", "Unknown")] += val
            
        sector_warnings = []
        for sector, val in sector_exposure.items():
            pct = val / total_equity if total_equity > 0 else 0
            if pct > self.max_sector_pct and sector != "Unknown":
                sector_warnings.append(
                    f"Overweight in {sector}: {pct:.1%} (Limit {self.max_sector_pct:.1%})"
                )
                
        exchange_warnings = []
        for ex, val in exchange_exposure.items():
            pct = val / total_equity if total_equity > 0 else 0
            if pct > self.max_exchange_pct and ex != "Unknown":
                exchange_warnings.append(
                    f"Overweight in {ex} Market: {pct:.1%} (Limit {self.max_exchange_pct:.1%})"
                )
                
        return {
            "sector_warnings": sector_warnings,
            "exchange_warnings": exchange_warnings,
        }
