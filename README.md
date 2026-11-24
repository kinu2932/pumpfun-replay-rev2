# Pump.fun Replay Sprint — Paper Bot, Real Ranking (rev2)

A revised entry for the make.fun competition
`u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122`
("Pump.fun Replay Sprint — Paper Bot, Real Ranking", harness
`pumpfun-replay/v2`, paper trading only — no real SOL).

## Strategy in one paragraph

**Dispersed Pullback Rider.** The dev-window forensics say every
chase-the-pump family loses after execution costs (2-slot latency,
~2.6–4.6% round-trip cost, 1%-of-reserve buy cap). The least-bad signal
found was the pullback rider: a coin bursts (5+ buys, ≥0.5 SOL in 30
slots), pulls back 8–25% off its burst high, then resumes with a buy
≥0.2 SOL → buy 0.03 SOL. Exits: TP +40% / SL −12%, max hold 120 slots,
exit on dev-sell / big sell ≥2 SOL, and — the exit that matters most — a
**fade exit**: sell when net flow over 90 slots drops below −0.75 SOL.
Buy slippage is tight (100 bps): a fill that ran away becomes a free
rejection instead of a loss. See [STRATEGY.md](STRATEGY.md) for the full
forensics, the family scoreboard, and every number.

## Files

- `main.py` — the bot (stdlib only, deterministic). All five tested
  signal families live in the code; only the pullback rider ships ON.
  The other four (ignition scalp, late-curve rider, launch sniper,
  completion rider) were built, swept and measured as consistent losers
  on this data, so they ship OFF and documented as tested-and-rejected.
- `vendor/makefun_bot.py` — the kit SDK, copied byte-identical.
- `STRATEGY.md` — forensics, sweeps, OOS, stress, and the honest verdict.

## Local validation

```sh
# official grading, process driver (no Docker on this machine)
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . \
  --driver process --worktree --json
# + stress copies
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . \
  --driver process --worktree --stress 8 --json
```

Official `grade-local` (process driver, 2 runs, action logs matched):

| metric | rev2 | old bot |
|---|---|---|
| net PnL (dev) | −0.054 SOL | +0.193 SOL |
| win rate | 22.4% | 20.8% |
| max drawdown | 1.18% | 0.63% |
| round trips / coins | 183 / 145 | 24 / 24 |
| fills | 366 | 48 |
| top-3 share of gains (official) | 34.9% | 94.0% |
| net PnL without top-3 | −0.171 SOL | −0.076 SOL |

Read the table honestly: the old bot's +0.193 SOL was a concentrated
lottery win on one window (94% of gains from 3 coins; its own stress
median was −0.04 SOL with 6 of 8 copies losing). Rev2 spreads 183 trips
over 145 coins and still loses a little on dev (−0.054 SOL, ≈ −0.0003
SOL per trip) — the signal edge is ~zero after costs, and no family
tested in this revision turned positive on dev. See STRATEGY.md for
the OOS quarters, the stress copies, and what that means for submission.

## Reproduce the research sim

The research harness that drove the sweeps lives outside this repo
(`/tmp/research/sim.py` — a re-implementation of the kit's documented
market model, validated to reproduce the kit equal-weight example's
official grade-local exactly). It is not part of the submission.
