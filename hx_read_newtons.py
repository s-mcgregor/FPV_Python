from machine import Pin
from time import sleep
import ujson, hx711

CLK_PIN, DT_PIN = 5, 4
hx = hx711.HX711(Pin(CLK_PIN, Pin.OUT), Pin(DT_PIN, Pin.IN), gain=128)

with open("hx_cal.json") as f:
    cal = ujson.load(f)

CPN = cal["counts_per_newton"]      # counts per Newton
ZERO = cal["raw_zero"]

def read_newtons(samples=10):
    counts = hx.read_average(samples)
    return (counts - ZERO) / CPN    # N = (counts - zero) / (counts_per_newton)

while True:
    F = read_newtons(20)
    print("{:.3f} N".format(F))
    sleep(0.3)