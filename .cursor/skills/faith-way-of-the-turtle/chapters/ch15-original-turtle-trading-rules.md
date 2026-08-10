# Chapter 15: Original Turtle Trading Rules

## Core Idea
A complete mechanical system covers markets, sizing, entries, stops, exits, and tactics. Consistency and discipline beat publishing slightly better rules that nobody follows.

## Frameworks Introduced
- **Complete trading system checklist**: Markets · Position sizing · Entries · Stops · Exits · Tactics.
- **Volatility-adjusted units via N**: Size so 1N ≈ 1% equity risk unit.
- **System 1 / System 2 entries**: Dual breakout systems with skip rules.
- **Pyramiding / adding units**: Scale in on favorable moves at ½N intervals.
- **Turtle stops & exits**: Predefined ATR stops; breakout-based profit exits (psychologically hard).
- **Unit limits**: Portfolio risk ceilings by correlation and direction.

## Key Concepts
- **N**: 20-day ATR (true range EMA/average); True Range = max(H−L, H−PDC, PDC−L).
- **Dollar volatility**: N × dollars per point.
- **Unit size**: (1% of equity) / dollar volatility → contracts (truncate).
- **Markets**: Liquid US futures; Turtles excluded grains (Dennis at exchange limits) and meats (pit corruption concerns); discretionary skip only if never trading that market inconsistently.
- **Entries (classic)**: System 1 — 20-day breakout (skip if last breakout was winner); System 2 — 55-day breakout always. Add units every ½N.
- **Stops**: Typically 2N risk from entry (Faith notes variants); alternative whipsaw stop strategies discussed.
- **Exits**: System 1 — 10-day opposite breakout; System 2 — 20-day opposite breakout (hard exits that give back open profit).
- **Tactics**: Prefer limits; handle fast markets; simultaneous signals; buy strength/sell weakness; roll expiring contracts carefully.
- **Unit limits**: 4 single market · 6 closely correlated · 10 loosely correlated · 12 single direction (long or short).

## Mental Models
- Automate decisions so fear/courage aren't inverted under P&L stress.
- Equalize risk across markets so diversification is real.
- Predefine loser exits before entry — no negotiation mid-loss.

## Anti-patterns
- Incomplete "systems" that specify entries but not winner exits.
- Oversizing small accounts until unit granularity destroys diversification.
- Inconsistent market participation (skipping only when scared).
- Moving stops away from pain.

## Worked Example
Heating oil HO03H: with N≈0.0141, $1M account, $42,000 per point → unit ≈ 16 contracts after truncation. Units built so each market's daily volatility maps to ~1% equity, enabling comparable bets across crude, FX, rates, metals.

## Key Takeaways
1. Completeness beats clever partial rules.
2. Size by N; cap by unit limits.
3. Dual breakout systems + pyramiding define Turtle entry geometry.
4. Stops/exits must be preset and obeyed.
5. Discipline is the unpublished alpha.

## Connects To
- **Ch 5 / 8 / 9 / 10**: Theory behind these rules
- **Ch 4**: Why skipping signals after losers is fatal
- **Ch 14**: Psychology required to follow them
