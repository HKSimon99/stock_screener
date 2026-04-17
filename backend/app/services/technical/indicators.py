import numpy as np
import pandas as pd

def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Compute Simple Moving Average."""
    return series.rolling(window=window, min_periods=1).mean()

def compute_ema(series: pd.Series, window: int) -> pd.Series:
    """Compute Exponential Moving Average."""
    return series.ewm(span=window, adjust=False).mean()

def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    Compute Average True Range (ATR).
    TR = max(High-Low, abs(High - PrevClose), abs(Low - PrevClose))
    ATR = 14-day rolling mean of TR (or Wilder's smoothing)
    """
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Simple rolling mean for ATR, though Wilder's smoothed is also common.
    # We will use simple rolling mean to avoid over-complicating, as it's standard for many basic scans.
    atr = tr.rolling(window=window, min_periods=1).mean()
    return atr

def compute_52w_high_low(high: pd.Series, low: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Compute 52-week (rolling 252 trading days) high and low.
    """
    window = 252
    high_52w = high.rolling(window=window, min_periods=1).max()
    low_52w = low.rolling(window=window, min_periods=1).min()
    return high_52w, low_52w

def compute_rs_rating(df: pd.DataFrame, close_col: str = 'close', date_col: str = 'trade_date') -> pd.DataFrame:
    """
    Compute raw Relative Strength performance over 1 year (or available max).
    Common IBD approach:
    RS = (current / 1_qtr_ago) * 0.4 + (1_qtr_ago / 2_qtr_ago) * 0.2 + (2_qtr_ago / 3_qtr_ago) * 0.2 + (3_qtr_ago / 1_yr_ago) * 0.2
    However, a simpler perfectly valid proxy is 1-year total return percent change.
    We will use a 1-year percent change (252 days) for raw RS.
    Returns a dataframe with 'rs_raw' added.
    """
    df = df.copy()
    # Ensure sorted by date
    df = df.sort_values(by=date_col)
    
    # 252 trading days ~ 1 year
    shifted_close = df[close_col].shift(252)
    
    # Avoid division by zero
    rs_raw = np.where(shifted_close > 0, (df[close_col] - shifted_close) / shifted_close, np.nan)
    df['rs_raw'] = rs_raw * 100 # percentage points
    
    return df

def batch_compute_rs_percentile(df_all_instruments: pd.DataFrame, group_col: str = 'market', date_col: str = 'trade_date', rs_raw_col: str = 'rs_raw') -> pd.DataFrame:
    """
    Given a dataframe of multiple instruments with a precomputed 'rs_raw' column,
    compute the 1-99 percentile rank cross-sectionally per market and per date.
    """
    df = df_all_instruments.copy()
    
    # Using transform to avoid pandas index/column dropping issues with apply
    pct_rank = df.groupby([date_col, group_col])[rs_raw_col].rank(pct=True, na_option='keep')
    df['rs_rating'] = np.floor(pct_rank * 98) + 1
    
    return df
