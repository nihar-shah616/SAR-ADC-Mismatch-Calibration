"""Day 3: digital calibration of SAR bit weights.

Idea: the SAR decides each bit with the REAL weights w_i, but the output code reads them as 2**i.
If we measure the real weights, we can rebuild the output as  y = c + sum_i b_i * w_hat_i.
Only N+1 numbers are needed (N weights and an offset), instead of a 2**N-entry lookup table.

Steps in this file
  1. sar_bits():  SAR conversion that returns the raw bits (needed for calibration).
  2. calibrate_weights(): least-squares fit  Vin = c + sum b_i w_i  on known calibration inputs.
  3. Compare: raw code, weight calibration, lookup table (LUT), small neural network.
  4. Experiments: noiseless chip, how many calibration samples are needed with noise,
     and what happens when mismatch is so large that the SAR makes wrong decisions.

Run:  python sar_calibration.py     (needs numpy, matplotlib, scikit-learn; sar_model.py in the same folder)
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sar_model import make_weights

N = 10
L = 2 ** N
SIGMA_U = 0.03                                             # unit-capacitor mismatch of the chip under test
rng = np.random.default_rng(5)

# ------------------------------------------------------------------ 1. SAR with bits
def sar_bits(vin, w):
    """Same search as sar_convert, but returns the bit matrix (n_samples x N), MSB first."""
    acc = np.zeros_like(vin, dtype=float)
    bits = np.zeros((len(vin), len(w)), dtype=float)
    for j, i in enumerate(range(len(w) - 1, -1, -1)):
        trial = acc + w[i]
        keep = vin >= trial
        acc = np.where(keep, trial, acc)
        bits[:, j] = keep
    return bits                                            # column j is bit (N-1-j)

def code_from_bits(bits):
    return (bits @ (2.0 ** np.arange(len(bits[0]) - 1, -1, -1))).astype(int)

# ------------------------------------------------------------------ 2. calibration
def calibrate_weights(bits, vin_true):
    """Least squares: vin_true = c + bits @ w. Returns (w_hat in MSB-first order, c)."""
    A = np.hstack([bits, np.ones((len(bits), 1))])
    sol, *_ = np.linalg.lstsq(A, vin_true, rcond=None)
    return sol[:-1], sol[-1]

def build_lut(codes, vin_true):
    """One estimate per output code = mean of the true inputs that produced it."""
    s = np.bincount(codes, weights=vin_true, minlength=L)
    n = np.bincount(codes, minlength=L)
    lut = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    missing = np.isnan(lut)
    lut[missing] = np.arange(L)[missing] + 0.5            # fall back to the ideal bin centre
    return lut

# ------------------------------------------------------------------ 3. metrics
NFFT, M_TEST = 2 ** 14, 1013
def metrics(y, M=M_TEST):
    y = y - y.mean()
    P = np.abs(np.fft.rfft(y)) ** 2
    P[0] = 0
    sig = P[M]
    sinad = 10 * np.log10(sig / (P.sum() - sig))
    sfdr = 10 * np.log10(sig / np.delete(P, [0, M]).max())
    return sinad, (sinad - 1.76) / 6.02, sfdr

def test_sine(noise, amp=0.95):
    n = np.arange(NFFT)
    clean = L / 2 + amp * L / 2 * np.sin(2 * np.pi * M_TEST * n / NFFT + 0.3)
    return clean, clean + noise * rng.standard_normal(NFFT)

def cal_data(count, noise):
    v = rng.uniform(0, L, count)                           # known calibration inputs
    return v, v + noise * rng.standard_normal(count)       # (true value, what the ADC sees)

# ------------------------------------------------------------------ experiment 1: noiseless
w_true = make_weights(N, SIGMA_U, rng)
v_true, v_adc = cal_data(100000, 0.0)
bits_c = sar_bits(v_adc, w_true)
w_hat_msb, c = calibrate_weights(bits_c, v_true)
w_hat = w_hat_msb[::-1]                                    # LSB-first, same order as w_true
print(f"Experiment 1: noiseless calibration, {SIGMA_U*100:.0f}% mismatch chip, 100,000 calibration samples")
print("  true weight errors e_i (LSB):      ", np.round(w_true - 2.0 ** np.arange(N), 3))
print("  estimated weight errors (LSB):     ", np.round(w_hat - 2.0 ** np.arange(N), 3))
print(f"  max error of weight estimates: {np.abs(w_hat - w_true).max():.4f} LSB,  offset c = {c:.3f}")

codes_c = code_from_bits(bits_c)
lut = build_lut(codes_c, v_true)
tr = rng.choice(len(v_true), 20000, replace=False)
sc = StandardScaler().fit((codes_c[tr] / L).reshape(-1, 1))
mlp = MLPRegressor(hidden_layer_sizes=(32, 32), activation="tanh", max_iter=400, early_stopping=True, random_state=0).fit(
    sc.transform((codes_c[tr] / L).reshape(-1, 1)), v_true[tr] - (codes_c[tr] + 0.5))

clean, seen = test_sine(0.0)
bits_t = sar_bits(seen, w_true)
codes_t = code_from_bits(bits_t)
outs = {
    "Raw code": codes_t + 0.5,
    "Weight calibration (11 numbers)": c + bits_t @ w_hat_msb,
    "LUT (1024 numbers)": lut[codes_t],
    "Neural network on code": codes_t + 0.5 + mlp.predict(sc.transform((codes_t / L).reshape(-1, 1))),
}
ideal = np.floor(clean) + 0.5
print(f"\n  {'Output':34s}{'RMS err (LSB)':>14s}{'SINAD (dB)':>12s}{'ENOB':>8s}{'SFDR (dBc)':>12s}")
for name, y in {"Ideal ADC": ideal, **outs}.items():
    s, e, f = metrics(y)
    print(f"  {name:34s}{np.sqrt(np.mean((y - clean) ** 2)):14.3f}{s:12.2f}{e:8.2f}{f:12.2f}")

# ------------------------------------------------------------------ experiment 2: noise and calibration size
NOISE = 0.3
print(f"\nExperiment 2: input noise {NOISE} LSB rms. RMS static error (LSB) vs number of calibration samples")
sizes = [1000, 3000, 10000, 30000, 100000, 300000]
res = {"Weights": [], "LUT": []}
clean_n, seen_n = test_sine(NOISE)
bt = sar_bits(seen_n, w_true); ct = code_from_bits(bt)
base = np.sqrt(np.mean((np.floor(seen_n) + 0.5 - clean_n) ** 2))
raw = np.sqrt(np.mean((ct + 0.5 - clean_n) ** 2))
for n in sizes:
    vt, va = cal_data(n, NOISE)
    b = sar_bits(va, w_true)
    wh, ch = calibrate_weights(b, vt)
    lt = build_lut(code_from_bits(b), vt)
    res["Weights"].append(np.sqrt(np.mean((ch + bt @ wh - clean_n) ** 2)))
    res["LUT"].append(np.sqrt(np.mean((lt[ct] - clean_n) ** 2)))
print(f"  reference: ideal ADC with the same noise = {base:.3f}, uncalibrated chip = {raw:.3f}")
print(f"  {'samples':>10s}{'weights':>10s}{'LUT':>10s}")
for n, a, b_ in zip(sizes, res["Weights"], res["LUT"]):
    print(f"  {n:10d}{a:10.3f}{b_:10.3f}")

# ------------------------------------------------------------------ experiment 3: very large mismatch
print("\nExperiment 3: large mismatch (decision errors). 100 chips each, 20,000 noiseless calibration samples")
for s in (0.01, 0.03, 0.06):
    frac, rms = [], []
    for _ in range(100):
        w = make_weights(N, s, rng)
        vt, va = cal_data(20000, 0.0)
        b = sar_bits(va, w)
        wh, ch = calibrate_weights(b, vt)
        resid = vt - (ch + b @ wh)
        rms.append(np.sqrt(np.mean(resid ** 2)))
        frac.append(np.mean(np.abs(resid) > 1.0) * 100)
    print(f"  sigma_u = {s*100:.0f}%: median RMS residual {np.median(rms):.3f} LSB (ideal 0.289),"
          f"  samples with |residual| > 1 LSB: {np.median(frac):.2f}%")

# ------------------------------------------------------------------ plots
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
ax[0].bar(np.arange(N) - 0.2, w_true - 2.0 ** np.arange(N), 0.4, label="true")
ax[0].bar(np.arange(N) + 0.2, w_hat - 2.0 ** np.arange(N), 0.4, label="estimated")
ax[0].set_xlabel("bit i"); ax[0].set_ylabel("weight error (LSB)"); ax[0].legend(); ax[0].grid(alpha=0.3)
ax[0].set_title("Weight errors: true vs estimated")
ax[1].loglog(sizes, res["LUT"], "o-", label="LUT (1024 entries)")
ax[1].loglog(sizes, res["Weights"], "s-", label="Weights (11 numbers)")
ax[1].axhline(base, color="gray", ls="--", label="ideal ADC, same noise")
ax[1].set_xlabel("calibration samples"); ax[1].set_ylabel("RMS static error (LSB)")
ax[1].set_title(f"Calibration cost with {NOISE} LSB noise"); ax[1].legend(); ax[1].grid(alpha=0.3, which="both")
plt.tight_layout(); plt.savefig("sar_calibration.png", dpi=150); plt.close()

fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True, sharey=True)
fr = np.arange(NFFT // 2 + 1) / NFFT
for a, name in zip(ax, ["Raw code", "Weight calibration (11 numbers)", "LUT (1024 numbers)"]):
    y = outs[name] - outs[name].mean(); S = np.abs(np.fft.rfft(y)); S = 20 * np.log10(S / S[M_TEST] + 1e-12)
    a.plot(fr, S, lw=0.6); a.set_ylim(-110, 5); a.grid(alpha=0.3)
    a.set_title(f"{name}: SFDR = {metrics(outs[name])[2]:.1f} dBc, ENOB = {metrics(outs[name])[1]:.2f}"); a.set_ylabel("dBc")
ax[-1].set_xlabel("Frequency (fraction of fs)"); plt.tight_layout(); plt.savefig("sar_spectra.png", dpi=150)
print("\nSaved sar_calibration.png and sar_spectra.png")
