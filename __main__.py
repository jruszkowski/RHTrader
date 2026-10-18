import argparse
import asyncio
import os
from pathlib import Path

try:
    from rh_agent.agent import run
    from rh_agent.mcp_client import connect
except ImportError:
    from .agent import run
    from .mcp_client import connect


async def _tools():
    from rh_agent.agent import load_config
    from rh_agent.guard import Guard, is_guarded
    policy, _ = load_config()
    Guard(policy)
    async with connect() as s:
        for t in (await s.list_tools()).tools:
            tag = "GUARDED  " if is_guarded(t.name) else "read-only"
            print(f"- [{tag}] {t.name}: {(t.description or '').splitlines()[0] if t.description else ''}")
            print(f"    schema: {t.inputSchema}")
    print("\n[GUARDED] tools go through the risk layer and are blocked unless they look like valid orders."
          "\nIf a harmless data tool is marked GUARDED, add its name to read_only_tools in your config.")


def _check(strategy: str):
    import sys
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from rh_agent.agent import load_config
    ok = True

    def line(good, msg):
        nonlocal ok
        ok = ok and good
        print(("OK   " if good else "FAIL ") + msg)

    line(sys.version_info >= (3, 11), f"Python {sys.version.split()[0]} (need 3.11+)")
    line(bool(os.environ.get("ANTHROPIC_API_KEY")), "ANTHROPIC_API_KEY is set")
    line(Path(strategy).exists(), f"strategy file {strategy}")
    try:
        pol, ag = load_config()
    except Exception as e:
        line(False, f"config failed to load: {e}")
        print("NOT READY"); return
    now = datetime.now(ZoneInfo(pol.tz))
    print(f"mode: {'DRY-RUN (no orders are sent)' if pol.dry_run else 'LIVE (orders WILL be sent)'}; "
          f"approval before buys: {pol.require_approval}")
    print(f"limits: ${pol.max_order_notional:g}/trade, {pol.max_orders_per_day} orders/day, "
          f"${pol.max_daily_notional:g}/day, ${pol.max_symbol_notional_per_day:g}/name/day")
    print(f"window {pol.trade_window_start}-{pol.trade_window_end}, flatten {pol.flatten_at} ({pol.tz}); "
          f"now {now:%a %H:%M}, model {ag['model']}")
    line(not Path(pol.kill_switch_file).exists(), f"no '{pol.kill_switch_file}' file present")
    print("READY" if ok else "NOT READY")


async def _watch(every: int, strategy: str):
    """Window-aware loop: a strategy/management pass every `every` s from window start until flatten_at
    (the guard still limits ENTRIES to the trade window), a flatten pass at flatten_at, sleep otherwise."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from rh_agent.agent import FLATTEN_TASK, load_config
    from rh_agent.guard import _hhmm
    policy, _ = load_config()
    tz, task, flattened = ZoneInfo(policy.tz), Path(strategy).read_text(), None
    while True:
        if Path(policy.kill_switch_file).exists():
            print("STOP file present; exiting."); return
        now = datetime.now(tz); mins = now.hour * 60 + now.minute
        stamp = f"\n\nCurrent time: {now:%A %Y-%m-%d %H:%M %Z}."
        wait = 60
        if now.weekday() < 5 and _hhmm(policy.trade_window_start) <= mins < _hhmm(policy.flatten_at):
            print(await run(task + stamp)); wait = every
        elif now.weekday() < 5 and _hhmm(policy.flatten_at) <= mins < 16 * 60 and flattened != now.date():
            print(await run(FLATTEN_TASK + "\n\nStrategy (for its end-of-day rules):\n" + task + stamp)); flattened = now.date()
        await asyncio.sleep(min(wait, 60) if wait != every else wait)


def main():
    ap = argparse.ArgumentParser(prog="rh_agent")
    ap.add_argument("--config", help="policy file (default config.toml)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tools", help="authenticate and print the server's tools + schemas")
    r = sub.add_parser("run", help="one agent run for a task"); r.add_argument("task")
    w = sub.add_parser("watch", help="re-run the strategy on an interval")
    w.add_argument("--every", type=int, default=300); w.add_argument("--strategy", default="strategy.md")
    c = sub.add_parser("check", help="offline preflight: python, API key, config, mode, limits")
    c.add_argument("--strategy", default="strategy.md")
    b = sub.add_parser("backtest", help="backtest the equal-weight rebalance rule under the live caps")
    b.add_argument("--symbols", required=True, help="comma-separated, e.g. VTI,AAPL,MSFT")
    b.add_argument("--start", default="2019-01-01"); b.add_argument("--end")
    b.add_argument("--csv-dir"); b.add_argument("--synthetic", action="store_true")
    b.add_argument("--capital", type=float, default=1000.0); b.add_argument("--every", type=int, default=21)
    b.add_argument("--band", type=float, default=0.02); b.add_argument("--plot", default="backtest.png")
    a = ap.parse_args()
    if a.config:
        os.environ["RH_AGENT_CONFIG"] = a.config
    if a.cmd == "tools": asyncio.run(_tools())
    elif a.cmd == "check": _check(a.strategy)
    elif a.cmd == "backtest":
        from rh_agent.backtest import BTConfig, load_prices, report, synthetic_prices
        sy = [x.strip().upper() for x in a.symbols.split(",")]
        px = synthetic_prices(sy) if a.synthetic else load_prices(sy, a.start, a.end, a.csv_dir)
        report(px, BTConfig(capital=a.capital, every=a.every, band=a.band), a.plot,
               "[SYNTHETIC DATA - engine test only] " if a.synthetic else "")
    elif a.cmd == "run": print(asyncio.run(run(a.task)))
    else: asyncio.run(_watch(a.every, a.strategy))


if __name__ == "__main__":
    main()
