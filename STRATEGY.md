# STRATEGY.md — Pump.fun Replay Sprint rev2

Competition: `u-jackxyz72-pump-fun-replay-sprint-paper-bot-0b809122`
("Pump.fun Replay Sprint — Paper Bot, Real Ranking", harness
`pumpfun-replay/v2`, paper trading, capital 10 SOL, max 5 open positions,
1% of real reserve per buy, 2-slot latency, ~125 bps curve fees + 105,000
lamport tx fee per order). Dev window: 2026-11-02 03:09 UTC → 2026-11-03
03:09 UTC, 403,213 slots, 126,801 trades, 1,222 mints, 35 completions.

## 0. Verdict up front (read this first)

Rev2 **does not achieve a positive expectancy**. No signal family tested
in this revision turned positive on the dev window, on any out-of-sample
quarter, or on any stress copy. The honest numbers:

| check | rev2 | target | old bot |
|---|---|---|---|
| dev net PnL (official grade-local) | −0.054 SOL | > 0 | +0.193 SOL |
| dev net PnL (research sim) | −0.075 SOL | > 0 | — |
| win rate | 22.4% | > 20.8% | 20.8% |
| max drawdown | 1.18% | small | 0.63% |
| round trips / distinct coins | 183 / 145 | diversified | 24 / 24 |
| top-3 share of gains (official) | 34.9% | ≪ 94% | 94.0% |
| net PnL without top-3 | −0.171 SOL | — | −0.076 SOL |
| OOS quarters (4× 6h, fresh 10 SOL) | +0.007 / −0.082 / −0.013 / −0.043 | ≥ 0 | — |
| stress median (8 copies) | −0.242 SOL | ≥ breakeven | −0.04 SOL |
| stress copies losing | **8 / 8** | minority | 6 / 8 |

What rev2 **did** fix vs the old bot: concentration (top-3 share of
gains 94% → 34.9%; 145 coins instead of 24; no coin dominates) and
process (regime filter tested and rejected with evidence, 4-quarter OOS,
TP/SL grid, tight-slippage discipline, duplicate-sell/zero-token bugs
fixed). What it did **not** fix: expectancy. The old bot's +0.193 SOL
was a concentrated lottery win on one window; rev2's −0.054 SOL is a
diversified small loss. Neither has a demonstrated edge — and on the
stress copies rev2 loses MORE (−0.24 median) than the old bot (−0.04),
because 183 trips bleed 7.6× the fees on reshuffled windows where the
signals are noise. **Recommendation to the coordinator: HOLD — do not
submit on expectancy grounds.** The final ranking is on a fresh 24h
window; rev2's expected value there is negative. Submit only if the
$2 prize is treated as a free lottery ticket.

## 1. Forensics — why every chase-the-pump family loses

Measured on the dev window before any bot was written:

- Launch base rates: within 600 slots of creation, 15.0% of coins ≥2x,
  7.4% ≥3x, 4.3% ≥5x, 2.5% ≥10x (n=1,123). Only 35/1,222 coins complete.
  Buying every launch loses ≈ −0.45 per unit stake even with perfect
  max capture — 85% of coins die and the 2.5% of 10x coins do not pay
  for them.
- Burst (4+ buys, ≥0.3 SOL in 5 slots): forward mean +1.86% at H=10,
  +0.96% at H=30, −3.73% at H=300. The move is mostly over by entry.
- Pullback-after-burst (burst, then −5..−15% off the 30-slot high, then
  a buy ≥0.05 SOL): H=30 mean +1.84%, median +0.89%, 42.5% beat
  ~2.9% round-trip costs — the best risk/reward measured.
- Completion riding looks great in analysis (from rq≥30 crossing, 33%
  complete; completers +149% mean) but fails in execution: the path to
  completion is so volatile that any stop that protects capital exits
  the winners early, and holding through needs −50–80% drawdowns on
  the 67% that never complete. Pure-hold tests: −6.79 SOL (rq≥30),
  −2.52 SOL (rq≥40).
- Round-trip cost ≈ 2.9% of stake at 0.05 SOL (1.25% curve fees each
  way + 2×105k lamports tx). The best measured signal edge (+1.8%
  forward mean) is smaller than the cost. **That gap is structural:**
  no tested signal clears costs, and the leaderboard's top bots
  (+12.5 / +5.2 / +4.0 SOL, 60–249 coins, 2–4.3 fills/coin) must be
  doing something this revision did not find — most plausibly scaling
  into winners (pyramiding) or a signal family not in this set. Both
  were attempted here (pyramiding: worse; see §3).

## 2. Winner-profile-first (leaderboard, 24 Nov ~09:37 WIB, 370 entries)

- #1 quick-gecko-13-1579 "Overhang Exhaustion & Dispersed Ownership
  Bot": +12.52 SOL, return 1.25, 90% low +4.15 SOL, DD 14.1%, Sharpe
  0.456, 259 fills, 60 coins, 5,045 counterparties. Broad-based edge
  (low bound +4.15 SOL) — not one lucky coin.
- #2 nimble-stork-27-4994 "early-accumulation with ladder exits":
  +5.16 SOL, 249 coins, 760 fills, low −2.17 SOL.
- #3 lucky-harbor-60: +4.00 SOL, 205 coins, 481 fills.
- #4 kh43 "SolSurge": +3.76 SOL, 100 coins. #5 illyash22 "Late-curve
  runner with wallet-farm filter": +3.29 SOL, 37 coins. #6 ken-biss
  "Breakout Rider": +3.25 SOL, 47 coins, DD 3.7%, Sharpe 0.439.
- Pattern: the winners trade MANY coins with multiple fills per coin —
  systematic, not single-coin lottery. Final ranking is on a FRESH 24h
  window after the deadline, so overfitting to dev is the trap.

## 3. Family scoreboard (research sim, full dev window)

All numbers are net PnL in SOL on the dev window unless noted. The sim
is a from-scratch re-implementation of the kit's documented market
model; it reproduces the kit equal-weight example's official
grade-local EXACTLY (−0.019283154 SOL).

| family | best config found | PnL | win rate | trips |
|---|---|---|---|---|
| D pullback rider (**ships ON**) | drop 8–25%, resume ≥0.2 SOL, TP+40%/SL−12%, hold 120, fade −0.75 SOL/90 slots, stake 0.03, buy-slip 100 bps | −0.075 | 21.1% | 180 |
| A ignition scalp | no-regime, fade on, slip 1500 | −0.136 | 20.2% | 238 |
| A + D combined | — | −0.162 | 23.5% | 264 |
| C launch sniper | TP+40%/SL−10%/H300, no fade/dev-exit | −0.544 | 15.4% | 376 |
| E completion rider (crossing) | thresh 40, trail 35% | −0.586 | 13.1% | 130 |
| E completion rider (confirm) | base | −2.091 | 16.4% | 165 |
| E pure-hold | thresh 30, no exits | −6.794 | 12.3% | 162 |
| B late-curve rider | base | −0.467 | 9.2% | — |
| D + pyramiding (add 0.05 @ +15%) | — | −0.484 | 22.2% | 180 |
| D + trail 30%/15% | — | −0.322 | 25.1% | 179 |

Why D won the internal contest: it is the only family whose exits
(fade + tight slippage + short hold) keep average loss small
(−0.0029 SOL/trip) while keeping 21% win rate. The fade exit is the
single most valuable rule: without it D is −0.318 with avg hold 107
slots; with fade −0.75 SOL/90 slots it is −0.075 with avg hold 39.

## 4. TP/SL asymmetry (family D grid, buy-slip 100)

| TP / SL / hold | PnL | win rate |
|---|---|---|
| +40% / −12% / 300 | −0.083 | 23.5% |
| +60% / −12% / 600 | −0.129 | 21.4% |
| +25% / −8% / 300 | −0.125 | 21.7% |
| +40% / −8% / 300 | −0.118 | 21.7% |
| +40% / −12% / 120 | −0.124 | 23.8% |
| +100% / −12% / 600 | −0.129 | 22.0% |

Exits barely matter — entries are the binding constraint. Chosen:
**TP +40% / SL −12% / hold 120** (with the fade exit doing the real
work). Asymmetry ratio 3.3:1 was picked for healthiest expectancy per
trip (−0.00041 SOL/trip), not highest total PnL.

## 5. Regime / volatility filter — tested, REJECTED

Family A with vs without the breadth filter (share of recently-traded
coins with positive 60-slot net flow):

| | full window | OOS total (4 quarters) |
|---|---|---|
| A, regime OFF | −0.136 | −0.434 |
| A, regime ON | worse in 3 of 4 quarters | −0.477 |

The filter removes good entries along with bad ones and never pays for
itself. It ships OFF (`regime_on: false`). The comparison the brief
asked for is the evidence above.

## 6. Out-of-sample (4 quarters of the dev window, fresh 10 SOL each)

Final defaults (D only): W0 **+0.007** (26.5% WR, 34 trips),
W1 −0.082 (13.2%), W2 −0.013 (24.6%), W3 −0.043 (22.8%).
Total −0.131, mean −0.033/window, DD ≤0.8% per window. No window
blows up; none is convincingly positive either. (Quarters truncate
holds at boundaries and restart cross-boundary coins from launch
reserves, so quarter PnLs are pessimistic/noisy by construction — read
them as a robustness signal, not a PnL estimate.)

## 7. Stress test (official grade-local --stress 8)

Copies (rebuilt from blocks of the dev window's own trades):
−0.24, −0.15, −0.09, −0.25, −0.18, −0.25, −0.25, −0.23 SOL.
Median **−0.242 SOL**, p10 −0.251, p90 −0.086, **8/8 copies losing**,
0 failed, dev rank 8/9 (dev was the best of the nine runs).
Warnings: "dev score is above 90% of the rebuilt copies" and "half or
more of the rebuilt copies lost money". **Target missed** (median ≥
breakeven, majority not losing). Mechanism: on reshuffled windows the
signals are noise, so 183 trips × ~0.0013 SOL/trip of costs bleed
more than the old bot's 24 trips did (old stress median −0.04, 6/8
losing). Diversification into more trips amplifies fee bleed when
there is no edge.

## 8. Official grade-local (process driver, 2 runs)

Action logs matched byte-for-byte (single action_log_sha256
`44edaf5e…`), status finished, dataset sha256 `b661ceee…`.
Net PnL −54,107,893 lamports (−0.054 SOL), return −0.54%, Sharpe
−0.118, Sortino −0.186, max DD 1.18%, win rate 22.4%, 183 round trips,
366 fills, 145 distinct mints, 80 rejected (79 max-slippage — the
tight 100 bps buy slip working as designed), 6 failed txs, fees
0.133 SOL, tx fees 0.039 SOL. Eligibility: `ranked: true`,
`prize_eligible: false` (reasons: `no_transcripts`, `cost_unpriced`
— Turn 2's bundle — and `below_hold_cash`, i.e. dev PnL < 0).
Concentration: top-3 gross gains 0.335 SOL, share of gains 34.9%,
net without top-3 −0.171 SOL.

## 9. What changed vs the old bot, and why rev2 is more robust anyway

- Old: 1 signal, 24 trips, 24 coins, top-3 = 94% of gains.
  Rev2: pullback-only core + 4 documented rejected families, 183
  trips, 145 coins, top-3 = 34.9% of gains.
- Old: aggressive trailing stop, no fade discipline, wide slippage.
  Rev2: fade exit (flow turns → out), tight 100 bps buy slippage
  (bad fills reject free), 120-slot max hold, dev-sell + big-sell
  exits, 0.03 SOL stakes (smaller fee share per trip).
- Old: no OOS / regime evidence. Rev2: 4-quarter OOS, regime
  with-vs-without, TP/SL grid, 8-copy stress — all reported, including
  the failures.
- Robustness here means: small DD (1.18%), no window blows up, no
  single coin can sink or save the bot. It does NOT mean profitable —
  and this document does not pretend otherwise.

## 10. Open threads for Turn 2 / Hermes

- The missing edge: leaderboard top-1's broad +4.15 SOL low bound
  implies a real signal this revision did not find. Best remaining
  hypotheses: (a) scaling into winners with a trailing stop that
  survives path volatility (attempted once — worse); (b) a
  creator/wallet-quality filter (top-5 mentions a "wallet-farm
  filter"); (c) exhaustion-after-overhang entries (top-1's title).
  Any of these is a new research cycle, not a tweak.
- If submitted despite the verdict, the entry is at least cheap to
  lose with: DD 1.2%, no concentration, deterministic.
