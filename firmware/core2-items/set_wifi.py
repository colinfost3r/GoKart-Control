#!/usr/bin/env python3
"""One-time Core2 Wi-Fi setup for OTA (core2-0.3.0+): sends `wifi SSID PASS` over USB serial,
reading the credentials from kart/sdcard/secrets.env (WIFI_SSID / WIFI_PASSWORD) so they are
never typed into a shell history or shown on screen. The sketch stores them in NVS; every
later update then goes over the air (espota.py -i gokart-core2.local).

  python3 set_wifi.py /dev/cu.usbserial-XXXX [path/to/secrets.env]
"""
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pip install pyserial")


def read_secrets(path):
    kv = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip().strip('"').strip("'")
    return kv


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    port = sys.argv[1]
    env = sys.argv[2] if len(sys.argv) > 2 else "kart/sdcard/secrets.env"
    kv = read_secrets(env)
    ssid, pw = kv.get("WIFI_SSID", ""), kv.get("WIFI_PASSWORD", "")
    if not ssid or not pw:
        sys.exit(f"{env}: WIFI_SSID / WIFI_PASSWORD not set")
    s = serial.Serial()
    s.port, s.baudrate, s.timeout = port, 115200, 2
    s.dtr = s.rts = False        # asserted DTR/RTS resets or holds the ESP32 via the usb bridge
    s.open()
    time.sleep(3)
    s.reset_input_buffer()
    s.write(f"wifi {ssid} {pw}\n".encode())
    s.flush()
    deadline = time.time() + 30
    while time.time() < deadline:
        line = s.readline().decode(errors="replace").strip()
        if not line:
            continue
        print(line.replace(pw, "<password>"))
        if line.startswith("wifi ") and ("ota" in line or "stored" in line):
            if "ota" in line:
                break
    s.close()


if __name__ == "__main__":
    main()
