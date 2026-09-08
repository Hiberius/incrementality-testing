# Incrementality Testing

**An Agent Skill for the causal question: did the ad cause the conversion, or take credit
for it. Sample ratio mismatch, an always-valid sequential test that survives daily
peeking, CUPED variance reduction, and the geo and holdout designs for channels where you
cannot randomise users.**

[![License: MIT](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776AB?logo=python&logoColor=white)
![Zero dependencies](https://img.shields.io/badge/dependencies-0-6E56CF)

```bash
npx skills add Hiberius/incrementality-testing
```

---

## The same data, two legal answers

```bash
python3 scripts/lift.py lift --control 50120/1204 --treatment 49880/1330
```
```
absolute lift  +0.2642 pp
relative lift  +11.00%   95% CI [+2.89%, +19.11%]
p = 0.00787  significant
```

```bash
python3 scripts/lift.py msprt --control 50120/1204 --treatment 49880/1330
```
```
always-valid p        0.17168
decision              keep collecting
```

Both are correct. The first is what you may claim if you committed to that sample size in
advance and looked once. The second is what you may claim if you have been watching it
daily. **Choosing the first after seeing that it is smaller is the bias itself.**

Checking a fixed-horizon p-value every day and stopping the first time it dips under 0.05
pushes the real false positive rate to around 30%. That is the main reason A/B results do
not replicate, and it is entirely self-inflicted.

The test suite proves the fix: twenty peeks under a true null, 200 simulated experiments,
false positive rate stays at 1%.

## Check the split before you read anything

```bash
python3 scripts/lift.py srm --arms "control=52000,treatment=48000"
```
```
SAMPLE RATIO MISMATCH. Stop. Do not read the lift.
The assignment, the logging or a filter is broken. A lift computed on a
broken split is not wrong by a little, it is meaningless.
```

Threshold 0.001, not 0.05. It is a smoke alarm, and a false alarm costs an hour while a
missed one costs a decision.

## Free power out of data you already have

```bash
python3 scripts/lift.py cuped experiment.csv --pre-column pre_28d --post-column post
```
```
correlation pre/post       0.5340
variance reduction         28.5%
equivalent to a sample     1.40x larger
```

The covariate is measured before assignment, so the treatment cannot have touched it,
which is what keeps the adjustment unbiased.

## What it does

| Command | What you get |
|---|---|
| `srm` | Chi-square check on the split, per-arm deltas, and a hard stop when it fires |
| `lift` | Absolute and relative lift with a confidence interval and a fixed-horizon p-value |
| `msprt` | Always-valid p-value from a mixture SPRT: peek as often as you like |
| `cuped` | Variance reduction from a pre-period covariate, with the effective sample multiplier |
| `mde` | Sample size per arm for a target lift, alpha and power |

All of it in the standard library: normal CDF and inverse CDF, regularised incomplete
gamma for the chi-square tail, no SciPy.

## Not significant is not no effect

The confidence interval decides. If it excludes the effect you would act on, you have
learned it is not there. If it still contains it, the test is underpowered, not negative.
The point estimate alone never tells you which.

## When you cannot randomise users

Inside an ad platform you rarely control assignment, and "exposed versus unexposed" is not
an experiment: the platform chose the exposed group precisely because they were more
likely to convert. Geo holdout, audience holdout, ghost ads and switchback designs, with
their failure modes, are in
[`references/geo-and-holdout.md`](references/geo-and-holdout.md), along with:

```
incrementality factor = incremental conversions / platform-reported conversions
```

A factor of 0.4 means the platform claims two and a half times what the campaign caused.

## Documentation

- [`SKILL.md`](SKILL.md) — the skill itself, what the agent reads
- [`references/experiment-design.md`](references/experiment-design.md) — unit of randomisation, deterministic assignment, power, duration, guardrails, what invalidates a test
- [`references/reading-results.md`](references/reading-results.md) — SRM, which p-value is legal, CUPED, novelty and primacy, Simpson's paradox, the decision table
- [`references/geo-and-holdout.md`](references/geo-and-holdout.md) — media incrementality without user-level randomisation

## Related

- [cpa-profit-ops](https://github.com/Hiberius/cpa-profit-ops) — the profit maths these decisions feed
- [competitor-ad-intelligence](https://github.com/Hiberius/competitor-ad-intelligence) — what to test next

## License

MIT. No network calls, no telemetry, no dependencies.
