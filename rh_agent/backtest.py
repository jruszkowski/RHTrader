"""Backtest the equal-weight rebalance strategy under the SAME caps the live guard enforces.

Decisions are made at day t's close and executed at day t+1's close (no lookahead),
with slippage. This tests the *rule*; it does not (and cannot honestly) test the LLM
agent's judgment, since the model's training data overlaps any historical period.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class BTConfig:
    capital: float = 1000.0
    every: int = 21
    band: float = 0.02
    slippage_bps: float = 5.0
    max_order_notional: float = 100.0
    max_daily_notional: float = 300.0
    max_orders_per_day: int = 5


def load_prices(symbols, start, end=None, csv_dir=None) -> pd.DataFrame:
    if csv_dir:
        cols = {s: pd.read_csv(Path(csv_dir) / f"{s}.csv", parse_dates=["Date"], index_col="Date")["Close"]
                for s in symbols}
        return pd.DataFrame(cols).dropna()
    import yfinance as yf
    df = yf.download(list(symbols), start=start, end=end, auto_adjust=True, progress=False)["Close"]
    return df[list(symbols)].dropna()


def synthetic_prices(symbols, years=5, seed=7) -> pd.DataFrame:
    """Correlated GBM. For smoke-testing the engine only; results mean nothing."""
    rng = np.random.default_rng(seed)
    n, T = len(symbols), int(252 * years)
    corr = np.full((n, n), 0.5) + 0.5 * np.eye(n)
    z = rng.standard_normal((T, n)) @ np.linalg.cholesky(corr).T
    mu, sig = 0.08 / 252, np.linspace(0.15, 0.35, n) / np.sqrt(252)
    px = 100 * np.exp(np.cumsum(mu - 0.5 * sig**2 + sig * z, axis=0))
    return pd.DataFrame(px, index=pd.bdate_range("2020-01-02", periods=T), columns=list(symbols))


def run_backtest(prices: pd.DataFrame, cfg: BTConfig):
    px, n, T = prices.values, prices.shape[1], len(prices)
    slip = cfg.slippage_bps / 1e4
    cash, shares = cfg.capital, np.zeros(n)
    pending: dict[int, float] = {}
    equity, n_trades, traded = [], 0, 0.0

    for t in range(T):
        if pending:
            budget, orders = cfg.max_daily_notional, 0
            for i, d in sorted(pending.items(), key=lambda kv: kv[1]):
                if d < 0:
                    amt = min(-d, shares[i] * px[t, i])
                    if amt < 1: pending[i] = 0; continue
                    shares[i] -= amt / px[t, i]; cash += amt * (1 - slip)
                    pending[i] = d + amt
                elif orders < cfg.max_orders_per_day:
                    amt = min(d, cfg.max_order_notional, budget, cash)
                    if amt < 1: continue
                    shares[i] += amt / (px[t, i] * (1 + slip)); cash -= amt
                    budget -= amt; orders += 1; pending[i] = d - amt
                else:
                    continue
                n_trades += 1; traded += amt
            pending = {i: d for i, d in pending.items() if abs(d) >= 1}
        equity.append(cash + shares @ px[t])

        if t % cfg.every == 0 and t < T - 1:
            eq = equity[-1]
            val = shares * px[t]
            pending = {i: eq / n - val[i] for i in range(n) if abs(val[i] / eq - 1 / n) > cfg.band}

    eq = pd.Series(equity, index=prices.index, name="strategy")
    bh = pd.Series(cfg.capital, index=prices.index, name="buy_hold_equal_weight")
    sh = (cfg.capital / n) / (px[1] * (1 + slip))
    bh.iloc[1:] = (px[1:] @ sh)
    return eq, bh, n_trades, traded


def metrics(s: pd.Series) -> dict:
    r = s.pct_change().dropna()
    yrs = len(s) / 252
    dd = (s / s.cummax() - 1).min()
    return {"total_return": s.iloc[-1] / s.iloc[0] - 1,
            "cagr": (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1,
            "ann_vol": r.std() * np.sqrt(252),
            "sharpe": (r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else float("nan"),
            "max_drawdown": dd}


def report(prices, cfg: BTConfig, plot: str | None = None, label: str = ""):
    eq, bh, n_trades, traded = run_backtest(prices, cfg)
    tbl = pd.DataFrame({"strategy": metrics(eq), "buy&hold EW": metrics(bh)}).T
    print(f"\nBacktest {label}{prices.index[0].date()} -> {prices.index[-1].date()}  "
          f"symbols={list(prices.columns)}  capital=${cfg.capital:,.0f}")
    out = tbl.copy()
    for c in out.columns:
        out[c] = out[c].map(lambda x: f"{x:.2f}" if c == "sharpe" else f"{x:.2%}")
    print(out.to_string())
    print(f"trades={n_trades}  turnover=${traded:,.0f} ({traded / cfg.capital:.1f}x capital)  "
          f"final=${eq.iloc[-1]:,.2f} vs ${bh.iloc[-1]:,.2f}")
    if plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ax = pd.concat([eq, bh], axis=1).plot(figsize=(9, 4), title=f"Equity {label}".strip())
        ax.set_ylabel("USD"); plt.tight_layout(); plt.savefig(plot, dpi=120); print(f"chart -> {plot}")
    return eq, bh
