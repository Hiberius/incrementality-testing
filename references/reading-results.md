# Reading the result

## 1. SRM, before anything else

```bash
python3 scripts/lift.py srm --arms "control=50120,treatment=49880"
```

A split further from the intended ratio than chance allows means the assignment, the
logging or a filter is broken. Threshold 0.001, not 0.05: this is a smoke alarm, and a
false alarm costs an hour while a missed one costs a decision.

**If SRM fires, stop.** Do not read the lift, do not "adjust for it". A lift computed on
a broken split is not slightly wrong, it is meaningless.

## 2. Which p-value you are allowed to read

| How you ran it | Valid test |
|---|---|
| Fixed N committed in advance, read once at the end | `lift` |
| Watched daily, want to stop early | `msprt` |

A fixed-horizon p-value is valid **only** at the sample size you committed to. Checking
it daily and stopping the first time it dips under 0.05 pushes the real false positive
rate to roughly 30%. That is the main reason A/B results fail to replicate, and it is
entirely self-inflicted.

The mSPRT gives an always-valid p-value: look as often as you like, stop when it crosses
alpha, and the error rate still holds. The test suite in this repo demonstrates it —
twenty peeks under a true null, and the false positive rate stays near alpha.

It costs something. On the same data:

```
fixed horizon   p = 0.008   "significant"
always valid    p = 0.172   "keep collecting"
```

Both are correct. The first is what you may claim if you committed to that sample size
in advance and looked once. The second is what you may claim if you have been watching.
Choosing the first **after** seeing that it is smaller is the bias itself.

## 3. CUPED, when you have pre-period data

```bash
python3 scripts/lift.py cuped experiment.csv --pre-column pre_28d --post-column conversions
```

Adjusting the outcome with a pre-experiment covariate removes rho-squared of the
variance. A correlation of 0.6 removes 36%, which is the same power from roughly a third
fewer users. The covariate must be measured **before** assignment, so the treatment
cannot have touched it, which is what keeps the adjustment unbiased.

Below a correlation of about 0.2 it is not worth the complexity. The best covariate is
almost always the same metric over the two to four weeks before the test.

## 4. Effects that are not the treatment

- **Novelty.** Anything new lifts engagement for a few days. Look at the daily series: an
  effect that decays toward zero across the test is novelty, not a result.
- **Primacy.** The mirror image. Existing users are worse at a new interface for a week
  and then better. Both make a short test lie in opposite directions.
- **Simpson's paradox.** The overall result can reverse inside every segment when arm
  composition differs by segment. Check the primary metric on the two or three biggest
  segments before believing an overall number.
- **Multiple comparisons.** Twenty metrics at alpha 0.05 produce one false positive by
  construction. Declare one primary metric; everything else is exploratory and gets
  described that way.

## 5. The decision

| Situation | Call |
|---|---|
| Significant, above the minimum effect you would act on, guardrails clean | Promote |
| Significant, below the effect that justifies the change | Do not ship. Statistical significance is not practical significance. |
| Not significant and the interval excludes your target effect | Retire. You have learned it is not there. |
| Not significant and the interval still contains your target effect | Keep collecting. The test is underpowered, not negative. |
| Guardrail broke | Reject regardless of the primary metric |

The fourth row is the one everyone gets wrong. "Not significant" is not "no effect": it
means the data cannot distinguish the effect from zero **yet**. The confidence interval
tells you which of the two you are in, and the point estimate alone never does.

## 6. Writing it up

State the number, the interval, the sample size, the stop rule you used, and the
guardrails you checked. A lift quoted without an interval is a number somebody will
repeat in a meeting six months from now with all its uncertainty removed.
