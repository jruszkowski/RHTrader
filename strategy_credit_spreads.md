# Strategy: weekly credit spreads for theta, low-volatility underlyings (edit me)

Goal: collect time decay by selling OUT-OF-THE-MONEY put credit spreads and/or call credit spreads
(both on one name = an iron condor), defined risk only, small size, on calm stocks/ETFs.

Underlyings: liquid, historically low-volatility names/ETFs with weekly options. Require ALL of:
- No earnings before expiration. Check ex-dividend dates (ITM short calls get assigned early before ex-div).
- Recent realized volatility is low and the stock isn't gapping or trending hard; no scheduled catalyst this week.
- Option bid-ask spread <= ~10% of mid on both legs, with real open interest.

Entry (Mon-Wed, inside the window; the risk layer enforces the days, window, and expiry range):
- Expiration: the nearest weekly (2-10 days out).
- Short strike ~0.10-0.20 delta and outside the stock's expected move; wing $1-$2.50 further out, same expiry.
- Net credit >= 20% of the width. If the credit is thinner than that, skip it: low-vol names pay little,
  and the right answer is often "no trade today".
- 1 contract per spread. Put side when the stock is calm/rising, call side when calm/falling, both if range-bound.
- Execution (multi-leg orders are NOT available): (1) BUY the protective wing first, LIMIT near mid;
  (2) once filled, SELL the short leg at a LIMIT that meets the credit target; reprice at most once;
  (3) if the short can't fill, sell the wing back and report it. Never hold a short without its wing.

Management (every pass):
- Take profit at ~50% of the credit: buy back the SHORT first, then sell the wing.
- Close the whole spread if the stock trades through the short strike, the short delta reaches ~0.35,
  or the spread's loss reaches ~2x the credit received. Do not roll for a bigger hole, do not average down.
- Close anything expiring TODAY by 2:45pm ET. Never carry short options into expiration.

Behavior: at most 1-2 new spreads per run. Doing nothing is a normal and often correct outcome; say so plainly.
