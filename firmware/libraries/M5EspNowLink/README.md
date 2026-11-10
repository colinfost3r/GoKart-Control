# M5 ESP-NOW display transport

Optional local transport between one Heltec and its Core2. It carries the existing M5 display
JSON and fixed mode-request line. LoRa packets, the pit contract, VESC BLE ownership and motor
policy are unchanged. The first wireless build is read-only; this library is not a motor
controller or a maintenance-console bridge.

## Integration

```cpp
#include <M5EspNowLink.h>
m5now::Link displayLink;

// Once per boot, after loading the paired device and independent 16-byte keys from NVS:
displayLink.begin(m5now::Role::Display, peerMac, lmk, pmk); // Heltec uses Role::Heltec

// In the main loop, including when no VESC or GPS fix is available:
displayLink.poll(millis());
while (const char* line = displayLink.readLine(millis())) {
    // Display JSON: preserve receive age rather than declaring buffered data fresh.
    state.ingest(line, displayLink.receivedMs());
}
```

On the Heltec, pass received lines only to the existing `m5link::decode`/single-use-token gate.
Never route them into the USB command parser. Validate requests against **current** `millis()`;
`receivedMs()` is for telemetry freshness, not a way to extend request validity. Continue the
existing compile-time VESC write gate, identity/readback requirements and no-replay behavior.

`sendLine(text, now)` copies bounded text, strips one terminal LF and optional CR, and rejects
interior control bytes. The limit is **1151 bytes excluding NUL/newline**. `readLine(now)` returns
a NUL-terminated line with no newline; its pointer remains valid until the next `readLine`.
For display requests, first test `canSend(now)` before calling `state.request()`. A busy/lost
wireless link rejects the request; callers must not queue or automatically retry it.

`ready()` means the driver and encrypted peer initialized. `connected(now)` means a complete,
authenticated peer message arrived within 1500 ms. The display sends an internal authenticated
heartbeat every 500 ms while receiving the Heltec. Heartbeats are never exposed as command
lines. `channel()` reports the actual driver channel; `receivedChannel()` reports the last
callback channel; `peerChannel()` reports the authenticated advertised/proved channel.
`channelAligned(now)`, `rssi()` and `stats()` provide nonsecret diagnostics. `txLines` means MAC
confirmation of all fragments, not application acknowledgement or proof that a setting changed.
Pair changes take effect at the next boot; provision through the sketches' local USB interface.

For Core2 maintenance Wi-Fi/OTA, call `setChannelSearchEnabled(false)` **before** `WiFi.begin()`.
Continue `poll()` and ordinary telemetry processing while connecting/connected. The setter
pauses channel search, clears alignment proof/queued requests and blocks display controls. It
does not disconnect Wi-Fi, restart ESP-NOW or erase pairing. After maintenance disconnects Wi-Fi,
call `setChannelSearchEnabled(true)` to resume discovery and require fresh alignment proof.
Search defaults to enabled; the maintenance integration uses this setter on the display only.
ESP-NOW can continue on the AP's channel when both paired devices share that channel. A different
AP channel can temporarily interrupt telemetry; normal stale/lost indicators still apply.

## Framing, trust and recovery

A packet is at most 250 bytes: a 20-byte versioned header, up to 214 text bytes and a 16-byte
truncated HMAC-SHA256 tag. The header carries role, boot nonce, monotonically increasing message
ID, total length, CRC16, fragment index/count and line/heartbeat kind. A maximum-size line uses
six packets. Multibyte integers are little-endian. The packet authentication key is derived with
HMAC-SHA256 from the pair LMK and the label `GoKart M5 ESP-NOW frame auth v1`.

Only unicast traffic addressed to this device from the provisioned peer is queued. ESP-NOW
uses the explicit LMK for encryption and an independent PMK. Application HMAC verification
also rejects a spoofed source MAC if an unencrypted frame reaches the driver. There is no open
pairing, plaintext fallback, broadcast mode or source-code key. CRC detects incomplete/mixed
assembly; it is not the authentication mechanism. Treat possession of the paired keys as trust.

Callbacks only copy into bounded FreeRTOS queues; parsing, HMAC and delivery run from `poll()`.
There is one transmit packet in flight, with the next sent only after its callback. No
application retransmission exists. Queued telemetry and partial assemblies expire after 250 ms;
expired data does not become fresh when dequeued. Up to 12 telemetry lines, 32 received packets
and four completed lines are buffered. A full completed-line queue pauses packet draining until
the caller reads it, preserving earlier self/metadata lines in a burst. Packet-queue overload
still drops data and increments counters. A display
request must fit one packet and is accepted only while the transport is linked and idle.

Duplicate completed message IDs are rejected. Fragments can arrive out of order; identical
partial duplicates do not extend their deadline. Four retired sender boot nonces are retained
to reject recent old-session replay. This bounded cache is not a persistent replay database;
future write-capable use must still require the Heltec's existing fresh single-use command token.

The Heltec preserves its Wi-Fi station channel, including an existing AP/OTA connection. The
Core2 normally does not join an AP or reuse stored Wi-Fi credentials: it disables reconnect and searches
US channels 1–11, dwelling 650 ms per channel after loss. Authentication alone is not channel
alignment: adjacent-channel reception was observed on the bench. Updated peers exchange the
proof below before enabling commands. Channel recovery can take several seconds and must
be measured alongside VESC BLE, OLED refresh, LoRa and OTA. Accessory radio loss never restores,
stops or otherwise changes VESC state.

## Channel alignment protocol

Framing remains v1. Two reserved 26-character authenticated `Line` payloads are consumed by the
transport and never passed to the JSON/mode parser:

- `G5CH1,CC,challengeHex,grantDisplayBootHex`: Heltec actual channel and current challenge; grant
  is zero until a fresh matching acknowledgement proves the current display boot.
- `G5CA1,CC,challengeHex,00000000`: Core2 acknowledgement on the advertised channel.

Channels are decimal 01–11; challenge/grant are eight lowercase hex digits. Records are sent
opportunistically every 500 ms when the transmitter is idle. A Heltec channel/peer-boot change
rotates its challenge and invalidates old grants/queued requests. Core2 retunes only outside
maintenance, Wi-Fi association/scanning and in-flight/queued TX, then requires a **new** record
received on its actual matching channel with a grant naming its own boot. Both sides check
freshness; callback and completed-line epochs reject proof or requests buffered before changes.
The Heltec rechecks its actual driver channel at final request dispatch as well as polling/TX.

Old/new pairs retain telemetry but cannot control: **update both accessory images** before testing
mode commands. A complete authenticated telemetry message is not an alignment grant. Transport
proof is additional to the existing application token, VESC identity/config checks and read-only
build gate; it does not alter VESC state on loss, channel change, maintenance or restart.

## Validation and limits

`python3 -I firmware/tests/test_m5_espnow.py` runs the native framing checks under address and
undefined-behavior sanitizers: maximum size, loss/recovery, reordering, duplicate/replay, changed
sender boot, malformed headers, CRC corruption, timeout and clock wrap. These are host framing
checks, not over-the-air encryption, latency, BLE coexistence or eight-kart throughput evidence.
The same command also runs pure alignment-state and actual adapter queue/callback tests. The
adapter harness substitutes a deterministic test MAC to verify authentication ordering/rejection;
it is not a test of cryptographic strength. Exact channel/recovery/range acceptance remains pending.
The native framing test does not exercise the runtime HMAC verifier: wrong-key/header/payload/tag
tamper acceptance remains a separate verification item. Hardware acceptance and actual installed
image hashes belong in the project handoff.

Protocol choices follow [Espressif's ESP-NOW documentation](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32/api-reference/network/esp_now.html):
peers share a Wi-Fi channel, encrypted unicast requires matching peer keys, packets are limited
to 250 bytes for v1 interoperability, and callbacks run on the Wi-Fi task. The adapter uses the
ESP-IDF 5.5 send/receive callback signatures shipped with the pinned ESP32 Arduino core 3.3.8.
