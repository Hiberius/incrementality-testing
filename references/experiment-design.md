# Designing the experiment

## Write it down before you start

Five lines, before a single user is assigned. Not for ceremony: everything below is a
decision you will otherwise make **after** seeing the data, which is where bias enters.

```
Hypothesis      the new creative increases lead rate
Primary metric  leads / sessions
Unit            user (hashed id), not session, not impression
Split           50 / 50
Stop rule       fixed at N per arm, or always-valid p under 0.05
Guardrails      cost per lead, bounce rate, lead acceptance rate
```

The stop rule is the one people skip, and it decides which p-value is even legal to
read.

## Unit of randomisation

Randomise on the unit that experiences the treatment consistently. Randomising by
session while the treatment changes the whole funnel means the same person sees both
variants, the effect leaks across arms, and the estimate is biased toward zero.

If a user can appear in both arms, the experiment measures nothing. Fix the unit before
anything else.

## Deterministic assignment

```
arm = hash(experiment_id + user_id) % 100 < 50 ? "control" : "treatment"
```

Not a random number generator at request time. Deterministic hashing means:

- The same user is in the same arm on every visit, across devices where the id is stable,
  and after a deploy.
- Assignment is reproducible in analysis without a lookup table.
- Adding a second experiment does not disturb the first, as long as the experiment id is
  in the hash.

Salt with the experiment id, never with a fixed string, or two experiments launched the
same week share their assignment and their effects become uninterpretable.

## Power, before launch

```bash
python3 scripts/lift.py mde --baseline 0.024 --lift 0.10
```

If the required sample is out of reach in a sensible window, there are three honest
responses: target a bigger effect, choose a metric that occurs more often, or use CUPED
to buy back variance. Running underpowered and reading the result anyway is not one of
them: an underpowered test that reaches significance has, by construction, overestimated
the effect.

## Duration

- **At least one full week**, always. Weekday and weekend behave differently and a
  Tuesday-to-Friday test measures Tuesday-to-Friday.
- **Whole weeks**, not 10 days. A partial week weights some days twice.
- **Long enough for the conversion lag.** If leads convert over five days, a seven-day
  test measures two days of outcomes for the users who joined last.

## Guardrails

The primary metric can improve while the business gets worse. Declare guardrails up front
and check them at the end: cost per result, downstream acceptance or refund rate, page
performance, complaint rate. A creative that lifts lead volume 20% and drops lead
acceptance 30% is a loss, and the primary metric will never say so.

## What invalidates an experiment

| Problem | Consequence |
|---|---|
| Sample ratio mismatch | Assignment or logging is broken. Nothing else is readable. |
| A user in both arms | The effect leaks; the estimate is biased toward zero. |
| Treatment changed mid-flight | You are now measuring two different things averaged together. |
| Arms launched at different times | Confounded with everything else that changed that day. |
| A filter applied post-assignment | Post-treatment selection. The classic silent bias. |

That last one deserves its name. Filtering to "engaged users" after assignment, when the
treatment itself affects engagement, conditions on a post-treatment variable and breaks
the randomisation you paid for. Filter on attributes fixed **before** assignment, or do
not filter.
