"""Pump.fun Replay Sprint — rev2 entry.

Built from scratch from the kit + competition requirements only.

Approach: "Dispersed Pullback Rider". The dev-window forensics say every
chase-the-pump family loses after execution (2-slot latency + ~2.6-4.6%
round-trip cost + 1%-of-reserve buy cap). The least-bad, most robust signal
found was the pullback rider: a coin bursts, pulls back 8-25% off its burst
high, then resumes with a strong buy. Small stakes (0.05 SOL), tight buy
slippage (100 bps — a bad fill becomes a free rejection instead of a loss),
TP +40% / SL -12%, max hold 300 slots. No family is left on by default
except the pullback rider: ignition scalp, launch sniper, late-curve rider
and completion rider were all built, swept and measured — each is a
consistent loser on this data — so they ship OFF, documented here as
tested-and-rejected rather than silently deleted.

Stdlib only. Deterministic: no clock, no env, no unseeded randomness.
Diagnostics go to stderr only.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bot  # noqa: E402

LAMPORTS = 1_000_000_000
BPS = 10_000

DEFAULTS = {
    # --- family toggles (only D ships on) ---
    "fam_a_on": False,  # ignition scalp (burst in 5 slots)
    "fam_b_on": False,  # late-curve rider (rq >= 40)
    "fam_c_on": False,  # launch sniper (age 0-3 slots)
    "fam_d_on": True,   # pullback rider (CORE)
    "fam_e_on": False,  # completion rider (rq crossing 30)
    # --- global ---
    "max_entries": 2,          # max entries per mint per run
    "buy_slip_bps": 100,       # tight: bad fills reject free instead of losing
    "sell_slip_bps": 10000,
    "regime_on": False,        # breadth filter for family A; measured HURTS, off
    # --- A: ignition scalp ---
    "burst_min_buys": 4, "burst_min_sol": 0.3, "burst_win": 5,
    "ignite_quiet": 120,       # no prior burst in this many slots
    "stake_a_sol": 0.05, "tp_a_bps": 1000, "sl_a_bps": 600, "max_hold_a": 120,
    "fade_a_net_sol": 0.5, "fade_a_win": 60,
    # --- B: late-curve rider ---
    "late_rq_sol": 40.0, "late_min_buys": 3, "late_win": 10,
    "stake_b_sol": 0.29, "tp_b_bps": 3000, "sl_b_bps": 1000, "max_hold_b": 1000,
    # --- C: launch sniper ---
    "snipe_max_age": 3, "snipe_max_dev_sol": 2.5, "snipe_max_buyers": 3,
    "snipe_min_rq_sol": 0.3,
    "stake_c_sol": 0.05, "tp_c_bps": 20000, "sl_c_bps": 3000, "max_hold_c": 20000,
    "trail_arm_c_bps": 3000, "trail_c_bps": 2000,
    "fade_c_net_sol": 1000.0, "exit_c_on_dev_sell": False,
    # --- D: pullback rider (CORE) ---
    "pull_burst_min_buys": 5, "pull_burst_min_sol": 0.5, "pull_burst_win": 30,
    "pull_drop_min_bps": 800, "pull_drop_max_bps": 2500,
    "pull_resume_sol": 0.2, "pull_burst_stale": 600,
    "stake_d_sol": 0.03, "tp_d_bps": 4000, "sl_d_bps": 1200, "max_hold_d": 120,
    "fade_d_net_sol": 0.75, "fade_d_win": 90,
    "exit_d_on_dev_sell": True,
    "add_d_sol": 0.0, "add_d_at_bps": 1500, "add_d_max": 1,
    "trail_arm_d_bps": 0, "trail_d_bps": 0,
    # --- E: completion rider ---
    "ride_cross_sol": 30.0, "ride_cross_on": True,
    "ride_flow_win": 30, "ride_flow_min_sol": 0.0,
    "stake_e_sol": 0.29, "add_e_sol": 0.21, "max_stake_e_sol": 0.50,
    "sl_e_bps": 1500, "trail_arm_e_bps": 2000, "trail_e_bps": 1500,
    "max_hold_e": 50000, "fade_e_net_sol": 5.0, "fade_e_win": 120,
    "exit_e_on_dev_sell": False,
}


def _px(curve):
    """Current price in lamports per token (virtual quote / virtual token)."""
    vt = curve.virtual_token_reserves
    if vt <= 0:
        return 0.0
    return curve.virtual_quote_reserves / vt


def create_bot(params=None):
    P = dict(DEFAULTS)
    if params:
        P.update(params)

    # Per-mint trackers, built from the event stream.
    T = {}

    def tracker(mint):
        t = T.get(mint)
        if t is None:
            t = {
                "trades": [],      # (slot, signed_sol_lamports, is_buy, px, user)
                "creator": None, "created_slot": None,
                "dev_sold": False, "dev_buy_sol": 0.0,
                "buyers": set(), "entries": 0,
                "prev_rq": 0, "burst_slot": -10**9, "burst_high": 0.0,
                "last_burst_slot": -10**9,
            }
            T[mint] = t
        return t

    # Open positions, keyed by mint.
    POS = {}

    def flow_over(t, now, win):
        lo = now - win
        tot = 0
        for (s, sgn, _b, _p, _u) in t["trades"]:
            if s > lo:
                tot += sgn
        return tot / LAMPORTS

    def buys_over(t, now, win):
        lo = now - win
        n = 0
        tot = 0.0
        for (s, sgn, is_buy, _p, _u) in t["trades"]:
            if s > lo and is_buy:
                n += 1
                tot += sgn / LAMPORTS
        return n, tot

    def regime_ok(state, now):
        # Breadth: share of coins traded in the last 60 slots whose net flow
        # over that window is positive. Off by default (measured: hurts).
        if not P["regime_on"]:
            return True
        good = 0
        tot = 0
        for mint, t in T.items():
            if not t["trades"] or t["trades"][-1][0] <= now - 60:
                continue
            tot += 1
            if flow_over(t, now, 60) > 0:
                good += 1
        return tot == 0 or good * 2 >= tot

    def on_batch(state, batch):
        now = state.slot
        orders = []
        traded = []

        # ---- fold this batch's events into trackers ----
        for e in batch.get("events", []):
            kind = e.get("event")
            mint = e.get("mint")
            if mint is None:
                continue
            t = tracker(mint)
            if kind == "CreateEvent":
                t["creator"] = e.get("creator")
                t["created_slot"] = int(e.get("slot", now))
                t["prev_rq"] = 0
                if mint not in traded:
                    traded.append(mint)
            elif kind == "TradeEvent":
                is_buy = bool(e.get("is_buy"))
                sol = int(e.get("sol_amount", 0))
                signed = sol if is_buy else -sol
                vt = int(e.get("virtual_token_reserves", 0))
                vq = int(e.get("virtual_sol_reserves", 0))
                px = (vq / vt) if vt > 0 else 0.0
                user = e.get("user")
                t["trades"].append((int(e.get("slot", now)), signed, is_buy, px, user))
                # prune trades older than 2000 slots (windows need <= 600)
                cut = now - 2000
                while len(t["trades"]) > 1 and t["trades"][0][0] < cut:
                    t["trades"].pop(0)
                if t["creator"] is not None and user == t["creator"]:
                    if is_buy:
                        t["dev_buy_sol"] += sol / LAMPORTS
                    else:
                        t["dev_sold"] = True
                elif is_buy and user:
                    t["buyers"].add(user)
                if not is_buy and sol >= 2 * LAMPORTS:
                    t["big_sell"] = True
                if not is_buy and sol >= 5 * LAMPORTS:
                    t["big_sell_e"] = True
                if mint not in traded:
                    traded.append(mint)
            elif kind == "CompleteEvent":
                t["complete"] = True
                if mint not in traded:
                    traded.append(mint)

        # ---- sync positions with the account ----
        held = {}
        for p in state.account.get("positions", []):
            mint = p["mint"]
            tokens = int(p["token_amount"])
            cost = int(p["cost_lamports"])
            if tokens <= 0 or cost <= 0:
                continue
            held[mint] = (tokens, cost)
        for mint in list(POS):
            if mint not in held:
                # Keep the record while its buy is still pending (fill lands
                # 2 slots after the decision); drop it only once the mint is
                # truly gone with no buy in flight (force-close / flatten).
                if not any(p.order["mint"] == mint and p.order["side"] == "buy"
                           for p in state.pending.values()):
                    POS.pop(mint, None)
        for mint, (tokens, cost) in held.items():
            entry_px = cost / tokens
            cur = state.curves.get(mint)
            cur_px = _px(cur) if cur is not None else entry_px
            pos = POS.get(mint)
            if pos is None:
                POS[mint] = {"family": None, "entry_px": entry_px, "entry_slot": now,
                             "peak_px": cur_px, "adds": 0, "tokens": tokens}
            else:
                # Keep the DECISION price as the exit basis (set when the
                # entry was decided); the fill lands 2 slots later at a
                # slightly worse price, and keying stops off the signal
                # price exits both sides a touch earlier. Only the token
                # count and the peak track the live account/market.
                pos["tokens"] = tokens
                if cur_px > pos["peak_px"]:
                    pos["peak_px"] = cur_px

        def want_sell(mint, pos, fam):
            """Exit rules for one open position. Returns True to sell all."""
            cur = state.curves.get(mint)
            if cur is None:
                return False
            ratio = _px(cur) / pos["entry_px"] if pos["entry_px"] > 0 else 1.0
            age = now - pos["entry_slot"]
            t = T.get(mint) or tracker(mint)
            if fam == "A":
                if ratio >= 1 + P["tp_a_bps"] / BPS or ratio <= 1 - P["sl_a_bps"] / BPS:
                    return True
                if age >= P["max_hold_a"]:
                    return True
                if t.get("dev_sold"):
                    return True
                if flow_over(t, now, P["fade_a_win"]) < -P["fade_a_net_sol"]:
                    return True
                return False
            if fam == "B":
                if ratio >= 1 + P["tp_b_bps"] / BPS or ratio <= 1 - P["sl_b_bps"] / BPS:
                    return True
                if age >= P["max_hold_b"]:
                    return True
                return bool(t.get("dev_sold"))
            if fam == "C":
                if ratio >= 1 + P["tp_c_bps"] / BPS or ratio <= 1 - P["sl_c_bps"] / BPS:
                    return True
                if age >= P["max_hold_c"]:
                    return True
                if P["exit_c_on_dev_sell"] and t.get("dev_sold"):
                    return True
                if flow_over(t, now, 120) < -P["fade_c_net_sol"]:
                    return True
                if P["trail_arm_c_bps"] > 0 and pos["peak_px"] >= pos["entry_px"] * (1 + P["trail_arm_c_bps"] / BPS):
                    if _px(cur) <= pos["peak_px"] * (1 - P["trail_c_bps"] / BPS):
                        return True
                return False
            if fam == "D":
                if ratio >= 1 + P["tp_d_bps"] / BPS or ratio <= 1 - P["sl_d_bps"] / BPS:
                    return True
                if age >= P["max_hold_d"]:
                    return True
                if P["exit_d_on_dev_sell"] and t.get("dev_sold"):
                    return True
                if t.get("big_sell"):
                    return True
                if flow_over(t, now, P["fade_d_win"]) < -P["fade_d_net_sol"]:
                    return True
                if P["trail_arm_d_bps"] > 0 and pos["peak_px"] >= pos["entry_px"] * (1 + P["trail_arm_d_bps"] / BPS):
                    if _px(cur) <= pos["peak_px"] * (1 - P["trail_d_bps"] / BPS):
                        return True
                return False
            if fam == "E":
                if ratio <= 1 - P["sl_e_bps"] / BPS:
                    return True
                if age >= P["max_hold_e"]:
                    return True
                if P["exit_e_on_dev_sell"] and t.get("dev_sold"):
                    return True
                if t.get("big_sell_e"):
                    return True
                if flow_over(t, now, P["fade_e_win"]) < -P["fade_e_net_sol"]:
                    return True
                if pos["peak_px"] >= pos["entry_px"] * (1 + P["trail_arm_e_bps"] / BPS):
                    if _px(cur) <= pos["peak_px"] * (1 - P["trail_e_bps"] / BPS):
                        return True
                return False
            return False

        def buy_order(mint, stake_sol):
            """Build a buy order capped by the 1%-of-reserve rule and cash."""
            cap = state.max_buy_lamports(mint)
            if cap <= 0:
                return None
            amt = int(stake_sol * LAMPORTS)
            amt = min(amt, cap)
            free = state.free_cash_lamports() - state.tx_fee_lamports()
            if free <= 0:
                return None
            amt = min(amt, free)
            if amt < int(0.01 * LAMPORTS):
                return None
            return {"side": "buy", "mint": mint, "quote_lamports": str(amt),
                    "max_slippage_bps": int(P["buy_slip_bps"]),
                    "client_id": state.client_id()}

        def sell_order(mint, tokens):
            return {"side": "sell", "mint": mint, "token_amount": str(tokens),
                    "max_slippage_bps": int(P["sell_slip_bps"]),
                    "client_id": state.client_id()}

        # ---- exits first (free slots for entries) ----
        for mint, pos in list(POS.items()):
            if pos["tokens"] <= 0:
                continue  # buy not filled yet; nothing to sell
            if any(p.order["mint"] == mint and p.order["side"] == "sell"
                   for p in state.pending.values()):
                continue  # sell already in flight; don't double-sell
            fam = pos["family"] or ("D" if P["fam_d_on"] else "A")
            if want_sell(mint, pos, fam):
                o = sell_order(mint, pos["tokens"])
                if o is not None:
                    orders.append(o)
                    POS.pop(mint, None)

        # ---- D pyramiding: one add on a proven winner ----
        if P["fam_d_on"] and P["add_d_sol"] > 0:
            for mint, pos in list(POS.items()):
                if pos["family"] != "D" or pos["adds"] >= P["add_d_max"]:
                    continue
                cur = state.curves.get(mint)
                if cur is None:
                    continue
                ratio = _px(cur) / pos["entry_px"] if pos["entry_px"] > 0 else 1.0
                if ratio < 1 + P["add_d_at_bps"] / BPS:
                    continue
                if any(p.order["mint"] == mint and p.order["side"] == "buy"
                       for p in state.pending.values()):
                    continue
                if state.committed_position_count() >= state.hello["caps"]["max_open_positions"]:
                    continue
                o = buy_order(mint, P["add_d_sol"])
                if o is not None:
                    orders.append(o)
                    pos["adds"] += 1

        # ---- entries ----
        slots_left = state.hello["caps"]["max_open_positions"] - state.committed_position_count()
        if slots_left > 0 and traded:
            for mint in traded:
                if len(orders) >= 16 or slots_left <= 0:
                    break
                cur = state.curves.get(mint)
                if cur is None or cur.complete:
                    continue
                if mint in POS:
                    continue
                if any(p.order["mint"] == mint and p.order["side"] == "buy"
                       for p in state.pending.values()):
                    continue
                t = T[mint]
                if t["entries"] >= P["max_entries"]:
                    continue
                if t.get("dev_sold"):
                    continue
                rq = cur.real_quote_reserves / LAMPORTS

                # Family E: completion rider — crossing-based entry.
                if P["fam_e_on"]:
                    prev = t["prev_rq"]
                    crossed = prev < P["ride_cross_sol"] * LAMPORTS <= cur.real_quote_reserves
                    if crossed and flow_over(t, now, P["ride_flow_win"]) > P["ride_flow_min_sol"] \
                            and not t.get("big_sell_e"):
                        o = buy_order(mint, P["stake_e_sol"])
                        if o is not None:
                            orders.append(o)
                            t["entries"] += 1
                            POS[mint] = {"family": "E", "entry_px": _px(cur),
                                         "entry_slot": now, "peak_px": _px(cur),
                                         "adds": 0, "tokens": 0}
                            slots_left -= 1
                            continue
                    elif not P["ride_cross_on"]:
                        # confirm mode: already mature, still flowing in
                        if rq >= P["ride_cross_sol"] and flow_over(t, now, 60) > 1.0:
                            if len(t["buyers"]) >= 8 and not t.get("big_sell_e"):
                                o = buy_order(mint, P["stake_e_sol"])
                                if o is not None:
                                    orders.append(o)
                                    t["entries"] += 1
                                    POS[mint] = {"family": "E", "entry_px": _px(cur),
                                                 "entry_slot": now, "peak_px": _px(cur),
                                                 "adds": 0, "tokens": 0}
                                    slots_left -= 1
                                    continue

                # Family C: launch sniper.
                if P["fam_c_on"] and t["created_slot"] is not None:
                    age = now - t["created_slot"]
                    if 0 <= age <= P["snipe_max_age"] \
                            and t["dev_buy_sol"] <= P["snipe_max_dev_sol"] \
                            and len(t["buyers"]) <= P["snipe_max_buyers"] \
                            and rq >= P["snipe_min_rq_sol"]:
                        o = buy_order(mint, P["stake_c_sol"])
                        if o is not None:
                            orders.append(o)
                            t["entries"] += 1
                            POS[mint] = {"family": "C", "entry_px": _px(cur),
                                         "entry_slot": now, "peak_px": _px(cur),
                                         "adds": 0, "tokens": 0}
                            slots_left -= 1
                            continue

                # Family B: late-curve rider.
                if P["fam_b_on"] and rq >= P["late_rq_sol"]:
                    n, tot = buys_over(t, now, P["late_win"])
                    if n >= P["late_min_buys"] and tot >= 0.3:
                        o = buy_order(mint, P["stake_b_sol"])
                        if o is not None:
                            orders.append(o)
                            t["entries"] += 1
                            POS[mint] = {"family": "B", "entry_px": _px(cur),
                                         "entry_slot": now, "peak_px": _px(cur),
                                         "adds": 0, "tokens": 0}
                            slots_left -= 1
                            continue

                # Family A: ignition scalp — burst must be NEW (no burst in quiet window).
                if P["fam_a_on"] and regime_ok(state, now):
                    n, tot = buys_over(t, now, P["burst_win"])
                    if n >= P["burst_min_buys"] and tot >= P["burst_min_sol"]:
                        if now - t["last_burst_slot"] > P["ignite_quiet"]:
                            o = buy_order(mint, P["stake_a_sol"])
                            if o is not None:
                                orders.append(o)
                                t["entries"] += 1
                                t["last_burst_slot"] = now
                                POS[mint] = {"family": "A", "entry_px": _px(cur),
                                             "entry_slot": now, "peak_px": _px(cur),
                                             "adds": 0, "tokens": 0}
                                slots_left -= 1
                                continue
                        t["last_burst_slot"] = now

                # Family D: pullback rider (CORE).
                if P["fam_d_on"]:
                    n, tot = buys_over(t, now, P["pull_burst_win"])
                    if n >= P["pull_burst_min_buys"] and tot >= P["pull_burst_min_sol"]:
                        if now - t["burst_slot"] > P["pull_burst_stale"] or t["burst_high"] == 0.0:
                            t["burst_slot"] = now
                            t["burst_high"] = _px(cur)
                        elif _px(cur) > t["burst_high"]:
                            t["burst_high"] = _px(cur)
                    if t["burst_slot"] > 0 and now - t["burst_slot"] <= P["pull_burst_stale"]:
                        high = t["burst_high"]
                        cur_px = _px(cur)
                        if high > 0 and cur_px > 0:
                            drop = (high - cur_px) / high
                            if P["pull_drop_min_bps"] / BPS <= drop <= P["pull_drop_max_bps"] / BPS:
                                # resume: the latest trade must be a strong buy
                                last = t["trades"][-1] if t["trades"] else None
                                if last is not None and last[2] and last[1] >= P["pull_resume_sol"] * LAMPORTS:
                                    o = buy_order(mint, P["stake_d_sol"])
                                    if o is not None:
                                        orders.append(o)
                                        t["entries"] += 1
                                        t["burst_slot"] = -10**9
                                        POS[mint] = {"family": "D", "entry_px": cur_px,
                                                     "entry_slot": now, "peak_px": cur_px,
                                                     "adds": 0, "tokens": 0}
                                        slots_left -= 1
                                        continue

        # ---- update crossing memory for family E ----
        if P["fam_e_on"]:
            for mint in traded:
                cur = state.curves.get(mint)
                if cur is not None:
                    T[mint]["prev_rq"] = cur.real_quote_reserves

        # clear per-batch big-sell flags (they are re-set by new trades)
        for mint in traded:
            T[mint].pop("big_sell", None)
            T[mint].pop("big_sell_e", None)

        return orders[:16]

    return on_batch


if __name__ == "__main__":
    makefun_bot.run(create_bot())
