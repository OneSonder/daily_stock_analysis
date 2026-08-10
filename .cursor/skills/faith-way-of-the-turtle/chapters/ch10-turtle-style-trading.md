# Chapter 10: Turtle-Style Trading — Step by Step

## Core Idea
Keep it simple. Well-executed, time-tested trend systems beat fancy complexity. Backtests are imperfect but better than guessing — if you avoid overoptimization.

## Frameworks Introduced
- **Tested Turtle-style systems** (common portfolio + half-Turtle risk: 0.5% per ATR):
  - ATR Channel Breakout
  - Bollinger Breakout
  - Donchian Trend
  - Donchian Trend + Time Exit
  - Dual Moving Average (always in)
  - Triple Moving Average (slow-trend gated)
- **Backtesting necessity**: Past is the only data; computers test more rigorously than memory/charts.
- **Myth of the expert**: Pseudo-experts copy rigid rules without understanding limits.

## Key Concepts
- **ATR Channel Breakout**: Long if prior close > 350-MA + 7 ATR; short if < 350-MA − 3 ATR; exit on close back through MA.
- **Bollinger Breakout**: 350-MA ± 2.5 stdev channels; similar entry/exit logic.
- **Donchian Trend**: 20-day entry / 10-day exit breakouts + 25/350 EMA filter + 2-ATR stop.
- **Always-in dual MA**: Continuous long/short via fast/slow crossover.
- **Common test harness**: Liquid US futures portfolio; 1996–2006; volatility-normalized sizing.

## Mental Models
- Hold building blocks constant when comparing rule changes.
- Prefer experts who explain simply and know technique limits.
- Use sims to kill bad ideas cheaply before risking capital.

## Anti-patterns
- Rejecting all historical testing because "past won't repeat."
- Overoptimizing parameters until history looks perfect.
- Confusing knowledge of complex stats with wisdom about sample representativeness.

## Worked Example
Compare systems on identical markets/money-management/dates so differences isolate rule effects. Faith argues even discretionary traders are covertly using historical experience — simulation just makes that process explicit and falsifiable.

## Key Takeaways
1. Simple systems, disciplined execution.
2. Backtests are necessary tools with sharp edges.
3. Compare systems under controlled common settings.
4. Avoid pseudo-expert rigid dogma.
5. Results in Ch10 set up robustness lessons in later chapters.

## Connects To
- **Ch 9**: Building blocks used by these systems
- **Ch 11**: Why sims overstate future results
- **Ch 12–13**: Robust measurement and bulletproof portfolios
