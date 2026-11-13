#!/bin/bash
# Bluetooth speaker for the kart dash (2026-11-13: an MZ_1688 speaker on each of karts 1 and 2).
# The dash's sounds (Chromium -> PipeWire) come out of the speaker whenever it is connected and
# out of the HDMI panel otherwise (config/wireplumber/*.conf). This script keeps it connected.
#
#   sudo bt_speaker.sh watch     the service (gokart-bt-speaker.service, root): every 10 s make
#                                sure the adapter is up and the speaker named in server/config.json
#                                ("bt_speaker": "41:42:..") is connected
#   bt_speaker.sh pair [MAC]     as the kart user, speaker in pairing mode: with no MAC, scan 20 s
#                                and list the audio devices seen; with a MAC, pair + trust + connect,
#                                make it the default sink, write it to config.json, play the test tone
#   bt_speaker.sh status         adapter / speaker / PipeWire sinks on one screen
#   bt_speaker.sh test           a short tone through PipeWire's default sink (as the kart user)
#
# Adapter recovery: kart 2's Pi 3 B came up with hci0 registered but the chip not answering
# ("command tx timeout"; bluetoothctl: No default controller). Re-binding the UART driver
# power-cycles the chip and it answers again; `watch` does that whenever `power on` fails.
# A2DP is registered with bluetoothd by WirePlumber in the kart user's session (linger keeps that
# session up from boot); a connect before it is up fails (br-connection-profile-unavailable) and
# is simply retried on the next round.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${GOKART_CONFIG:-$ROOT/server/config.json}"
TAG=gokart-bt-speaker

cfg_mac() { python3 - "$CFG" <<'PY' 2>/dev/null
import json, sys
try:
    v = json.load(open(sys.argv[1])).get("bt_speaker")
except (OSError, ValueError):
    v = None
print(v.strip().upper() if isinstance(v, str) else "")
PY
}
cfg_set_mac() { python3 - "$CFG" "$1" <<'PY'
import json, sys
p, mac = sys.argv[1], sys.argv[2]
try:
    cfg = json.load(open(p))
except (OSError, ValueError):
    cfg = {}
cfg["bt_speaker"] = mac
with open(p, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print(f"{p}: bt_speaker = {mac}")
PY
}
hci_ok() { hciconfig hci0 2>/dev/null | grep -q "UP RUNNING"; }
connected() { bluetoothctl info "$1" 2>/dev/null | grep -q "Connected: yes"; }
KART_USER="${GOKART_KART_USER:-kart}"
sink_up() {   # root: does the kart user's PipeWire have the speaker's A2DP sink? (connected in bluez is not enough)
  runuser -u "$KART_USER" -- env XDG_RUNTIME_DIR="/run/user/$(id -u "$KART_USER")" wpctl status -n 2>/dev/null \
    | sed -n '/Sinks:/,/Sources:/p' | grep -q "bluez_output.${1//:/_}"
}
sink_id() {   # PipeWire node id of the speaker's A2DP sink, empty when it is not connected
  wpctl status -n 2>/dev/null | sed -n '/Sinks:/,/Sources:/p' | grep "bluez_output.${1//:/_}" | grep -oE '[0-9]+\.' | head -1 | tr -d .
}

adapter_up() {   # root: unblock + power on; when the chip does not answer, power-cycle it through the UART driver
  rfkill unblock bluetooth 2>/dev/null
  bluetoothctl power on >/dev/null 2>&1; sleep 1
  hci_ok && return 0
  for drv in /sys/bus/serial/drivers/hci_uart_*/; do
    for dev in "$drv"serial*; do
      [ -e "$dev" ] || continue
      n="$(basename "$dev")"
      logger -t $TAG "hci0 not answering: re-binding $n to $(basename "$drv")"
      echo "$n" > "$drv/unbind" 2>/dev/null; sleep 2; echo "$n" > "$drv/bind" 2>/dev/null; sleep 4
    done
  done
  bluetoothctl power on >/dev/null 2>&1; sleep 1
  hci_ok
}

watch() {
  [ "$(id -u)" = 0 ] || { echo "watch runs as root (gokart-bt-speaker.service)"; exit 1; }
  last=""
  while :; do
    mac="$(cfg_mac)"
    if [ -z "$mac" ]; then sleep 30; continue; fi          # no speaker configured: nothing to do
    systemctl is-active --quiet bluetooth || systemctl start bluetooth
    bluetoothctl discoverable off >/dev/null 2>&1; bluetoothctl pairable off >/dev/null 2>&1   # invisible to the other kart and to phones
    if ! hci_ok; then
      if adapter_up; then logger -t $TAG "Bluetooth adapter up"
      else [ "$last" != noadapter ] && logger -t $TAG "no usable Bluetooth adapter (hci0)"; last=noadapter; sleep 20; continue; fi
    fi
    if connected "$mac"; then
      if sink_up "$mac"; then
        [ "$last" != up ] && logger -t $TAG "speaker $mac connected"
        last=up; nosink=0
      else                                                    # bluez says connected but PipeWire has no sink
        nosink=$(( ${nosink:-0} + 1 ))                        # (profile failed / WirePlumber not up yet): sounds
        if [ "$nosink" -ge 3 ]; then                          # would go to the HDMI panel; drop and reconnect
          logger -t $TAG "speaker $mac connected without an audio sink for 30 s; reconnecting"
          bluetoothctl disconnect "$mac" >/dev/null 2>&1; nosink=0; last=down
        fi
      fi
    else
      [ "$last" = up ] && logger -t $TAG "speaker $mac dropped; reconnecting until it is back"
      last=down
      timeout 25 bluetoothctl connect "$mac" >/dev/null 2>&1 || true
    fi
    sleep 10
  done
}

tone() {   # 1.1 s three-note jingle, generated on the spot (no audio files in the repo)
  python3 - "$1" <<'PY'
import math, struct, sys, wave
sr, frames = 44100, bytearray()
for f, dur in ((440, 0.3), (554, 0.3), (659, 0.5)):
    n = int(sr * dur)
    for i in range(n):
        env = min(1.0, i / (sr * 0.01)) * min(1.0, (n - i) / (sr * 0.05))
        v = int(12000 * env * math.sin(2 * math.pi * f * i / sr))
        frames += struct.pack("<hh", v, v)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(bytes(frames))
PY
}
test_tone() {
  f="${XDG_RUNTIME_DIR:-/tmp}/gokart-bt-tone.wav"
  tone "$f" && timeout 15 pw-play "$f" && echo "tone played on: $(wpctl status 2>/dev/null | sed -n '/Sinks:/,/Sources:/p' | grep '\*' | sed 's/.*[0-9]\. //')"
}

pair() {
  mac="${1:-}"
  bluetoothctl power on >/dev/null 2>&1; bluetoothctl pairable on >/dev/null 2>&1
  if [ -z "$mac" ]; then
    echo "scanning 20 s for audio devices (put the speaker in pairing mode)..."
    bluetoothctl --timeout 20 scan on >/dev/null 2>&1
    bluetoothctl devices | while read -r _ m rest; do
      cls="$(bluetoothctl info "$m" 2>/dev/null | sed -n 's/^\s*Class: //p' | awk '{print $1}')"
      [ -n "$cls" ] && [ $(( (cls >> 8) & 0x1f )) -eq 4 ] && echo "  $m  $rest"
    done
    echo "then: $0 pair MAC"
    return 0
  fi
  mac="$(echo "$mac" | tr a-f A-F)"
  bluetoothctl --timeout 25 scan on >/dev/null 2>&1 &
  p="/org/bluez/hci0/dev_${mac//:/_}"
  for _ in $(seq 1 25); do busctl get-property org.bluez "$p" org.bluez.Device1 RSSI >/dev/null 2>&1 && break; sleep 1; done
  echo "pair:    $(bluetoothctl pair "$mac" 2>&1 | tail -1)"
  bluetoothctl scan off >/dev/null 2>&1; wait
  bluetoothctl pairable off >/dev/null 2>&1      # pairing is this command only; the Pi never accepts a pairing from outside
  echo "trust:   $(bluetoothctl trust "$mac" 2>&1 | tail -1)"
  echo "connect: $(bluetoothctl connect "$mac" 2>&1 | tail -1)"
  sleep 4
  id="$(sink_id "$mac")"
  if [ -n "$id" ]; then
    wpctl set-default "$id" && wpctl set-volume "$id" 1.0 && echo "default sink -> $id ($mac); WirePlumber remembers it"
  else
    echo "no PipeWire sink for $mac yet (speaker connected? wireplumber running in this session?)"
  fi
  cfg_set_mac "$mac"
  test_tone
}

status() {
  echo "adapter:   $(hciconfig hci0 2>/dev/null | sed -n 3p | xargs)  bluetooth.service: $(systemctl is-active bluetooth 2>/dev/null)  rfkill soft-blocked: $(rfkill list bluetooth 2>/dev/null | grep -c 'Soft blocked: yes')"
  mac="$(cfg_mac)"
  echo "config:    bt_speaker = ${mac:-none}"
  [ -n "$mac" ] && echo "speaker:   $(bluetoothctl info "$mac" 2>/dev/null | grep -E 'Name|Paired|Trusted|Connected' | xargs)"
  echo "pipewire:  $(systemctl --user is-active pipewire 2>/dev/null)  wireplumber: $(systemctl --user is-active wireplumber 2>/dev/null)  keeper: $(systemctl is-active gokart-bt-speaker 2>/dev/null)"
  wpctl status 2>/dev/null | sed -n '/Sinks:/,/Sources:/p'
}

case "${1:-}" in
  watch) watch ;;
  pair) pair "${2:-}" ;;
  status) status ;;
  test) test_tone ;;
  *) sed -n '2,15p' "$0"; exit 1 ;;
esac
