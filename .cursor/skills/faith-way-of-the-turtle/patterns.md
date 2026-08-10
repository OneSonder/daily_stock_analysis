# Patterns — Way of the Turtle

## Trend-Following Breakout
**When to use**: Markets leave quiet ranges into sustained directional moves; you can tolerate many small losers.
**How**: Enter on N-day high/low breakouts aligned with a long-term trend filter; exit on opposite shorter breakout or MA reclaim; stop at ~2N.
**Trade-offs**: Low win rate, large givebacks at bends; needs capital and psychological stamina.

## Volatility-Normalized Unit Sizing
**When to use**: Multi-market portfolios where raw contract counts would overweight volatile markets.
**How**: Compute N (ATR); size unit so 1N ≈ target % equity; truncate to whole contracts.
**Trade-offs**: Small accounts lose diversification granularity; huge ATR markets may be untradable at safe risk.

## Portfolio / Correlated Unit Limits
**When to use**: Always for aggressive multi-market trend books.
**How**: Cap units per market and per correlated group/direction so shock days can't compound unboundedly.
**Trade-offs**: May miss lagging markets' late entries (often a feature); reduces peak returns.

## Trend Portfolio Filter
**When to use**: Breakout systems that bleed in countertrend chops.
**How**: Long only if fast MA > slow MA (e.g., 50/300 or 25/350); short only if opposite.
**Trade-offs**: Misses some V-reversals; improves medium-term E-ratio and robustness.

## Countertrend Fade of Failed Breakouts
**When to use**: Short horizon around support/resistance when breakouts show adverse short-term E-ratio.
**How**: Fade extensions that fail to hold beyond S/R; tight horizon exits; avoid fighting strong filtered trends.
**Trade-offs**: Crushed in clean trends; edge is horizon-specific and fragile under crowding.

## Pyramiding on Strength
**When to use**: Confirmed trends after initial unit is working.
**How**: Add units every ~½N favorable progress up to unit caps.
**Trade-offs**: Concentrates risk into winners (good) but increases shock exposure if limits ignored.

## Time-Based Exit Overlay
**When to use**: Want to cut late-trend giveback earlier than lagging indicators.
**How**: Exit after fixed holding days even if breakout exit not hit.
**Trade-offs**: May exit before major continuation; can smooth DD profile.

## Dual/Triple Moving-Average Systems
**When to use**: Want continuous or gated trend exposure without breakout geometry.
**How**: Trade fast/slow crossover; optional ultra-slow gate (triple MA).
**Trade-offs**: Whipsaws in chop; always-in dual MA never flat.

## Robust Backtest Protocol
**When to use**: Any system research before capital.
**How**: Multi-state long samples; prefer RAR%/R-cubed; parameter scramble; rolling windows; Monte Carlo; watch trader effects.
**Trade-offs**: More work; yields "worse looking" but more honest expectations.

## Ego-Detached Process Trading
**When to use**: Always — especially after streaks.
**How**: Precommit rules; judge process not last trade; no favorites/excuses; skip secrecy myths.
**Trade-offs**: Feels boring; ego resists; is the scarce edge.
