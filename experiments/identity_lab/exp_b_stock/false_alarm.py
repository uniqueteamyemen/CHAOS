"""How to choose the break threshold before the system is stable.

Answers one question only: given a zero-parameter identity and a ruled detector,
what false-alarm rate do I buy, and what is the smallest leak I can still see?

Monte Carlo, 4000 replications per cell. Two cases:
  A. sigma known from a long quiet history
  B. sigma estimated from a 6-month quiet window (the situation CHAOS is actually in)
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.identity import mad_sigma  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPS = 4000
HORIZON = 36
LEAK_START = 7


def fires(residuals: list[float], sigma: float, k: float, run_len: int) -> int | None:
    run = 0
    sign = 0
    for i, r in enumerate(residuals, start=1):
        if abs(r) >= k * sigma:
            s = 1 if r > 0 else -1
            if s == sign:
                run += 1
            else:
                run, sign = 1, s
        else:
            run, sign = 0, 0
        if run >= run_len:
            return i
    return None


def simulate(rng, sigma, k, run_len, leak=0.0, sigma_estimated=False):
    quiet = [rng.gauss(0, sigma) for _ in range(6)] if sigma_estimated else []
    s = mad_sigma(quiet) if sigma_estimated else sigma
    if s <= 0:
        s = sigma * 0.5
    res = []
    for month in range(1, HORIZON + 1):
        mu = leak if month >= LEAK_START else 0.0
        res.append(rng.gauss(mu, sigma))
    return fires(res, s, k, run_len)


def cell(k, run_len, leak_sigmas, sigma_estimated):
    rng = random.Random(1000 + int(k * 10) + run_len + int(leak_sigmas * 100))
    hits, months = 0, []
    for _ in range(REPS):
        d = simulate(rng, 1.0, k, run_len, leak=leak_sigmas, sigma_estimated=sigma_estimated)
        if d:
            hits += 1
            months.append(d)
    return hits / REPS, (statistics.median(months) if months else None)


def main():
    lines = [
        "# Threshold calibration — what the rule buys",
        "",
        f"Monte Carlo, {REPS} replications, 36-month horizon, leak starts month {LEAK_START}.",
        "Rule: *run_len* consecutive residuals, same sign, each beyond *k*·σ. No model, no likelihood.",
        "",
        "## A. σ known from a long quiet history",
        "",
        "| k | run | false alarm / 36 mo | detect λ=2σ | λ=3σ | λ=5σ | λ=10σ |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in (2.0, 2.5, 3.0, 4.0):
        for run_len in (2, 3, 4):
            far, _ = cell(k, run_len, 0.0, False)
            p2, _ = cell(k, run_len, 2.0, False)
            p3, m3 = cell(k, run_len, 3.0, False)
            p5, m5 = cell(k, run_len, 5.0, False)
            p10, m10 = cell(k, run_len, 10.0, False)
            med = lambda p, m: f"{p * 100:.0f}% @ m{m}" if m else f"{p * 100:.0f}%"  # noqa: E731
            lines.append(
                f"| {k} | {run_len} | {far * 100:.2f}% | {med(p2, None)} | {med(p3, m3)} | "
                f"{med(p5, m5)} | {med(p10, m10)} |"
            )

    lines += [
        "",
        "## B. σ estimated from a 6-month quiet window (the real situation)",
        "",
        "| k | run | false alarm / 36 mo | detect λ=3σ | λ=5σ |",
        "|---|---|---|---|---|",
    ]
    for k in (2.0, 3.0):
        for run_len in (3, 5):
            far, _ = cell(k, run_len, 0.0, True)
            p3, m3 = cell(k, run_len, 3.0, True)
            p5, m5 = cell(k, run_len, 5.0, True)
            lines.append(
                f"| {k} | {run_len} | {far * 100:.2f}% | "
                f"{(f'{p3 * 100:.0f}% @ m{m3}' if m3 else f'{p3 * 100:.0f}%')} | "
                f"{(f'{p5 * 100:.0f}% @ m{m5}' if m5 else f'{p5 * 100:.0f}%')} |"
            )

    lines += [
        "",
        "## Reading it",
        "",
        "- At k=3, run=3 the false-alarm rate over three years is under 1 in 1000 — the rule is",
        "  conservative, and that is why it can be adopted before the system is stable.",
        "- The price is a floor: leaks below about 3σ are invisible. That floor is arithmetic, not",
        "  a tuning problem, and it is the honest answer to *'what if the leak is small?'*.",
        "- Estimating σ from six points inflates false alarms by an order of magnitude, because a",
        "  short window can land below the true scale. Pool σ across entities, or use a floor.",
        "- Therefore: **the threshold is a purchase, not a discovery.** k and run are chosen by the",
        "  smallest leak you must see and the number of false alarms you can absorb per year.",
        "- Until 20 labelled events exist, do not automate. Label by hand, then calibrate.",
    ]
    (ROOT / "results/false_alarm.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote results/false_alarm.md")


if __name__ == "__main__":
    main()
