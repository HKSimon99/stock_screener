import math

class PositionSizer:
    def __init__(self, atr_multiplier: float = 2.0, account_risk_pct: float = 0.01):
        """
        atr_multiplier: How many ATRs to set the stop loss at.
        account_risk_pct: Max percentage of total equity to risk on a single trade (e.g. 1%).
        """
        self.atr_multiplier = atr_multiplier
        self.account_risk_pct = account_risk_pct

    def calculate_position_size(self, total_equity: float, current_price: float, atr: float) -> int:
        """
        Calculate recommended number of shares using ATR-based positional sizing.
        Equation: Shares = (Total Equity * Risk %) / (ATR * Multiplier)
        """
        if atr <= 0 or current_price <= 0:
            return 0
        
        capital_at_risk = total_equity * self.account_risk_pct
        risk_per_share = atr * self.atr_multiplier
        
        if risk_per_share <= 0:
            return 0
            
        shares = math.floor(capital_at_risk / risk_per_share)
        
        # Ensure we don't exceed 25% of total equity in a single position (hard cap)
        max_position_value = total_equity * 0.25
        if shares * current_price > max_position_value:
            shares = math.floor(max_position_value / current_price)
            
        return max(0, shares)

