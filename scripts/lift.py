#!/usr/bin/env python3
"""lift - incrementality testing that survives being looked at every day.

Platform ROAS is correlational: it credits the ad for conversions that would have
happened anyway. Incrementality is the causal question, and answering it means running
an experiment properly, which means three things almost nobody does: checking the
randomisation before reading the result, using a test that stays valid when you peek,
and reducing variance with data you already have.

  lift.py srm    --arms "control=50120,treatment=49880"
  lift.py lift   --control 50120/1204 --treatment 49880/1330
  lift.py msprt  --control 50120/1204 --treatment 49880/1330
  lift.py cuped  pre_post.csv
  lift.py mde    --baseline 0.024 --lift 0.10

Pure standard library, Python 3.8+. No network, no dependencies.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys

# --------------------------------------------------------------------------
# distributions, from the standard library only
# --------------------------------------------------------------------------

def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_ppf(p):
    """Inverse normal CDF, Acklam's rational approximation. Accurate to ~1e-9."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _gamma_inc_upper_regularised(s, x):
    """Q(s, x). Series below the crossover, continued fraction above."""
    if x < 0 or s <= 0:
        raise ValueError("domain")
    if x == 0:
        return 1.0
    if x < s + 1.0:
        term = 1.0 / s
        total = term
        n = s
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return 1.0 - total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h * math.exp(-x + s * math.log(x) - math.lgamma(s))


def chi2_sf(x, df):
    """P(X > x) for a chi-square with df degrees of freedom."""
    return _gamma_inc_upper_regularised(df / 2.0, x / 2.0)


# --------------------------------------------------------------------------
# sample ratio mismatch: the gate before any analysis
# --------------------------------------------------------------------------

def srm(counts, expected=None, alpha=0.001):
    """Chi-square goodness of fit against the intended split.

    Run this FIRST, every time. A split that is off by more than chance means the
    randomisation, the logging or the filtering is broken, and a broken assignment makes
    the lift estimate meaningless no matter how significant it looks. The conventional
    threshold is 0.001, not 0.05: SRM is a smoke alarm, and false alarms are cheaper
    than shipping a bad decision.
    """
    labels = list(counts)
    observed = [float(counts[k]) for k in labels]
    total = sum(observed)
    if expected:
        weights = [float(expected[k]) for k in labels]
    else:
        weights = [1.0] * len(labels)
    wsum = sum(weights)
    exp = [total * w / wsum for w in weights]
    stat = sum((o - e) ** 2 / e for o, e in zip(observed, exp) if e > 0)
    p = chi2_sf(stat, len(labels) - 1)
    return {
        "arms": {labels[i]: {"observed": int(observed[i]), "expected": round(exp[i], 1),
                             "delta_pct": round((observed[i] - exp[i]) / exp[i] * 100, 3)}
                 for i in range(len(labels))},
        "chi_square": round(stat, 4),
        "df": len(labels) - 1,
        "p_value": p,
        "mismatch": p < alpha,
        "threshold": alpha,
    }


# --------------------------------------------------------------------------
# fixed-horizon lift
# --------------------------------------------------------------------------

def lift(n_c, x_c, n_t, x_t, alpha=0.05):
    """Absolute and relative lift on a binary metric, with a confidence interval."""
    p_c, p_t = x_c / n_c, x_t / n_t
    diff = p_t - p_c
    se = math.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z_crit = norm_ppf(1 - alpha / 2)
    lo, hi = diff - z_crit * se, diff + z_crit * se

    p_pool = (x_c + x_t) / (n_c + n_t)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = diff / se_pool if se_pool else 0.0
    p_value = 2 * (1 - norm_cdf(abs(z)))

    return {
        "control_rate": p_c, "treatment_rate": p_t,
        "absolute_lift": diff,
        "relative_lift": (diff / p_c) if p_c else None,
        "ci_low": lo, "ci_high": hi, "ci_level": 1 - alpha,
        "relative_ci_low": (lo / p_c) if p_c else None,
        "relative_ci_high": (hi / p_c) if p_c else None,
        "z": z, "p_value": p_value,
        "significant": p_value < alpha,
    }


# --------------------------------------------------------------------------
# always-valid sequential testing (mSPRT)
# --------------------------------------------------------------------------

def msprt(n_c, x_c, n_t, x_t, tau=0.01, alpha=0.05):
    """Mixture sequential probability ratio test with a normal mixing prior.

    A fixed-horizon p-value is only valid at the sample size you committed to. Looking
    at it daily and stopping when it dips under 0.05 inflates the false positive rate to
    somewhere around 30%, which is the single most common reason A/B results do not
    replicate.

    The mSPRT statistic gives an ALWAYS-VALID p-value: you may look as often as you
    like, stop whenever it crosses your threshold, and the false positive rate still
    holds at alpha.

    tau is the prior standard deviation on the true effect, in ABSOLUTE units of the
    metric. Set it to the smallest effect you would act on. Too small and the test is
    slow; too large and it is insensitive to the effects you care about.
    """
    p_c, p_t = x_c / n_c, x_t / n_t
    v = p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t
    if v <= 0:
        return {"error": "zero variance: one arm has no variation yet"}
    diff = p_t - p_c
    t2 = tau ** 2
    log_lr = 0.5 * math.log(v / (v + t2)) + (t2 * diff ** 2) / (2 * v * (v + t2))
    lr = math.exp(log_lr)
    p_always_valid = min(1.0, 1.0 / lr) if lr > 0 else 1.0
    return {
        "observed_diff": diff,
        "likelihood_ratio": lr,
        "always_valid_p": p_always_valid,
        "reject_null": p_always_valid < alpha,
        "tau": tau,
        "note": ("Safe to peek. This p-value is valid at every sample size, so you may "
                 "stop the moment it crosses alpha."),
    }


# --------------------------------------------------------------------------
# CUPED
# --------------------------------------------------------------------------

def cuped(pre, post):
    """Controlled experiment Using Pre-Experiment Data.

    Y_adjusted = Y - theta * (X - mean(X)),  theta = Cov(X, Y) / Var(X)

    The adjustment is unbiased because X is measured BEFORE assignment and therefore
    cannot be affected by the treatment. Variance falls by rho squared, so a correlation
    of 0.6 removes 36% of the variance and buys the same power from roughly a third fewer
    users. Free statistical power out of data you already have.
    """
    n = len(pre)
    if n != len(post) or n < 3:
        raise ValueError("pre and post must be the same length, at least 3 points")
    mx = sum(pre) / n
    my = sum(post) / n
    var_x = sum((x - mx) ** 2 for x in pre) / (n - 1)
    var_y = sum((y - my) ** 2 for y in post) / (n - 1)
    cov = sum((pre[i] - mx) * (post[i] - my) for i in range(n)) / (n - 1)
    if var_x == 0:
        return {"error": "the covariate has zero variance and cannot help"}
    theta = cov / var_x
    adjusted = [post[i] - theta * (pre[i] - mx) for i in range(n)]
    ma = sum(adjusted) / n
    var_adj = sum((a - ma) ** 2 for a in adjusted) / (n - 1)
    rho = cov / math.sqrt(var_x * var_y) if var_y > 0 else 0.0
    return {
        "theta": theta,
        "correlation": rho,
        "variance_before": var_y,
        "variance_after": var_adj,
        "variance_reduction": (1 - var_adj / var_y) if var_y else 0.0,
        "effective_sample_multiplier": (var_y / var_adj) if var_adj else None,
        "adjusted": adjusted,
    }


# --------------------------------------------------------------------------
# sample size
# --------------------------------------------------------------------------

def mde_sample_size(baseline, relative_lift, alpha=0.05, power=0.8):
    p1 = baseline
    p2 = baseline * (1 + relative_lift)
    if not 0 < p2 < 1:
        raise ValueError("the lifted rate must stay between 0 and 1")
    z_a = norm_ppf(1 - alpha / 2)
    z_b = norm_ppf(power)
    n = ((z_a + z_b) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))) / ((p2 - p1) ** 2)
    return {
        "baseline_rate": p1, "target_rate": p2,
        "relative_lift": relative_lift,
        "per_arm": int(math.ceil(n)),
        "total": int(math.ceil(n)) * 2,
        "alpha": alpha, "power": power,
    }


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def parse_arm(spec, label):
    try:
        n, x = spec.split("/")
        return int(n), int(x)
    except Exception:
        raise SystemExit("error: --%s must be exposures/conversions, e.g. 50120/1204"
                         % label)


def pct(v):
    return "-" if v is None else "%+.2f%%" % (v * 100)


def cmd_srm(args):
    counts = {}
    for part in args.arms.split(","):
        k, v = part.split("=")
        counts[k.strip()] = int(v)
    expected = None
    if args.expected:
        expected = {}
        for part in args.expected.split(","):
            k, v = part.split("=")
            expected[k.strip()] = float(v)
    result = srm(counts, expected, args.alpha)
    if args.json:
        print(json.dumps(result, indent=2))
        return 1 if result["mismatch"] else 0
    print("%-14s %10s %10s %9s" % ("ARM", "OBSERVED", "EXPECTED", "DELTA"))
    for arm, d in result["arms"].items():
        print("%-14s %10d %10.1f %8.3f%%" % (arm, d["observed"], d["expected"], d["delta_pct"]))
    print("\nchi2 %.4f on %d df, p = %.6g" % (result["chi_square"], result["df"],
                                              result["p_value"]))
    if result["mismatch"]:
        print("\nSAMPLE RATIO MISMATCH. Stop. Do not read the lift.")
        print("The assignment, the logging or a filter is broken. A lift computed on a")
        print("broken split is not wrong by a little, it is meaningless.")
    else:
        print("\nSplit is within chance. Safe to read the result.")
    return 1 if result["mismatch"] else 0


def cmd_lift(args):
    n_c, x_c = parse_arm(args.control, "control")
    n_t, x_t = parse_arm(args.treatment, "treatment")
    r = lift(n_c, x_c, n_t, x_t, args.alpha)
    if args.json:
        print(json.dumps(r, indent=2))
        return 0
    print("control      %8d exposures  %7d conversions  %.4f%%"
          % (n_c, x_c, r["control_rate"] * 100))
    print("treatment    %8d exposures  %7d conversions  %.4f%%"
          % (n_t, x_t, r["treatment_rate"] * 100))
    print("\nabsolute lift  %+.4f pp" % (r["absolute_lift"] * 100))
    print("relative lift  %s   %.0f%% CI [%s, %s]"
          % (pct(r["relative_lift"]), r["ci_level"] * 100,
             pct(r["relative_ci_low"]), pct(r["relative_ci_high"])))
    print("p = %.5f  %s" % (r["p_value"],
                            "significant" if r["significant"] else "not significant"))
    print("\nThis p-value is valid ONLY at the sample size you committed to in advance.")
    print("If you have been watching it daily, use msprt instead.")
    return 0


def cmd_msprt(args):
    n_c, x_c = parse_arm(args.control, "control")
    n_t, x_t = parse_arm(args.treatment, "treatment")
    r = msprt(n_c, x_c, n_t, x_t, args.tau, args.alpha)
    if "error" in r:
        print(r["error"])
        return 2
    if args.json:
        print(json.dumps(r, indent=2))
        return 0
    print("observed difference   %+.4f pp" % (r["observed_diff"] * 100))
    print("likelihood ratio      %.4f" % r["likelihood_ratio"])
    print("always-valid p        %.5f" % r["always_valid_p"])
    print("decision              %s"
          % ("REJECT the null, the effect is real"
             if r["reject_null"] else "keep collecting"))
    print("\n%s" % r["note"])
    return 0


def cmd_cuped(args):
    pre, post = [], []
    with open(args.source, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            try:
                pre.append(float(row[args.pre_column]))
                post.append(float(row[args.post_column]))
            except (KeyError, ValueError):
                continue
    r = cuped(pre, post)
    if "error" in r:
        print(r["error"])
        return 2
    print("rows                       %d" % len(pre))
    print("theta                      %.6f" % r["theta"])
    print("correlation pre/post       %.4f" % r["correlation"])
    print("variance before            %.6f" % r["variance_before"])
    print("variance after             %.6f" % r["variance_after"])
    print("variance reduction         %.1f%%" % (r["variance_reduction"] * 100))
    if r["effective_sample_multiplier"]:
        print("equivalent to a sample     %.2fx larger" % r["effective_sample_multiplier"])
    if r["correlation"] < 0.2:
        print("\nCorrelation is too low for CUPED to be worth the complexity.")
        print("Find a covariate closer to the outcome, usually the same metric measured")
        print("over the two weeks before assignment.")
    return 0


def cmd_mde(args):
    r = mde_sample_size(args.baseline, args.lift, args.alpha, args.power)
    print("baseline rate     %.4f%%" % (r["baseline_rate"] * 100))
    print("target rate       %.4f%%  (%+.0f%% relative)"
          % (r["target_rate"] * 100, r["relative_lift"] * 100))
    print("alpha %.2f, power %.0f%%" % (r["alpha"], r["power"] * 100))
    print("\nper arm           %d" % r["per_arm"])
    print("total             %d" % r["total"])
    print("\nIf you cannot reach that in a reasonable window, the honest options are a")
    print("bigger expected effect, a more frequent metric, or CUPED. Running the test")
    print("underpowered and reading it anyway is not one of them.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="lift", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("srm", help="sample ratio mismatch check, run this first")
    s.add_argument("--arms", required=True, help='e.g. "control=50120,treatment=49880"')
    s.add_argument("--expected", help='intended split, e.g. "control=1,treatment=1"')
    s.add_argument("--alpha", type=float, default=0.001)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_srm)

    l = sub.add_parser("lift", help="fixed-horizon lift with a confidence interval")
    l.add_argument("--control", required=True, metavar="N/X")
    l.add_argument("--treatment", required=True, metavar="N/X")
    l.add_argument("--alpha", type=float, default=0.05)
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_lift)

    m = sub.add_parser("msprt", help="always-valid sequential test, safe to peek")
    m.add_argument("--control", required=True, metavar="N/X")
    m.add_argument("--treatment", required=True, metavar="N/X")
    m.add_argument("--tau", type=float, default=0.01,
                   help="prior sd of the effect, in absolute metric units")
    m.add_argument("--alpha", type=float, default=0.05)
    m.add_argument("--json", action="store_true")
    m.set_defaults(func=cmd_msprt)

    c = sub.add_parser("cuped", help="variance reduction from a pre-period covariate")
    c.add_argument("source")
    c.add_argument("--pre-column", default="pre")
    c.add_argument("--post-column", default="post")
    c.set_defaults(func=cmd_cuped)

    d = sub.add_parser("mde", help="sample size for a target lift")
    d.add_argument("--baseline", type=float, required=True)
    d.add_argument("--lift", type=float, required=True, help="relative, e.g. 0.10 for +10%%")
    d.add_argument("--alpha", type=float, default=0.05)
    d.add_argument("--power", type=float, default=0.8)
    d.set_defaults(func=cmd_mde)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
