# Chapter 11: Lies, Damn Lies, and Backtests

## Core Idea
Backtests overstate the future for structural reasons. Know the four discrepancy sources — trader effects, randomness, optimization paradox, overfitting — or become prey for charlatans and your own optimism.

## Frameworks Introduced
- **Trader effect**: Trading a known pattern changes the pattern (front-running, diluted edge).
- **Random effects**: Luck can create apparent excellence; track records alone can't separate luck from skill quickly.
- **Optimization paradox**: Choosing parameters (25 vs 30 MA) itself reduces predictive value of the backtest.
- **Overfitting / curve fitting**: Complexity tuned to history collapses on slight regime change.
- **Reversion to the mean ("lucky genes")**: Extreme past performance tends to normalize.

## Key Concepts
- **Observer/trader effect**: Measuring/exploiting a phenomenon alters it.
- **Anticipatory buying into known stops/opens**: Popular systems get hunted.
- **Illiquid markets amplify trader effects**: Thin books move on light volume.
- **Random system variance**: Coin-flip entries can show huge best/worst spread; add trend filter and averages rise but variance remains large.
- **Investor selection bias**: More lucky-average traders than unlucky-great traders in short track-record samples.
- **Time favors true skill**: Longer histories shrink lucky impostors.

## Mental Models
- Prefer proprietary timing details; public cookie-cutter systems get crowded.
- Distrust ads with "turn $5k into $1M / 90% accurate / no losing months."
- Evaluate process quality + sample design, not headline CAGR.

## Anti-patterns
- Buying vendor systems from glossy equity curves.
- Selecting managers solely on 5-year sparkling returns.
- Optimizing until every wiggle is explained.
- Ignoring that your own live fills won't match historical assumptions once others know the rule.

## Worked Example
Gold breakout stop run: knowing ACME buys 1,000 @ $410.50, predator lifts price into stops, dumps inventory for quick profit — breakout meaning corrupted vs historical sim. Also: Turtle-era order flow sometimes moved markets; Faith used occasional fake opposite limits (rare bluff) to reduce predictability — analogy to poker bluffing frequency.

## Key Takeaways
1. Four structural reasons sims ≠ live.
2. Crowding kills edges.
3. Luck masquerades as skill in short samples.
4. Optimization and complexity are predictive poison.
5. Build your own, keep it simple, stay skeptical.

## Connects To
- **Ch 12**: Robust testing methods and metrics
- **Ch 13**: Diversity/simplicity as defense
- **Ch 5**: Edge measurement before marketing claims
