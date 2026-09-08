# When you cannot randomise users: media incrementality

Inside an ad platform you rarely control assignment. The platform decides who sees the
ad, and it optimises toward people who were going to convert anyway. That is exactly why
platform-reported ROAS overstates incremental value, often by a lot, and why "we turned
it off and revenue barely moved" keeps happening.

Four designs, in order of how much they ask of you.

## Geo holdout

Split comparable markets into treatment and control, run the campaign only in treatment,
compare outcomes.

- **Match on pre-period behaviour**, not on population. Two cities with the same
  population and different baseline conversion rates are not a pair.
- **Randomise within matched pairs**, and use several pairs. One pair is an anecdote.
- **Watch for spillover**: commuter regions, national media, and shipping catchments that
  cross the boundary.
- Analysis is on the geo as the unit, so your sample size is the number of geos, not the
  number of users. This is why geo tests need a large effect: you have twenty units, not
  twenty thousand.

Best for: upper-funnel, brand, TV-adjacent, anything where user-level tracking is absent.

## Audience holdout

Withhold the campaign from a random share of the addressable audience, usually 5-10%,
and compare.

- Cheapest to run when the platform supports it natively.
- The holdout must be excluded **everywhere**, including retargeting and lookalikes built
  from converters, or it contaminates within a week.
- Small holdouts are underpowered. A 5% holdout on a small account measures nothing; run
  the sample size calculation before choosing the share.

## Ghost ads and PSA control

The control group goes through the same auction and would have seen your ad, but is shown
a neutral placeholder or nothing. This removes the selection bias that makes an "unexposed"
comparison group worthless: unexposed users differ from exposed users in every way that
made the platform pick the exposed ones.

Best available design where the platform offers it. If it does not, an "exposed versus
unexposed" comparison is not an experiment and should not be presented as one.

## Switchback

Turn the campaign on and off in alternating time blocks across the same population. Useful
when the treatment affects a shared marketplace and a holdout would leak.

- Blocks must be long enough to cover the conversion lag, and short enough to give you
  many of them.
- Randomise the order of the blocks; alternating strictly confounds with day of week.

## What to compute

Once you have arms, the maths is the same as any experiment:

```bash
python3 scripts/lift.py srm  --arms "control=...,treatment=..."
python3 scripts/lift.py lift --control N/X --treatment N/X
```

Then the number that matters for media:

```
incremental conversions = treatment conversions - (control rate x treatment exposures)
incremental CPA         = campaign spend / incremental conversions
incrementality factor   = incremental conversions / platform-reported conversions
```

The last one is the ratio worth tracking over time. A factor of 0.4 means the platform is
claiming two and a half times the conversions the campaign actually caused. That does not
mean the campaign is bad; it means every CPA target built on platform-reported conversions
is wrong by the same factor, in the same direction, every month.

## Cadence

Incrementality is measured, not monitored. Run it per channel once a quarter, and after
any change large enough to move the answer: a new channel, a major creative direction, a
change in attribution settings. Between measurements, use the factor you measured to
deflate the platform's numbers, and re-measure before trusting it for another quarter.
