"""Deterministic risk layer between the LLM and Robinhood.

The model proposes; this code disposes. It fails CLOSED: if an order's size
can't be determined from its arguments, the order is rejected and the model is
told to resubmit with a limit price + quantity (or a dollar amount).
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

LOCAL = Path(".rh_agent")
SYMBOL_KEYS = ("symbol", "ticker")
SIDE_KEYS = ("side",)
QTY_KEYS = ("quantity", "qty", "shares")
PRICE_KEYS = ("limit_price", "price")
NOTIONAL_KEYS = ("dollar_amount", "notional", "amount")
READ_ONLY_TOOLS = {
    "get_accounts",
    "get_portfolio",
    "get_equity_orders",
    "get_option_orders",
    "get_watchlists",
    "get_watchlist_items",
    "search",
    "update_watchlist",
    "follow_watchlist",
    "unfollow_watchlist",
    "get_quote",
    "get_quotes",
    "get_historicals",
    "get_alerts",
    "get_alert_log",
    "get_trade_approvals",
    "get_trade_approval_setting",
    "get_positions",
    "get_option_positions",
    "get_option_chains",
    "get_option_instruments",
    "get_option_quotes",
    "get_option_historicals",
}


def is_guarded(tool: str) -> bool:
    """Anything that isn't clearly read-only or a watchlist edit is guarded."""
    return tool not in READ_ONLY_TOOLS


def _find(args, keys):
    if not isinstance(args, dict):
        return None
    for k in keys:
        if args.get(k) not in (None, ""):
            return args[k]
    for v in args.values():
        if isinstance(v, dict):
            r = _find(v, keys)
            if r is not None:
                return r
    return None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


@dataclass
class Policy:
    dry_run: bool = True
    require_approval: bool = True
    approve_exits: bool = False
    approval_timeout_s: int = 60
    max_order_notional: float = 100.0
    max_daily_notional: float = 300.0
    max_orders_per_day: int = 5
    max_symbol_notional_per_day: float = 200.0
    count_exits: bool = False
    allow_options: bool = False
    allow_short_legs: bool = False
    entry_weekdays: tuple[int, ...] = (0, 1, 2, 3, 4)
    allowed_symbols: tuple = ()
    kill_switch_file: str = "STOP"
    tz: str = "America/New_York"
    trade_window_start: str = "09:30"
    trade_window_end: str = "15:45"
    flatten_at: str = "15:45"
    read_only_tools: tuple = ()
    enforce_exits: bool = False
    max_opens_per_symbol: int = 1
    min_symbol_cash: float = 50.0
    exit_stop_pct: float = 0.10
    exit_target_pct: float = 0.20
    allowlist: tuple = ()
    ledger_values: dict = field(default_factory=dict)


class Guard:
    def __init__(self, policy: Policy):
        self.p = policy
        LOCAL.mkdir(exist_ok=True)
        self.ledger_path = LOCAL / "ledger.json"
        self.audit_path = LOCAL / "audit.jsonl"
        self.ledger_dry_path = LOCAL / "ledger_dry.json"

    def _today(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _ledger(self) -> dict:
        d = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {}
        return d.get(self._today(), {"notional": 0.0, "orders": 0, "symbols": {}})

    def record(self, notional: float, symbol: str | None = None):
        d = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {}
        day = d.get(self._today(), {"notional": 0.0, "orders": 0, "symbols": {}})
        day["notional"] += notional
        day["orders"] += 1
        if symbol:
            symbols = day.setdefault("symbols", {})
            symbols[str(symbol).upper()] = symbols.get(str(symbol).upper(), 0.0) + notional
        d[self._today()] = day
        self.ledger_path.write_text(json.dumps(d, indent=2))

    def audit(self, **kw):
        with self.audit_path.open("a") as f:
            f.write(json.dumps({"ts": time.time(), **kw}, default=str) + "\n")

    def check(self, tool: str, args: dict):
        """Returns (allowed, reason, est_notional)."""
        if Path(self.p.kill_switch_file).exists():
            return False, f"Kill switch file '{self.p.kill_switch_file}' exists.", 0.0
        if "cancel" in tool:
            return True, "cancel", 0.0

        symbol = _find(args, SYMBOL_KEYS)
        side = str(_find(args, SIDE_KEYS) or "").lower()
        if not symbol:
            return False, "Could not find a symbol in the order arguments.", 0.0
        if self.p.allowed_symbols and str(symbol).upper() not in {s.upper() for s in self.p.allowed_symbols}:
            return False, f"{symbol} is not in allowed_symbols.", 0.0

        notional = _num(_find(args, NOTIONAL_KEYS))
        if notional is None:
            q, px = _num(_find(args, QTY_KEYS)), _num(_find(args, PRICE_KEYS))
            notional = q * px if q is not None and px is not None else None
        if notional is None:
            return False, (
                "Cannot determine order size. Resubmit as a limit order with "
                "quantity and limit price, or with a dollar amount."
            ), 0.0

        if side == "sell":
            return True, "sell", notional

        day = self._ledger()
        if notional > self.p.max_order_notional:
            return False, f"${notional:,.2f} exceeds max_order_notional ${self.p.max_order_notional:,.2f}.", notional
        if day["notional"] + notional > self.p.max_daily_notional:
            return False, f"Would exceed max_daily_notional (${day['notional']:,.2f} already used today).", notional
        if day["orders"] + 1 > self.p.max_orders_per_day:
            return False, "max_orders_per_day reached.", notional
        symbol_key = str(symbol).upper()
        if day.get("symbols", {}).get(symbol_key, 0.0) + notional > self.p.max_symbol_notional_per_day:
            return False, f"Would exceed per-symbol daily cap for {symbol_key}.", notional
        return True, "ok", notional

    async def approve(self, tool: str, args: dict) -> bool:
        print("\n=== ORDER APPROVAL ===")
        print(f"tool: {tool}\nargs: {json.dumps(args, indent=2)}")
        ans = await asyncio.get_running_loop().run_in_executor(None, input, "Send to Robinhood? [y/N] ")
        return ans.strip().lower() == "y"


def _hhmm(s: str):
    h, m = map(int, s.split(":"))
    return h * 60 + m
