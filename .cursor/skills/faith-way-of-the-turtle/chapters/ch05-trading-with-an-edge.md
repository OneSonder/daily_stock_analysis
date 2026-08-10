# Chapter 5: Trading with an Edge

## Core Idea
Without an **edge**, trading costs guarantee long-run losses. An edge is an exploitable statistical advantage based on market behavior likely to recur.

## Frameworks Introduced
- **Edge definition**: Advantage from recurring behavior (often cognitive-bias driven), not dart-throw entries.
- **Edge components**: Portfolio selection + entry signals + exit signals (pair entries/exits by style/timeframe).
- **E-ratio (Edge Ratio)**: Volatility-normalized measure of favorable vs adverse excursion after an entry.
- **Trend portfolio filter**: Restrict longs/shorts by long-term MA relationship to improve breakout edge.
- **Exit edge**: Judge exits by system-level impact, not post-exit price "what if."

## Key Concepts
- **MAE / MFE**: Maximum adverse / favorable excursion after entry.
- **ATR normalization**: Divide excursions by ATR so edges compare across markets.
- **E-n ratio**: MFE/MAE over n days post-signal (e.g., E10, E50, E70).
- **Donchian channel breakout**: Buy above 20-day high / sell below 20-day low (example system component).
- **Trend filter example**: Long only if 50-day MA > 300-day MA; short only if 50 < 300.
- **Timeframe fit**: Short-term E-ratio can be ≤1 even when medium-term E-ratio >1 for trend entries.

## Mental Models
- Pair **entry style with exit style** (trend entry ≠ countertrend exit).
- Measure edges in the **horizon the system actually holds**.
- Prefer filters that remove trades against the dominant market state.

## Anti-patterns
- Entries with no statistical advantage after costs.
- Mixing mismatched horizons (day-trade entry with multi-month exit logic without testing).
- Treating random entries as skill (E-ratio ≈ 1.0 by construction).
- Obsessing over post-exit moves (money is only at risk while in the market).

## Worked Example
Random coin-flip entries → E5≈1.01, E10≈1.005, E50≈0.997 (≈1.0). 20-day Donchian breakout alone: weak/negative short-term E-ratio, E70≈1.20. Add 50/300 trend filter: random entries under filter E70≈1.27; breakout+filter E70≈1.33 and smoother edge curve (E120≈1.6). Short-term adverse move explains why breakouts feel terrible and why countertrend can have short-horizon edge.

## Key Takeaways
1. Define edge as recurring statistical advantage.
2. Portfolio filter can be as important as entry.
3. Normalize by volatility (ATR) when comparing markets.
4. Match measurement window to system timeframe.
5. Exits matter via whole-system metrics, not isolated perfection.

## Connects To
- **Ch 6**: Why short-term breakout fades create countertrend edges
- **Ch 9–10**: Building-block indicators and full systems
- **Ch 12**: Robust performance metrics beyond naive Sharpe
