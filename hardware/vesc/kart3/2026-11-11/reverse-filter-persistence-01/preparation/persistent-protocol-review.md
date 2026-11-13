# Pinned VESC 6.02 persistent Lisp installation audit

Scope: offline protocol/source review only. No hardware access, project edit or flash writer was performed here. The owner requested applying the successfully tested filter; the root agent owns hardware authorization, physical readiness and installation.

## Recommendation

Use a separately reviewed, fixed-package installer with current kart identity, complete application/configuration checks, joined filter stop and matching-RX rollback before erase; then one erase, bounded one-shot writes with exact offset ACKs, full stored-code readback, and separately verified execution/normal boot. Preserve motor/app bytes and all Hall/pedal calibration. Do not introduce a firmware upgrade or motor-control command.

VESC Tool 6.02 already supports persistent Lisp Upload. However, its official uploader writes the header first, retries chunks up to five times and ignores the ACK offset. Its Auto Run checkbox only controls immediate execution after upload. For this specific kart, the small fixed installer can retain the UUID/full-app pins and no-retry rules already used by the project. Do not use STREAM139 for persistence or recovery.

## Most important semantic distinction

**Valid stored Lisp automatically runs on a normal VESC boot. There is no Lisp autostart flag in this firmware.** Header flags exist and participate in CRC, but stock 6.02's Lisp initialization does not inspect them. `lispif_init` calls `lispif_restart(false, true)` except after watchdog reset/first-watchdog fault. Code containing definitions alone stays functionally disarmed; a reviewed appended startup invocation is required for filtering after boot.

The ADC application starts before Lisp, including the native ADC safe-start period. Therefore physical RX is in use until the filter has qualified its initial state. If qualification is blocked, raw RX remains active. A watchdog boot suppresses Lisp and uses the configured native input. Persistence does not create a guarantee that filtering is active from the first instant after power-up.

## Exact wire formats

All multibyte integers below are big-endian. The ordinary VESC packet framing and its independent CRC16 still wrap every payload.

| Command | Request payload | Success reply payload | Notes |
| --- | --- | --- | --- |
| READ_CODE 130 | `130, length:i32, offset:i32` | `130, total:i32, offset:i32, bytes[length]` | Offset excludes the eight-byte flash header. Limit read chunks to 256 bytes. No valid blob yields exactly nine bytes with total=0, offset=0. |
| ERASE_CODE 132 | `132, size:i32` | exactly `132, 1` | Tool sends size; this firmware ignores it and erases the entire 128 KiB Lisp sector. It resets Lisp first, without loading code. |
| WRITE_CODE 131 | `131, offset:u32, data[]` | exactly `131, 1, offset:u32` | Offset is relative to the beginning of the Lisp sector, including the header. Firmware does not validate the requested offset/range. Host must enforce its fixed image and sector bounds. |
| SET_RUNNING 133 | `133, running:u8` | exactly `133, ok:u8` | 1 resets/reinitializes the interpreter and loads stored code. 0 pauses all Lisp; it is not a button rollback. A successful reply is not proof that the script armed. |

The sector is index 10, base address 0x080C0000, size 131,072 bytes. The usable code/import blob is at most 131,064 bytes. The 512-byte packet payload ceiling permits at most 507 data bytes for WRITE131; 256-byte writes keep a conservative margin. Do not accept failure/extra/truncated ACKs or an offset different from the one just sent. Do not append after a partial frame or automatically retry a missing/uncertain write response.

### Stored image

```
flash offset 0: uint32 length of code/import blob, excluding flags/header
flash offset 4: uint16 CRC16 of (flags || code/import blob)
flash offset 6: uint16 flags = 0
flash offset 8: ASCII Lisp source, terminating NUL, uint16 import count = 0
```

This is the no-import format produced by official VESC Tool's `lispPackImports` and `lispUpload`. Source+NUL alone is also accepted by the firmware, but source+NUL+zero import count matches the upstream packer. The CRC is the same initial-zero CRC16 used by VESC packet framing (`binascii.crc_hqx(data, 0)`), calculated over the two flag bytes followed by the entire code/import blob. The code size includes the NUL and zero import count.

The reviewed autostart artifact generated independently by m5_review has:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `rx-filter-autostart.lisp` | 3,981 | `30981ff45663d254153009ec0f6258b400126afd74a66a6caa2a70c56ac96700` |
| Code/import blob | 3,984 | `a2461adda272a014506cc76f0bdbf2240c85dff39842c6dac8655b4e0be34801` |
| Header plus code/import blob | 3,992 | `428657a58bc6d4a2a0e85df858e36fc7d34972007d7df436ed236632a9a19495` |

Header hex: **00000f90af410000**, CRC16 **44865 / 0xAF41**. I independently verified that the first 3,732 source bytes are the previously tested compact candidate without modification. The additional expression checks UUID, firmware `(6 2 0)` and current app2/ctrl3 before calling the existing start function once. Full ADC button/hysteresis/servo/safe-start and calibration checks remain the host install/maintenance responsibility; the available Lisp configuration API does not expose all those fields. m5_review reports 14 pinned-VM startup fixtures passed; see its own artifacts for that independent validation.

## Maintenance sequence and reversibility

1. Keep competing BLE/USB clients disconnected. Freshly verify the exact UUID/firmware, all motor/app bytes, zero-command pedal/rest/fault-free state and stored-code baseline. Preserve current runtime and stored-code evidence. The known baseline is no valid stored blob; this is not a bit-for-bit erased-flash backup.
2. At rest with raw RX matching the currently held direction, join the filter worker and explicitly reattach native buttons through the reviewed rollback. Confirm completion before proceeding. Pausing Lisp, erasing code or restarting the interpreter does not itself restore native input; C-side detach/override state otherwise survives.
3. Send exactly one ERASE132. Its handler calls `lispif_restart(false,false)` before sector erase; this destroys old Lisp lifecycle tracking. Require the exact success ACK, then verify no valid stored blob. Do not send another erase after an uncertain result.
4. Write the fixed body at offset8 in bounded, sequential chunks, checking each exact success/offset ACK. The arbitrary-offset firmware API supports writing the header last. Until the header is complete, READ130 cannot verify the body because it only exposes CRC-valid images.
5. Commit the fixed header once after the body ACKs. A simple eight-byte header-last write reduces the valid-image window but is not a transactional flash operation. An optional stronger ordering for this sub-64KiB image is body, CRC/flags at offset4, low length bytes at offset2, then high length bytes `0000` at offset0 last: the length stays above the sector limit until the final byte. This ordering must be part of the independently reviewed fixed plan; do not improvise it live.
6. Read the complete stored code/import blob back with READ130, require exact size and byte-for-byte/hash equality, and repeat identity/motor/app checks. Keep all attempted frames, replies and partial/failure evidence. No automatic start follows an uncertain result.
7. A separately supervised SET_RUNNING133=1 can load the verified stored source now, but its ACK alone does not prove successful execution. Observe the correct live worker and applied direction with safe pedal/rest/fault state. Finally, an owner-controlled normal power cycle and fresh status/forward/reverse checks establish actual boot persistence; runtime restart alone is not that evidence.

**Flash operations affect live operation even though they do not change the tune.** Both erase and write temporarily ignore motor input, release motor output and wait for release, then temporarily adjust watchdog/interrupt handling. They must happen as at-rest maintenance. They target the Lisp sector, not the firmware image or configuration sectors, only because the host uses the correct fixed offsets.

To remove the persistent filter later, first join/rollback it safely, then perform a separately authorized single Lisp erase and verify no valid stored blob. A normal power cycle returns cold-boot native C-side input state. Stopping the worker alone leaves the last direction held; restarting the controller without erasing a valid autostart script runs that script again. If the runtime's state is unknown or rollback refuses, do not invent an input-reset command; resolve the state or use a controlled whole-controller power cycle under the owner’s supervision.

### Backup and readback limits

READ130 returns only CRC-valid code/import bytes, excluding size, stored CRC and flags. It cannot preserve the exact original header or independently read back flags. `no_valid_blob` conflates erased flash and invalid/corrupt contents. For this known no-valid-script baseline, erase restores the functional absence of autostart code, not the exact prior sector bits. For a future nonempty/unknown script, do not claim a full flash backup or silently replace it on the basis of source text alone; preserve imports and establish header/flag provenance before an exact restoration plan.

## Pinned primary sources

Firmware commit `f7c2b34e1cff2234cae98be3abf0cd50e249558f`:

- [commands.c](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/comm/commands.c): READ at1416; ERASE at1461; WRITE at1482; Lisp boot initialization at1985.
- [flash_helper.c](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/flash_helper.c): sector/layout constants; erase/write189–196; payload/flags199–230; motor-output side effects389–444; CRC/size validity447–465.
- [lispif.c](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/lispBM/lispif.c): watchdog boot exclusion; SET_RUNNING; restart/import parsing and execution.

VESC Tool6.02 commit `f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee`:

- [codeloader.cpp](https://github.com/vedderb/vesc_tool/blob/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee/codeloader.cpp): flags/pack96, zero-import count248, image/header308, five retries and ignored ACKoffset, 384-byte chunks.
- [commands.cpp](https://github.com/vedderb/vesc_tool/blob/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee/commands.cpp): wire methods2145–2187 and ACK decoding975–1011.
- [pagelisp.cpp](https://github.com/vedderb/vesc_tool/blob/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee/pages/pagelisp.cpp): Upload596–635 and immediate Auto Run behavior; no independent boot-autostart flag.

Fetched Tool source copies are retained under sources/ with upstream copyright notices. This audit contains no executable hardware writer.
