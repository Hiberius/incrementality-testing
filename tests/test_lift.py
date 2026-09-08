#!/usr/bin/env python3
"""Zero-dependency test suite. Run: python3 tests/test_lift.py"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import lift as L  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s %s" % (name, detail))
        FAILED.append(name)


print("distributions against published values")
check("norm_ppf(0.975) is 1.959964", abs(L.norm_ppf(0.975) - 1.959964) < 1e-5)
check("norm_ppf(0.5) is 0", abs(L.norm_ppf(0.5)) < 1e-9)
check("norm_ppf(0.8) is 0.841621", abs(L.norm_ppf(0.8) - 0.8416212) < 1e-5)
check("norm_ppf(0.001) is -3.090232", abs(L.norm_ppf(0.001) + 3.0902323) < 1e-4)
check("norm_cdf(1.96) is 0.975", abs(L.norm_cdf(1.959964) - 0.975) < 1e-6)
check("norm_cdf and norm_ppf invert each other",
      all(abs(L.norm_cdf(L.norm_ppf(p)) - p) < 1e-9 for p in (0.01, 0.3, 0.5, 0.9, 0.99)))
check("chi2_sf(3.8415, 1) is 0.05", abs(L.chi2_sf(3.841459, 1) - 0.05) < 1e-5)
check("chi2_sf(5.9915, 2) is 0.05", abs(L.chi2_sf(5.991465, 2) - 0.05) < 1e-5)
check("chi2_sf(10.828, 1) is 0.001", abs(L.chi2_sf(10.8276, 1) - 0.001) < 1e-5)
check("chi2_sf(0, df) is 1", abs(L.chi2_sf(0.0, 3) - 1.0) < 1e-12)
check("chi2_sf is monotone decreasing", L.chi2_sf(1, 1) > L.chi2_sf(5, 1) > L.chi2_sf(20, 1))

print("sample ratio mismatch")
r = L.srm({"control": 50000, "treatment": 50000})
check("a perfect split has chi square zero", abs(r["chi_square"]) < 1e-12)
check("a perfect split is not a mismatch", not r["mismatch"])
check("p is 1 on a perfect split", abs(r["p_value"] - 1.0) < 1e-9)
r = L.srm({"control": 50120, "treatment": 49880})
check("a plausible imbalance passes", not r["mismatch"])
r = L.srm({"control": 52000, "treatment": 48000})
check("a 4 percent imbalance is caught", r["mismatch"])
check("the delta is reported per arm",
      abs(r["arms"]["control"]["delta_pct"] - 4.0) < 1e-6)
r = L.srm({"a": 10000, "b": 10000, "c": 10000})
check("three arms use two degrees of freedom", r["df"] == 2)
r = L.srm({"control": 90000, "treatment": 10000},
          expected={"control": 9, "treatment": 1})
check("an intended 90/10 split is not a mismatch", not r["mismatch"])
r = L.srm({"control": 50000, "treatment": 50000},
          expected={"control": 9, "treatment": 1})
check("a 50/50 result against a 90/10 intent is a mismatch", r["mismatch"])

print("fixed horizon lift")
r = L.lift(10000, 500, 10000, 500)
check("identical arms give zero lift", abs(r["absolute_lift"]) < 1e-12)
check("identical arms are not significant", not r["significant"])
check("identical arms have p near 1", r["p_value"] > 0.99)
r = L.lift(50120, 1204, 49880, 1330)
check("relative lift computed", abs(r["relative_lift"] - 0.1100) < 0.002)
check("the interval contains the point estimate",
      r["ci_low"] < r["absolute_lift"] < r["ci_high"])
check("a clear win is significant", r["significant"])
big = L.lift(100000, 2400, 100000, 2700)
small = L.lift(1000, 24, 1000, 27)
check("more data narrows the interval",
      (big["ci_high"] - big["ci_low"]) < (small["ci_high"] - small["ci_low"]))
check("the same effect is significant at scale and not at low volume",
      big["significant"] and not small["significant"])
r99 = L.lift(50120, 1204, 49880, 1330, alpha=0.01)
check("a 99 percent interval is wider than a 95 percent one",
      (r99["ci_high"] - r99["ci_low"]) > (r["ci_high"] - r["ci_low"]))

print("always-valid mSPRT")
r = L.msprt(50000, 1200, 50000, 1200)
check("no difference gives an always-valid p of 1", abs(r["always_valid_p"] - 1.0) < 0.02)
check("no difference does not reject", not r["reject_null"])
weak = L.msprt(50120, 1204, 49880, 1330)
strong = L.msprt(50120, 1204, 49880, 1600)
check("a larger effect gives a smaller always-valid p",
      strong["always_valid_p"] < weak["always_valid_p"])
check("a strong effect rejects", strong["reject_null"])
check("the always-valid p never exceeds 1",
      all(L.msprt(n, int(n * 0.02), n, int(n * 0.025))["always_valid_p"] <= 1.0
          for n in (500, 5000, 50000)))
fixed = L.lift(50120, 1204, 49880, 1330)
check("mSPRT is more conservative than a fixed-horizon p, which is the whole point",
      weak["always_valid_p"] > fixed["p_value"])
check("zero variance is reported rather than crashing",
      "error" in L.msprt(100, 0, 100, 0))

print("mSPRT false positive rate under repeated peeking")
random.seed(20260908)
false_positives = 0
runs = 200
for _ in range(runs):
    n_c = n_t = 0
    x_c = x_t = 0
    rejected = False
    for _step in range(20):                      # peek twenty times
        for _i in range(500):                    # 500 users per arm per peek
            n_c += 1
            n_t += 1
            x_c += 1 if random.random() < 0.02 else 0
            x_t += 1 if random.random() < 0.02 else 0   # SAME rate: null is true
        if L.msprt(n_c, x_c, n_t, x_t, tau=0.005)["reject_null"]:
            rejected = True
            break
    false_positives += rejected
rate = false_positives / runs
check("peeking twenty times keeps the false positive rate near alpha (%.3f)" % rate,
      rate < 0.12, "got %.3f over %d runs" % (rate, runs))

print("CUPED")
pre = [float(i) for i in range(100)]
post = [x * 2.0 for x in pre]
r = L.cuped(pre, post)
check("perfect correlation removes almost all variance", r["variance_reduction"] > 0.999)
check("perfect correlation is reported as 1", abs(r["correlation"] - 1.0) < 1e-9)
random.seed(7)
pre = [random.gauss(0, 1) for _ in range(2000)]
post = [random.gauss(0, 1) for _ in range(2000)]
r = L.cuped(pre, post)
check("an unrelated covariate reduces almost nothing", r["variance_reduction"] < 0.02)
pre = [random.gauss(0, 1) for _ in range(4000)]
post = [0.6 * pre[i] + random.gauss(0, 0.8) for i in range(4000)]
r = L.cuped(pre, post)
check("a 0.6 correlation removes roughly rho squared of the variance",
      0.25 < r["variance_reduction"] < 0.45,
      "got %.3f at rho %.3f" % (r["variance_reduction"], r["correlation"]))
check("the effective sample multiplier is above 1", r["effective_sample_multiplier"] > 1)
check("a constant covariate is reported, not crashed on",
      "error" in L.cuped([1.0] * 10, [float(i) for i in range(10)]))

print("sample size")
a = L.mde_sample_size(0.024, 0.10)
b = L.mde_sample_size(0.024, 0.20)
check("a bigger target lift needs fewer users", b["per_arm"] < a["per_arm"])
c = L.mde_sample_size(0.024, 0.10, power=0.95)
check("more power needs more users", c["per_arm"] > a["per_arm"])
d = L.mde_sample_size(0.024, 0.10, alpha=0.01)
check("a stricter alpha needs more users", d["per_arm"] > a["per_arm"])
check("total is twice the per-arm figure", a["total"] == a["per_arm"] * 2)
check("halving the lift roughly quadruples the sample",
      3.5 < L.mde_sample_size(0.024, 0.05)["per_arm"] / a["per_arm"] < 4.5)

print("")
if FAILED:
    print("%d test(s) failed: %s" % (len(FAILED), ", ".join(FAILED)))
    sys.exit(1)
print("all tests passed")
