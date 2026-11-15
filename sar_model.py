"""Day 1: behavioural model of an N-bit charge-redistribution SAR ADC with capacitor mismatch.

What this file does
  1. make_weights(): builds the bit weights of a binary-weighted capacitor DAC in which every unit
     capacitor has a random relative error (mismatch).
  2. sar_convert():  runs the SAR binary search (MSB first) using those actual weights.
  3. static_metrics(): measures transition levels with a slow ramp and returns INL and DNL.
  4. Prints a sanity check (ideal chip) and results for one mismatched chip, and saves a plot.

Run:  python sar_model.py       (needs numpy, matplotlib)
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ------------------------------------------------------------------ 1. capacitor DAC weights
def make_weights(N, sigma_u, rng):
    """Actual bit weights, in LSB, for a binary-weighted capacitor array.

    Bit i is built from 2**i unit capacitors. Each unit has relative error ~ N(0, sigma_u^2),
    so a group of m units has a standard deviation of sigma_u*sqrt(m) (in unit-capacitor values):
    big capacitors are *relatively* more accurate, but their *absolute* error is larger.
    One extra dummy unit capacitor completes the array (total ideal value = 2**N units).
    The weights are normalised by the actual total capacitance, so a perfect array gives 2**i.
    """
    units = 2.0 ** np.arange(N)
    C = units + sigma_u * np.sqrt(units) * rng.standard_normal(N)
    dummy = 1.0 + sigma_u * rng.standard_normal()
    return (2 ** N) * C / (C.sum() + dummy)

# ------------------------------------------------------------------ 2. SAR conversion
def sar_convert(vin_lsb, w):
    """SAR binary search. vin_lsb: input in LSB (0 .. 2**N). w: actual bit weights (MSB last).

    For each bit from MSB to LSB: tentatively set the bit, compare the input with the DAC output
    (acc + w[i]); keep the bit if the input is larger. The output code is read with ideal
    binary weights 2**i, which is exactly what a real digital output would be."""
    N = len(w)
    acc = np.zeros_like(vin_lsb, dtype=float)
    code = np.zeros(vin_lsb.shape, dtype=int)
    for i in range(N - 1, -1, -1):
        trial = acc + w[i]
        keep = vin_lsb >= trial
        acc = np.where(keep, trial, acc)
        code += keep.astype(int) << i
    return code

# ------------------------------------------------------------------ 3. static test (ramp)
def static_metrics(w, pts_per_lsb=20):
    """Transition levels from a slow ramp -> INL, DNL (both in LSB).

    T[k] is the input at which the output first reaches code k.
    DNL[k] = (T[k+1] - T[k]) - 1      (width of code k minus one LSB)
    INL[k] = T[k] - k, endpoint-fit (offset and gain error removed)."""
    N = len(w)
    L = 2 ** N
    ramp = (np.arange(L * pts_per_lsb) + 0.5) / pts_per_lsb
    codes = sar_convert(ramp, w)
    T = np.full(L, np.nan)
    for k in range(1, L):
        j = np.argmax(codes >= k)
        if codes[j] >= k:
            T[k] = ramp[j]
    k = np.arange(1, L)
    t = T[1:]
    ok = ~np.isnan(t)
    INL_raw = t - k
    p = np.polyfit(k[ok], INL_raw[ok], 1)
    INL = INL_raw - np.polyval(p, k)
    DNL = np.diff(t) - 1.0
    return k, INL, DNL

if __name__ == "__main__":
    rng = np.random.default_rng(7)
    N = 10

    # sanity check: a perfect array must give ~0 INL and DNL
    k, inl, dnl = static_metrics(make_weights(N, 0.0, rng))
    print(f"Ideal array (sigma_u = 0):   max|INL| = {np.nanmax(abs(inl)):.3f} LSB,  max|DNL| = {np.nanmax(abs(dnl)):.3f} LSB")

    # one mismatched chip
    sigma_u = 0.01                         # 1% unit-capacitor mismatch
    w = make_weights(N, sigma_u, rng)
    print(f"\nOne chip, sigma_u = {sigma_u*100:.1f}%")
    print("Ideal weights :", np.round(2.0 ** np.arange(N), 3))
    print("Actual weights:", np.round(w, 3))
    print("Weight error  :", np.round(w - 2.0 ** np.arange(N), 3), "(LSB)")
    k, inl, dnl = static_metrics(w)
    print(f"max|INL| = {np.nanmax(abs(inl)):.2f} LSB,  max|DNL| = {np.nanmax(abs(dnl)):.2f} LSB")
    worst = np.nanargmax(abs(dnl))
    print(f"Largest DNL error is at code {k[1:][worst]} (binary {k[1:][worst]:010b})")

    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].plot(k, inl, lw=0.8); ax[0].set_ylabel("INL (LSB)"); ax[0].grid(alpha=0.3)
    ax[0].set_title(f"{N}-bit SAR ADC, unit-capacitor mismatch sigma = {sigma_u*100:.1f}% (one chip)")
    ax[1].plot(k[1:], dnl, lw=0.8); ax[1].set_ylabel("DNL (LSB)"); ax[1].set_xlabel("Output code")
    ax[1].grid(alpha=0.3)
    for a in ax:
        for c in (256, 512, 768):
            a.axvline(c, color="gray", lw=0.5, ls="--")
    plt.tight_layout(); plt.savefig("sar_inl_dnl.png", dpi=150)
    print("\nSaved sar_inl_dnl.png")
