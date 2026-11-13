# VESC Tool schema provenance

These two XML schemas are unmodified upstream VESC Tool configuration definitions
for firmware 6.00. They are used for offline decoding, not as device settings.

- Repository: https://github.com/vedderb/vesc_tool
- Pinned commit: `85fc40852541a0cc1f8b6339ff98b1f65a48ed93`
- Paths: `res/config/6.00/parameters_mcconf.xml` and `parameters_appconf.xml`.
- Motor-schema Git blob: `6ef7031cfef259f2f00ddb55a3019ca7e99a1329`.
- App-schema Git blob: `aad35c6d3d1a63f662a984f75a2fd1bf99aae4d4`.
- Both downloaded files' Git blob hashes were verified against upstream metadata.
- License: GPL-3.0-or-later; upstream LICENSE is retained in this directory.
- Upstream author/copyright attribution: Benjamin Vedder and VESC Tool contributors.

Do not confuse XML schema default values with settings read from the kart.
Captured values live under hardware/vesc; the decoder uses SerOrder, transport
types, scales and enum names, and verifies the firmware's schema signature.

Protocol/serialization references inspected: upstream configparams.cpp,
vbytearray.cpp, datatypes.h and commands.cpp; bldc comm/packet.c and comm/commands.c.
The local Python tools provide a limited inspection implementation, not a full
VESC Tool replacement. No upstream firmware or original dashboard source is vendored.


## Verified 6.02 wire compatibility (2026-11-10)

The read-only decoder deliberately reuses the existing 6.00 files for 6.02. Both
configuration replies must still pass their signatures and exact length checks.
No controller settings are supplied by these schemas.

- Official VESC Tool `release_6_02` commit:
  [`f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee`](https://github.com/vedderb/vesc_tool/tree/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee).
- Compared [motor XML](https://github.com/vedderb/vesc_tool/blob/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee/res/config/6.02/parameters_mcconf.xml)
  and [app XML](https://github.com/vedderb/vesc_tool/blob/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee/res/config/6.02/parameters_appconf.xml)
  with all 376 serialized fields in the pinned 6.00 schemas. Serialization order,
  type, transport, double scale and enum/bit names are identical. Motor XML is
  byte-identical; app XML differs only in descriptions.
- Motor signature: `2e43a161` (189 fields). App signature: `1d003a2c` (187 fields).
- Official firmware `release_6_02` commit:
  [`f7c2b34e1cff2234cae98be3abf0cd50e249558f`](https://github.com/vedderb/bldc/tree/f7c2b34e1cff2234cae98be3abf0cd50e249558f).
  Its [commands.c](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/comm/commands.c)
  confirms the identity and 74-byte full `COMM_GET_VALUES` layouts.
  [confgenerator.h](https://github.com/vedderb/bldc/blob/f7c2b34e1cff2234cae98be3abf0cd50e249558f/confgenerator.h)
  independently confirms both signature constants; `confgenerator.c` serializes
  the corresponding motor/application structures.
- Bitfield interpretation was checked against VESC Tool's
  [parameditbitfield.cpp](https://github.com/vedderb/vesc_tool/blob/f3c6fe5f5dcf0cb2fba7676204ea3db1dc8ff4ee/widgets/parameditbitfield.cpp):
  label index N means bit `1 << N`, not enum value N. Zero has no enabled options.

[Machine-readable evidence](compatibility-6.02.json) records source hashes, blob
identities and normalized full serialization-layout fingerprints. Offline tests
check the reused schemas against this record. This is protocol compatibility,
not a claim that different hardware can safely share every motor/app value.
