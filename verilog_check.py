"""Cross-check the Verilog SAR logic against the Python model.

Three ways to run it:
  python verilog_check.py            full automatic check with Icarus Verilog (iverilog + vvp installed)
  python verilog_check.py generate   only write weights.txt and inputs.txt (for a Vivado simulation)
  python verilog_check.py compare    compare codes_verilog.txt (written by the testbench) with Python
"""
import subprocess, sys, numpy as np
from sar_model import make_weights, sar_convert

N = 10
rng = np.random.default_rng(21)

def make_files(sigma_u):
    w = make_weights(N, sigma_u, rng)
    ramp = (np.arange(1024 * 8) + 0.5) / 8
    edges = np.array([0.0, 0.25, 1.0, 511.999, 512.0, 512.001, 1023.0, 1023.75])
    ints = np.arange(0, 1024, dtype=float)                 # exact integers (tie cases for an ideal chip)
    rand = rng.uniform(0, 1024, 3000)
    np.savetxt("weights.txt", w, fmt="%.12f")
    np.savetxt("inputs.txt", np.concatenate([edges, ints, ramp, rand]), fmt="%.12f")

def compare(name, sigma_u):
    verilog = np.loadtxt("codes_verilog.txt", dtype=int)
    w_file, v_file = np.loadtxt("weights.txt"), np.loadtxt("inputs.txt")   # exactly what the Verilog read
    python = sar_convert(v_file, w_file)
    bad = int(np.sum(verilog != python))
    print(f"[{name}] inputs: {len(v_file)}   mismatches Verilog vs Python: {bad}")
    if sigma_u == 0:
        print("        ideal chip, output equals floor(Vin) for every input:",
              bool(np.all(verilog == np.minimum(np.floor(v_file), 1023))))
    return bad

mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
if mode == "generate":
    make_files(0.01); print("Wrote weights.txt and inputs.txt (1% mismatch chip)")
elif mode == "compare":
    raise SystemExit(compare("from testbench", 0.01))
else:
    total = 0
    for name, s in (("ideal", 0.0), ("1% mismatch", 0.01), ("3% mismatch", 0.03)):
        make_files(s)
        subprocess.run(["iverilog", "-g2005", "-o", "sim.vvp", "sar_logic.v", "tb_sar.v"], check=True)
        subprocess.run(["vvp", "sim.vvp"], capture_output=True)
        total += compare(name, s)
    print("ALL MATCH" if total == 0 else f"{total} mismatches")
