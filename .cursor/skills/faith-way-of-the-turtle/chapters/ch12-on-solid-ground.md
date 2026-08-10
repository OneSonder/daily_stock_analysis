# Chapter 12: On Solid Ground

## Core Idea
You can't get precise future forecasts from history — but a **rough, statistically honest estimate** is enough edge to get rich if you test the right way.

## Frameworks Introduced
- **Sampling inference**: Past trades are a sample; validity needs size + representativeness.
- **Robust statistics mindset**: Prefer estimators that don't jump when a few trades/dates change.
- **RAR% (Regressed Annual Return)**: Slope of best-fit equity line — less endpoint-sensitive than CAGR%.
- **R-cubed (RRRR)**: Robust risk/reward using RAR% over length-adjusted average of large drawdowns.
- **Robust Sharpe**: RAR% / annualized stdev of monthly returns.
- **Stress tools**: Parameter scrambling, rolling optimization windows, Monte Carlo, alternative universes.

## Key Concepts
- **Representativeness > raw trade count**: Thousands of trades from two quiet weeks ≠ valid sample.
- **Non-robust classic metrics**: CAGR%, MAR, Sharpe jump when start/end dates shift a few months.
- **Average max drawdown**: Mean of top-five drawdowns (severity + duration via length adjustment).
- **Lucky systems / overfitting diagnostics**: Scramble params / roll windows to see stability.
- **Monte Carlo & alternative trading universes**: Explore outcome ranges beyond one historical path.

## Mental Models
- Poll-at-the-Democratic-convention analogy: recent-only tests are biased samples.
- Prefer metrics stable under small data perturbations.
- Treat every backtest as a rough map, not a GPS.

## Anti-patterns
- Judging systems by single CAGR/MAR/Sharpe on one date window.
- Paper-trading only the latest regime.
- Ignoring that rules applying to few events have weak statistical support even in long tests.

## Worked Example
Triple MA: original window 43.2% / MAR 1.39 / Sharpe 1.25; shift dates a few months → 46.2% / 1.61 / 1.37. RAR% barely moves (54.67% → 54.78%). Same sensitivity pattern for ATR Channel Breakout. Hence Faith's push to RAR% and R-cubed.

## Key Takeaways
1. History gives rough estimates — useful if honest.
2. Demand representative multi-state samples.
3. Prefer robust metrics (RAR%, R-cubed, robust Sharpe).
4. Stress-test parameter and path dependency.
5. Solid ground = method quality, not curve beauty.

## Connects To
- **Ch 11**: Failure modes these methods address
- **Ch 7**: Why risk metrics matter
- **Ch 13**: Robust portfolios beyond single-system perfection
