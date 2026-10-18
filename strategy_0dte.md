# Strategy: aggressive 0DTE long-option scalps, final hour (edit me)

Window: 3:00-3:50pm ET, Mon-Fri, only if the market is open today. Never open positions outside it.

Universe: highly liquid, high-volatility underlyings that have a chain expiring TODAY.
(Daily expirations exist on index ETFs like SPY/QQQ; most single stocks only list same-day
expirations on Fridays. Check the chain; if nothing expires today, do nothing.)

Entry (all required):
- Underlying's range today is well above its typical day (or it is moving on a catalyst) and volume is heavy.
- Clear direction in the last hour: buy CALLS on strength holding above the day's high/VWAP, PUTS on weakness
  below the day's low/VWAP. No direction, no trade.
- Contract: expires today, delta roughly 0.25-0.45, bid-ask spread <= ~10% of mid, real volume/open interest.
- Single-leg LONG calls/puts only (buy to open). No spreads, no selling to open, no market orders:
  limit at/near mid, cancel and reprice at most once.
- Premium per trade and daily premium must fit the caps; the risk layer will reject anything bigger.

Exit:
- Take profit around +50% to +100% on premium; cut at about -40% to -50%.
- Everything is closed by 3:55pm ET. Never hold a 0DTE option into the close (expiry/exercise risk).

Behavior: max 1-2 new trades per run. Doing nothing is the correct outcome most days; say so plainly.
