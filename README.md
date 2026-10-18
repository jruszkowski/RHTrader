# rh-agent: agentic trading on Robinhood's MCP server

Claude (via the Anthropic API) reasons; Robinhood's hosted MCP server
(`https://agent.robinhood.com/mcp/trading`) executes; a deterministic risk layer sits between them.

```
strategy.md ─► Claude ─► tool calls ─► [guard.py: caps, allowlist, kill switch, approval, dry-run] ─► Robinhood MCP
                                                                   └─► .rh_agent/audit.jsonl
```

## Setup
Prereq: Robinhood Agentic Trading beta access and an Agentic account (separate, dedicated, funded only with what you're willing to lose).

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=...
    python -m rh_agent tools            # browser OAuth with Robinhood; prints real tool schemas

## Run
    python -m rh_agent run "Summarize my agentic account and open orders"
    python -m rh_agent run "$(cat strategy.md)"
    python -m rh_agent watch --every 3600 --strategy strategy.md

`config.toml` ships with `dry_run = true`: order calls are intercepted and never sent. Review `.rh_agent/audit.jsonl`
for a few runs, then set `dry_run = false`. With `require_approval = true` each real order still needs a terminal `y`.

## Safety model
- Hard cap = the funded Agentic account balance (Robinhood-side). Keep it small.
- Per-order, per-day, order-count limits; symbol allowlist; `touch STOP` blocks all orders instantly.
- Fails closed: if order size can't be parsed from the arguments, it's rejected.
- Tool output is treated as untrusted data (prompt-injection defense in the system prompt).
- You can also disconnect the agent from inside the Robinhood app.

## Caveats
- Written against public docs; the order-tool argument schemas weren't verifiable offline. `guard.py` looks for common
  field names (`symbol`, `side`, `quantity`, `limit_price`, `dollar_amount`). Run `tools` and adjust the `*_KEYS`
  tuples if Robinhood's names differ.
- Tool names seen publicly: get_accounts, get_portfolio, get_equity_orders, get_watchlists, search,
  update_watchlist, place_equity_order, cancel_equity_order.
- Not financial advice; agent-driven trading can lose your whole stake.

## Backtest
    pip install -r requirements.txt
    python -m rh_agent backtest --symbols VTI,AAPL,MSFT --start 2019-01-01          # Yahoo data via yfinance
    python -m rh_agent backtest --symbols VTI,AAPL --csv-dir ./prices                # ./prices/<SYM>.csv with Date,Close
    python -m rh_agent backtest --symbols VTI,AAPL --synthetic                       # engine smoke test only

Tests the equal-weight rebalance *rule* under the same per-order/daily/order-count caps as `guard.py`, decisions at
close t executed at close t+1 with slippage, versus equal-weight buy & hold. It cannot honestly backtest the LLM's
judgment (the model's training data overlaps history), so test that with `dry_run` instead.

## Strategy: intraday equity momentum (current `strategy.md` + `config.toml`)
Long-only momentum entries on liquid US stocks: gainers on heavy relative volume breaking the opening-range/day high above VWAP.
- Limits enforced in code: **20 entries/day, $50 per trade, $1,000/day, $150 per name/day**, entries 9:45-15:30 ET, no options, flat by 15:45.
  "Trade" = an entry; exits are never blocked. Set `count_exits = true` to make sells count toward the 20 / $1,000 too.
- Orders: size by `dollar_amount` or quantity x limit price; a market order with only a share count is rejected (size unknown).
- The daily ledger is kept in dry-run too (`ledger_dry.json`), so the caps show up in dry-run audits exactly as they would live.
- Not enforced by code: the strategy's -$40 day-stop and its stop/target rules. The agent only watches positions when a pass runs
  (`python -m rh_agent watch --every 300`), so a stock can move through your stop between passes. A polling LLM agent is slow
  momentum, not high-frequency. Reduce `--every` for tighter management at the cost of more API calls.
- Day-trading rules: Robinhood says the pattern-day-trader rule was replaced on June 4, 2026: margin accounts need $2,000 minimum
  equity and are watched for intraday margin deficits. Verify whether your Agentic account is margin or cash (cash accounts have settlement limits).
- `backtest` still models only the old rebalance rule; there is no honest intraday backtest here (no data access, and LLM judgment leaks).

## Strategy: weekly credit spreads (`strategy_credit_spreads.md` + `config_credit_spreads.toml`)
Sells out-of-the-money put and/or call credit spreads (defined risk) on the nearest weekly, Mon-Wed entries, small size.
- **No multi-leg orders:** Robinhood's agents can't place them, so spreads are built from single-leg orders: buy the
  protective wing first, then sell the short. The risk layer tracks legs in `.rh_agent/legs_*.json` and rejects a short
  that has no wing, a wing sold while it still protects a short, naked shorts, multi-leg payloads, and ambiguous sells.
- **Unverified:** whether Robinhood accepts a single-leg sell-to-open against a wing you already hold, and what buying
  power it reserves. Check with `python -m rh_agent tools`, a dry run, and Robinhood.
- Caps: `max_spread_width`, `max_risk_per_trade`, `max_open_risk`, `min_credit_ratio`, expiry 2-10 days out.

## Switching strategies
Each strategy is a pair of files; `--config` picks the policy and `--strategy` the text:

    python -m rh_agent watch --every 300 --strategy strategy.md                                   # equity momentum (default)
    python -m rh_agent --config config_credit_spreads.toml watch --every 1800 --strategy strategy_credit_spreads.md
    python -m rh_agent --config config_0dte.toml watch --strategy strategy_0dte.md                # 0DTE long options
    (`strategy_rebalance.md` is the backtested equal-weight rule)
