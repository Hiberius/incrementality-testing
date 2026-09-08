---
name: incrementality-testing
description: Use when deciding whether an ad, creative, channel or product change actually caused the result rather than took credit for it - designing an A/B or geo test, choosing a sample size, checking a split for sample ratio mismatch, reading a lift that has been watched daily, reducing variance with pre-period data, or converting platform-reported conversions into incremental ones.
---

# Incrementality Testing

## Overview

Platform ROAS is correlational. The platform optimises toward people who were going to
convert anyway and then bills you for the credit. Incrementality is the causal question,
and answering it takes three things almost nobody does:

1. **Check the randomisation before reading the result.**
2. **Use a test that stays valid when you peek**, because you will peek.
3. **Reduce variance with data you already have**, instead of buying more users.

## When to use

- Designing an experiment on a creative, landing page, channel or product change
- Choosing a sample size, or explaining why a test cannot answer the question
- Reading a result that has been watched daily
- Deciding whether "not significant" means no effect or not enough data
- Measuring the incrementality of a channel where you cannot randomise users
- Converting platform-reported conversions into incremental ones

**Not for:** attribution modelling, which allocates credit among touchpoints that already
happened. Attribution splits a pie; incrementality asks how big the pie would have been
without you.

## The order is not optional

```bash
# 1. is the split even valid?
python3 scripts/lift.py srm --arms "control=50120,treatment=49880"

# 2. what is the effect?
python3 scripts/lift.py lift --control 50120/1204 --treatment 49880/1330

# 3. ...but only if you committed to that sample size. If you have been watching:
python3 scripts/lift.py msprt --control 50120/1204 --treatment 49880/1330
```

## Sample ratio mismatch first, always

A split further from the intended ratio than chance allows means assignment, logging or a
filter is broken. Threshold **0.001**, not 0.05: this is a smoke alarm.

If it fires, stop. Do not read the lift and do not "adjust for it". A lift computed on a
broken split is not slightly wrong, it is meaningless.

## Peeking is the main way results go wrong

A fixed-horizon p-value is valid **only** at the sample size you committed to in advance.
Checking daily and stopping the first time it dips below 0.05 pushes the real false
positive rate to roughly 30%.

On the same data:

```
fixed horizon   p = 0.008   "significant"
always valid    p = 0.172   "keep collecting"
```

Both are correct. The first is what you may claim if you committed to that N and looked
once. The second is what you may claim if you have been watching. **Picking the first
after seeing that it is smaller is the bias itself.**

The mSPRT in `msprt` gives an always-valid p-value: look as often as you like, stop the
moment it crosses alpha, error rate holds. The test suite demonstrates it with twenty
peeks under a true null.

`--tau` is the prior standard deviation of the effect in absolute metric units. Set it to
the smallest effect you would act on.

## CUPED: free power out of data you already have

```bash
python3 scripts/lift.py cuped experiment.csv --pre-column pre_28d --post-column conversions
```

Adjusting the outcome with a pre-experiment covariate removes rho-squared of the variance:
a correlation of 0.6 removes 36%, the same power from roughly a third fewer users. It is
unbiased because the covariate is measured **before** assignment, so the treatment cannot
have touched it. Below a correlation of about 0.2, not worth the complexity.

## Not significant is not no effect

| Situation | Call |
|---|---|
| Significant and above the effect you would act on, guardrails clean | Promote |
| Significant but below the effect that justifies the change | Do not ship |
| Not significant, interval excludes your target effect | Retire, you have learned it is not there |
| Not significant, interval still contains your target effect | Keep collecting, it is underpowered |
| A guardrail broke | Reject regardless of the primary metric |

The confidence interval decides between rows three and four. The point estimate never does.

## When you cannot randomise users

Inside an ad platform you rarely control assignment. Four designs, in order of how much
they ask of you: geo holdout, audience holdout, ghost ads or PSA control, switchback.
Details and their failure modes in `references/geo-and-holdout.md`.

The number worth tracking over time:

```
incrementality factor = incremental conversions / platform-reported conversions
```

A factor of 0.4 means the platform claims two and a half times what the campaign caused.
Every CPA target built on platform-reported conversions is wrong by that factor, in the
same direction, every month.

## Reference

| Topic | File |
|---|---|
| Unit of randomisation, deterministic assignment, power, duration, guardrails, what invalidates a test | `references/experiment-design.md` |
| SRM, which p-value is legal, CUPED, novelty and primacy, Simpson's paradox, the decision table | `references/reading-results.md` |
| Geo holdout, audience holdout, ghost ads, switchback, incremental CPA | `references/geo-and-holdout.md` |

## Common mistakes

- **Reading the lift before checking SRM.**
- **Filtering after assignment** on something the treatment affects. Post-treatment
  selection quietly destroys the randomisation you paid for.
- **Randomising by session** when the treatment spans the funnel, so the same person
  lands in both arms.
- **Stopping the day it turns green** without an always-valid test.
- **Comparing exposed against unexposed** inside a platform and calling it an experiment.
  The platform chose the exposed group precisely because they were more likely to convert.
- **Ending on a partial week.** Weekdays and weekends are different populations.
- **Reporting a lift without its interval.** Six months later someone repeats the number
  with all its uncertainty removed.
