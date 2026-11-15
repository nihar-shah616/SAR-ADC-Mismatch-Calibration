"""Day 2: Monte Carlo over many chips -> distributions of max INL / DNL and yield vs mismatch.

A 'chip' = one random draw of all unit-capacitor errors (make_weights). For each chip we run the
static ramp test (static_metrics) and record max|INL| and max|DNL| (in LSB).
Yield = fraction of chips whose max|INL| and max|DNL| are both below a limit.

Run:  python mc_yield.py        (needs numpy, matplotlib; imports sar_model.py from the same folder)
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sar_model import make_weights, static_metrics

rng = np.random.default_rng(11)

def run_chips(N, sigma_u, chips, pts=10):
    inl_max, dnl_max, carry = [], [], []
    for _ in range(chips):
        w = make_weights(N, sigma_u, rng)
        k, inl, dnl = static_metrics(w, pts_per_lsb=pts)
        inl_max.append(np.nanmax(np.abs(inl)))
        dnl_max.append(np.nanmax(np.abs(dnl)))
        carry.append(w[N - 1] - w[:N - 1].sum() - 1.0)       # major-carry DNL, from the weights
    return np.array(inl_max), np.array(dnl_max), np.array(carry)

# ---------------------------------------------------------------- 1. one operating point (N = 10, 1 %)
N, s, chips = 10, 0.01, 200
inl_m, dnl_m, carry = run_chips(N, s, chips)
print(f"N = {N}, sigma_u = {s*100:.1f}%, {chips} chips")
print(f"  max|INL|: median {np.median(inl_m):.2f}, 95th percentile {np.percentile(inl_m,95):.2f}, worst {inl_m.max():.2f} LSB")
print(f"  max|DNL|: median {np.median(dnl_m):.2f}, 95th percentile {np.percentile(dnl_m,95):.2f}, worst {dnl_m.max():.2f} LSB")
print(f"  major-carry DNL (from weights): std = {carry.std(ddof=1):.3f} LSB,  theory sqrt(2^N-1)*sigma_u = {np.sqrt(2**N-1)*s:.3f} LSB")

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].hist(inl_m, bins=20); ax[0].set_xlabel("max |INL| per chip (LSB)"); ax[0].set_ylabel("chips")
ax[1].hist(dnl_m, bins=20); ax[1].set_xlabel("max |DNL| per chip (LSB)")
fig.suptitle(f"{N}-bit SAR ADC, unit-capacitor mismatch {s*100:.1f}%, {chips} chips")
plt.tight_layout(); plt.savefig("mc_histograms.png", dpi=150); plt.close()

# ---------------------------------------------------------------- 2. yield versus mismatch and resolution
sigmas = np.array([0.25, 0.5, 1.0, 1.5, 2.0, 3.0]) / 100
limit = 0.5                                                # LSB
print(f"\nYield (max|INL| and max|DNL| both < {limit} LSB), 100 chips per point")
print("sigma_u(%) " + "".join(f"{x*100:>8.2f}" for x in sigmas))
curves = {}
for N in (8, 10, 12):
    y = []
    for s in sigmas:
        i, d, _ = run_chips(N, s, 100)
        y.append(np.mean((i < limit) & (d < limit)) * 100)
    curves[N] = y
    print(f"N = {N:>2d}      " + "".join(f"{v:>8.0f}" for v in y))

plt.figure(figsize=(7, 4.5))
for N, y in curves.items():
    plt.plot(sigmas * 100, y, "o-", label=f"{N}-bit")
plt.xlabel("Unit-capacitor mismatch sigma_u (%)"); plt.ylabel(f"Yield, INL & DNL < {limit} LSB (%)")
plt.title("SAR ADC yield vs capacitor matching"); plt.grid(alpha=0.3); plt.legend()
plt.tight_layout(); plt.savefig("mc_yield.png", dpi=150)
print("\nSaved mc_histograms.png and mc_yield.png")
