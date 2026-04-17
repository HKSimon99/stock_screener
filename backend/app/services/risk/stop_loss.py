class StopLossChecker:
    def __init__(self, stop_loss_pct: float = 0.07):
        """
        stop_loss_pct: Default 7% (0.07) stop loss rule based on CANSLIM methodology.
        """
        self.stop_loss_pct = stop_loss_pct

    def check_position(self, entry_price: float, current_price: float) -> dict:
        """
        Evaluate if a position has hit the stop loss.
        """
        if entry_price <= 0:
            return {"hit": False, "price": 0.0, "drop_pct": 0.0}
            
        stop_price = entry_price * (1 - self.stop_loss_pct)
        drop_pct = (entry_price - current_price) / entry_price
        
        hit = current_price <= stop_price
        
        return {
            "hit": hit,
            "stop_price": stop_price,
            "drop_pct": drop_pct
        }
