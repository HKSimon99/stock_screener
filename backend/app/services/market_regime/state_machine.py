import pandas as pd
import numpy as np
from enum import Enum

class MarketState(Enum):
    CONFIRMED_UPTREND = "CONFIRMED_UPTREND"
    UPTREND_UNDER_PRESSURE = "UPTREND_UNDER_PRESSURE"
    MARKET_IN_CORRECTION = "MARKET_IN_CORRECTION"

def detect_market_regime(df: pd.DataFrame, close_col: str = 'close', vol_col: str = 'volume', date_col: str = 'trade_date') -> pd.DataFrame:
    """
    Computes IBD-style Market Regime for a broad market index historically.
    Requires daily OHLCV data with at least 'close', 'volume', and 'trade_date'.

    State transitions:
      CONFIRMED_UPTREND → UNDER_PRESSURE:  5+ distribution days in 25 sessions OR drawdown > 7%
      CONFIRMED_UPTREND → CORRECTION:      drawdown ≥ 10% OR death cross (SMA50 < SMA200)
      UNDER_PRESSURE → CORRECTION:         drawdown ≥ 10% OR 7+ distribution days
      UNDER_PRESSURE → CONFIRMED_UPTREND:  distribution days ≤ 2 AND drawdown < 5%
      CORRECTION → CONFIRMED_UPTREND:      Follow-Through Day (FTD) confirmed
    """
    df = df.copy()
    df = df.sort_values(by=date_col).reset_index(drop=True)

    prev_close = df[close_col].shift(1)
    prev_vol = df[vol_col].shift(1)

    # 1. Distribution Days (down > 0.2% on higher volume)
    pct_change = (df[close_col] - prev_close) / prev_close
    is_distribution = (pct_change < -0.002) & (df[vol_col] > prev_vol)
    df['is_distribution'] = is_distribution

    # Rolling 25-day distribution count
    df['dist_count_25d'] = df['is_distribution'].rolling(window=25, min_periods=1).sum()

    # 2. Drawdown from cumulative high
    rolling_peak = df[close_col].cummax()
    drawdown = (df[close_col] - rolling_peak) / rolling_peak
    df['drawdown'] = drawdown

    # 3. SMAs for Golden/Death Cross
    df['sma_50'] = df[close_col].rolling(window=50, min_periods=50).mean()
    df['sma_200'] = df[close_col].rolling(window=200, min_periods=200).mean()

    # 4. State Machine Execution
    states = []
    current_state = MarketState.CONFIRMED_UPTREND

    # FTD tracking
    rally_day_count = 0
    rally_low = float('inf')  # The lowest low since correction started

    closes_arr = df[close_col].values
    lows_arr = df['low'].values if 'low' in df.columns else closes_arr
    pct_chgs = pct_change.values
    vols = df[vol_col].values
    prev_vols = prev_vol.values
    dist_counts = df['dist_count_25d'].values
    drawdowns = df['drawdown'].values
    sma50 = df['sma_50'].values
    sma200 = df['sma_200'].values

    for i in range(len(df)):
        c_pct = pct_chgs[i] if not np.isnan(pct_chgs[i]) else 0.0
        c_dist = dist_counts[i] if not np.isnan(dist_counts[i]) else 0
        c_dd = drawdowns[i] if not np.isnan(drawdowns[i]) else 0.0
        c_close = closes_arr[i]
        c_low = lows_arr[i]
        c_vol = vols[i] if not np.isnan(vols[i]) else 0
        c_prev_vol = prev_vols[i] if not np.isnan(prev_vols[i]) else 0
        c_sma50 = sma50[i]
        c_sma200 = sma200[i]

        if current_state == MarketState.MARKET_IN_CORRECTION:
            # Track the rally attempt low
            if c_low < rally_low:
                rally_low = c_low
                rally_day_count = 0  # New low resets the rally attempt

            if c_pct > 0:
                rally_day_count += 1
            elif c_close < rally_low:
                # Undercut rally low → rally attempt fails
                rally_day_count = 0
                rally_low = c_low

            # Follow-Through Day: Day 4+ of rally, gain ≥ 1.25%, higher volume
            if (
                rally_day_count >= 4
                and c_pct >= 0.0125
                and c_vol > c_prev_vol
            ):
                current_state = MarketState.CONFIRMED_UPTREND
                rally_day_count = 0
                rally_low = float('inf')

        elif current_state == MarketState.CONFIRMED_UPTREND:
            rally_day_count = 0

            # Death cross: fast downgrade to CORRECTION
            if (
                not np.isnan(c_sma50) and not np.isnan(c_sma200)
                and c_sma50 < c_sma200
                and c_dd < -0.08
            ):
                current_state = MarketState.MARKET_IN_CORRECTION
                rally_low = c_low
            # Sudden crash → CORRECTION
            elif c_dd < -0.10:
                current_state = MarketState.MARKET_IN_CORRECTION
                rally_low = c_low
            # Pressure: too many distribution days or mild drawdown
            elif c_dd < -0.07 or c_dist >= 5:
                current_state = MarketState.UPTREND_UNDER_PRESSURE

        elif current_state == MarketState.UPTREND_UNDER_PRESSURE:
            # Escalate to CORRECTION if drawdown deepens or distribution piles up
            if c_dd <= -0.10 or c_dist >= 7:
                current_state = MarketState.MARKET_IN_CORRECTION
                rally_low = c_low
            # Recover to UPTREND if distribution fades
            elif c_dist <= 2 and c_dd > -0.05:
                current_state = MarketState.CONFIRMED_UPTREND

        states.append(current_state.value)

    df['regime'] = states

    # 5. Golden/Death cross flag for context
    df['is_golden_cross'] = df['sma_50'] > df['sma_200']

    return df
