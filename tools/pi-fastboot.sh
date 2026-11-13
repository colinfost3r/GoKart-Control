#!/bin/bash
# tools/pi-fastboot.sh: make the GoKart Pis boot faster (pit Pi 4, kart Pi 3 B kiosks).
# A provisioned kiosk does per-boot work it never needs; the driver waits on it at every key-on.
# Run as root on the Pi:
#   sudo bash pi-fastboot.sh            apply
#   sudo bash pi-fastboot.sh --revert   undo (re-enable services, cloud-init, serial console)
# The revert re-adds console=serial0,115200 even if an image never had it; both 2026-11 images do.
set -u
[ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
REVERT=0; [ "${1:-}" = "--revert" ] && REVERT=1

# Services/timers a provisioned GoKart Pi never needs at boot:
#   NetworkManager-wait-online: nothing waits for the network (the gokart units say so explicitly);
#   apt/man-db/eeprom/e2scrub: maintenance, run by hand when updating (apt-get still works);
#   udisks2: no removable-media automount on a kiosk.
#   bluetooth.service STAYS: the kart dash speakers are Bluetooth (kart/tools/bt_speaker.sh, 2026-11-13).
UNITS="NetworkManager-wait-online.service apt-daily.timer apt-daily-upgrade.timer man-db.timer
       rpi-eeprom-update.service udisks2.service e2scrub_all.timer"
for u in $UNITS; do
  systemctl cat "$u" >/dev/null 2>&1 || continue
  if [ "$REVERT" = 1 ]; then systemctl enable "$u" >/dev/null 2>&1 && echo "enabled  $u"
  else systemctl disable "$u" >/dev/null 2>&1 && echo "disabled $u"; fi
done

# cloud-init provisions on the FIRST boot only (NoCloud), but its four services still cost
# seconds on every boot after. The supported off switch is this flag file; the Wi-Fi profiles
# and users it wrote are ordinary files and stay.
if [ "$REVERT" = 1 ]; then rm -f /etc/cloud/cloud-init.disabled; echo "cloud-init re-enabled"
else touch /etc/cloud/cloud-init.disabled; echo "cloud-init disabled (provisioning already ran)"; fi

# Firmware: no rainbow splash, no pre-kernel delay.
CFG=/boot/firmware/config.txt
if [ "$REVERT" = 1 ]; then sed -i '/^# pi-fastboot/,+2d' "$CFG"; echo "config.txt restored"
elif ! grep -q '^# pi-fastboot' "$CFG"; then
  printf '# pi-fastboot\ndisable_splash=1\nboot_delay=0\n' >> "$CFG"
  echo "config.txt: splash off, boot_delay 0"
fi

# Kernel cmdline: drop the serial console (nothing is attached; printk at 115200 baud is slow,
# worst on the Pi 3 B) and go quiet. console=tty1 stays, so boot text is still on HDMI if needed.
python3 - "$REVERT" <<'PY'
import sys
p = "/boot/firmware/cmdline.txt"
line = open(p).read().strip()
args = line.split()
if sys.argv[1] == "1":
    args = [a for a in args if a != "quiet"]
    if "console=serial0,115200" not in args:
        args.insert(0, "console=serial0,115200")
else:
    args = [a for a in args if a != "console=serial0,115200"]
    if "quiet" not in args:
        args.append("quiet")
new = " ".join(args)
if new != line:
    open(p, "w").write(new + "\n")
    print("cmdline.txt:", new)
PY

echo "done: reboot to take effect, then check with systemd-analyze time"
