# Strategy: intraday momentum chasing on US equities (edit me)

Hard limits (enforced by the risk layer, not by you): at most 20 entries per day, at most $50 per trade
(size to $45-$50; rounding above $50 is rejected), at most $1,000 of entries per day, at most $150 per symbol per day,
entries only 9:45am-3:30pm ET. Long only: no shorting, no margin, no options. Sells/exits are never blocked.

Universe: liquid US stocks/ETFs only. Price >= $5, average volume >= ~1M shares/day, bid-ask spread <= ~0.15% of price,
no OTC/penny names, no leveraged/inverse ETFs. Use the scan/search tools to find top intraday gainers and
unusual-volume names; skip anything you can't verify is liquid.

Entry (all required):
- Up roughly +2% to +8% on the day (skip > +15%: parabolic names reverse) on relative volume >= ~2x normal.
- Breaking out: trading above the opening-range high or the day/pre-market high, AND above VWAP, with volume expanding.
- A catalyst (news, earnings reaction, sector move) is a plus; a drift with no volume is not a setup.
- Not already extended: skip if it has run > ~3% in the last 15 minutes with no pullback.
- Size: dollar-based order of ~$45-$50 (fractional shares are fine). At most 2 entries per name per day, and never add to a loser.

Exit (check every pass; positions are only watched when this runs, so be disciplined):
- Stop: sell if down ~1% from entry or if price loses VWAP on volume.
- Target: take profit around +2%; if it keeps running, sell half and trail the rest under recent 5-min lows.
- Time stop: not up at least +0.5% after ~30-45 minutes means the momentum failed, so sell.
- Everything is sold by 3:45pm ET. Never hold overnight.

Soft day-stop (not enforced by code): if the day's P&L is worse than about -$40, open no more trades today.

Behavior: at most 3 new entries per run; no revenge trades; "no setup right now" is a normal outcome, say so plainly.
