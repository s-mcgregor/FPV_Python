from machine import Pin, PWM
import utime

# ========= USER SETTINGS =========
ESC_PIN   = 0        # PWM output to ESC signal wire (GPIO number)
F_HZ      = 50       # 50 Hz (20 ms period)
MIN_US    = 1000     # 0% throttle (typical)
MAX_US    = 2000     # 100% throttle (typical)
HOLD_S    = 5        # hold at each 10% step
SAFE_OUT  = 15       # drives HIGH
SAFE_IN   = 16       # must read HIGH via the jumper to be "safe"
CHECK_MS  = 50       # safety check period during holds
# =================================

# --- PWM setup ---
p = PWM(Pin(ESC_PIN))
p.freq(F_HZ)
PERIOD_US = 1_000_000 // F_HZ  # e.g., 20,000 µs at 50 Hz

def set_pulse_us(us: int):
    if us < 0: us = 0
    duty = int(us * 65535 // PERIOD_US)
    p.duty_u16(duty)

def set_percent(percent: int):
    if percent < 0:   percent = 0
    if percent > 100: percent = 100
    us = MIN_US + (MAX_US - MIN_US) * percent // 100
    set_pulse_us(us)
    print(f"Throttle: {percent:>3}%  |  {us} µs")
    return us

# --- Safety interlock (GP15 -> GP16) ---
safe_drv = Pin(SAFE_OUT, Pin.OUT, value=1)       # drive HIGH
safe_sns = Pin(SAFE_IN,  Pin.IN,  Pin.PULL_DOWN) # expect HIGH if wire is present

def safety_ok() -> bool:
    """Return True when the jumper is detected (GP16==1)."""
    return safe_sns.value() == 1

def require_safety_stable(ms=200):
    """Ensure safety line reads HIGH consistently for ~ms before proceeding."""
    t0 = utime.ticks_ms()
    while utime.ticks_diff(utime.ticks_ms(), t0) < ms:
        if not safety_ok():
            raise RuntimeError("Safety interlock NOT present. Connect GP15 to GP16.")
        utime.sleep_ms(5)

def hold_with_safety(seconds: int):
    """Hold current throttle, but poll safety. Abort if broken."""
    end_ms = utime.ticks_add(utime.ticks_ms(), seconds * 1000)
    while utime.ticks_diff(end_ms, utime.ticks_ms()) > 0:
        if not safety_ok():
            raise RuntimeError("Safety interlock BROKEN during run. Cutting throttle.")
        utime.sleep_ms(CHECK_MS)

def kill_and_wait(msg="Throttle KILLED (safety)."):
    print(msg)
    set_percent(0)
    # Keep PWM at 0% (many ESCs expect a continuous signal).
    # Block here until safety is restored (optional behavior).
    print("Waiting for safety to be restored (GP15↔GP16 connected)...")
    while not safety_ok():
        utime.sleep_ms(100)
    print("Safety restored. Staying at 0%.")

try:
    # Confirm safety is connected before doing anything
    require_safety_stable(300)

    # Optional: show arming 0% for a moment
    set_percent(0)
    hold_with_safety(1)

    # Step 0%,10%,...,100% with HOLD_S each
    for pct in range(0, 101, 10):
        set_percent(pct)
        hold_with_safety(HOLD_S)

    print("Cutting throttle to 0%")
    set_percent(0)
    utime.sleep(1)

except RuntimeError as e:
    kill_and_wait(str(e))

finally:
    # Leave PWM running at 0% so ESC keeps getting a valid signal.
    # If you prefer to completely stop PWM output, uncomment:
    # p.deinit()
    pass
