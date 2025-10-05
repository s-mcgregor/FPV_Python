from machine import Pin

from time import sleep
import ujson, os
import hx711

# ---------- User wiring (Pico GPIO) ----------
CLK_PIN = 5   # GP5 -> HX711 CLK
DT_PIN  = 4   # GP4 -> HX711 DAT
GAIN    = 128 # channel A, high gain

# ---------- Known calibration force ----------
# 5 lb weight → Newtons (1 lbf = 4.4482216152605 N)
LBF_TO_NEWTON = 4.4482216152605
CAL_WEIGHT_LB = 5.0
CAL_FORCE_N   = CAL_WEIGHT_LB * LBF_TO_NEWTON  # ≈ 22.2411 N

# ---------- File to store calibration ----------
CAL_FILE = "hx_cal.json"

# ---------- Helpers ----------
def wait_for_enter(msg="Press ENTER to continue..."):
    print(msg)
    while True:
        s = input().strip()
        if s == "":
            return   # continue when Enter is pressed
        print("Please just press ENTER.")

def safe_remove(path):
    try:
        os.remove(path)
        print(f"Deleted old calibration: {path}")
    except OSError:
        pass

def avg_read(hx, samples=25, settle_ms=0):
    if settle_ms > 0:
        sleep(settle_ms/1000)
    return hx.read_average(samples)

# ---------- Main calibration flow ----------
def main():
    print("\n=== HX711 Calibration (Newtons) ===")
    print(f"Using 5 lb known weight = {CAL_FORCE_N:.6f} N")
    print("Load cell rated capacity mentioned: 10 kg (info only).\n")

    # Remove any previous calibration
    safe_remove(CAL_FILE)

    # Init HX711
    clk = Pin(CLK_PIN, Pin.OUT)
    dt  = Pin(DT_PIN,  Pin.IN)
    hx  = hx711.HX711(clk, dt, gain=GAIN)

    print("Letting amplifier settle...")
    sleep(1.0)

    # Step 1: Tare (no load)
    print("\nSTEP 1: Tare (no load on the cell).")
    wait_for_enter("Ensure NOTHING is attached. Press Enter to tare...")
    print("Taring (averaging 30 samples)...")
    hx.tare(30)
    # Read a baseline after tare (should be near zero, but we record it)
    raw_zero = avg_read(hx, samples=25, settle_ms=200)
    print(f"Baseline after tare (counts): {raw_zero}")

    # Step 2: Apply known weight
    print("\nSTEP 2: Apply the known weight (5 lb) to the load cell.")
    wait_for_enter("Hang the 5 lb weight now. Let it settle. Press Enter to sample...")
    raw_with_weight = avg_read(hx, samples=30, settle_ms=300)
    print(f"Reading with weight (counts): {raw_with_weight}")

    # Compute calibration: counts per Newton
    delta_counts = raw_with_weight - raw_zero
    if abs(delta_counts) < 1e-6:
        raise RuntimeError("No change detected between zero and weight. Check wiring/orientation and try again.")

    counts_per_newton = delta_counts / CAL_FORCE_N
    print(f"\nCalibration complete:")
    print(f"  Δcounts                 = {delta_counts}")
    print(f"  Known force (N)         = {CAL_FORCE_N:.6f}")
    print(f"  counts_per_newton       = {counts_per_newton:.6f} counts/N")

    # Persist calibration
    cal = {
        "version": 1,
        "gain": GAIN,
        "counts_per_newton": counts_per_newton,
        "raw_zero": raw_zero,
        "cal_force_newton": CAL_FORCE_N,
        "notes": "Use N = counts / counts_per_newton; grams = N / 9.80665 * 1000"
    }
    with open(CAL_FILE, "w") as f:
        ujson.dump(cal, f)

    print(f"\nSaved new calibration to {CAL_FILE}")
    print("You can now use this file in your main reader to report Newtons directly.\n")

if __name__ == "__main__":
    main()
