# Chapter 9: Turtle-Style Building Blocks

## Core Idea
Don't hunt exotic indicators. Master basic trend building blocks — breakouts, moving averages, volatility channels, time exits, simple lookbacks — and use them to detect shifts between market states.

## Frameworks Introduced
- **Building blocks**: Tools that estimate when a trend may have started/ended (odds, not certainty).
- **Market-state awareness**: Stable/quiet, stable/volatile, trending/quiet, trending/volatile — systems should avoid unfavorable states.
- **Simplicity over novelty**: Fancy indicators rarely beat well-executed basics.

## Key Concepts
- **Breakouts**: Price beyond N-day high/low; fewer days = shorter horizon.
- **Moving averages**: SMA/EMA of price; crossovers as trend-start candidates.
- **Volatility channels**: MA ± k·volatility (ATR or stdev) — excursions signal trend onset.
- **Time-based exits**: Exit after fixed days; can cut late-trend giveback earlier than lagging indicators.
- **Simple lookbacks**: Compare current price to price D days ago (± ATR buffer).

## Mental Models
- Any competent trend block can be tuned fast/slow to similar behavior — stop searching for magic.
- Combine blocks (e.g., breakout + MA trend filter) rather than stacking complexity.
- Casino math: slight odds favor + volume of bets can be enough.

## Anti-patterns
- Magazine-indicator hopping and nuclear-powered curve-fit toys.
- Using complex MA variants that mainly increase overfitting risk.
- Expecting any block to "always work."

## Worked Example
20-day vs 70-day EMA: shorter MA tracks closer; crossover can mark early uptrend entry. Volatility channel: price mostly inside MA±band until a sustained breach — then MA turns and follows. Breakouts + MA filter (Donchian Trend style) outperform naked complexity for Turtle-style goals.

## Key Takeaways
1. Basics first; execution > novelty.
2. Tune horizon via lookback length.
3. Blocks estimate odds of state change.
4. Combine simple filters instead of inventing indicators.
5. Complexity increases curve-fit risk.

## Connects To
- **Ch 10**: Concrete systems built from these blocks
- **Ch 5**: Why filtered breakouts have edge
- **Ch 11**: Optimization/overfitting dangers
