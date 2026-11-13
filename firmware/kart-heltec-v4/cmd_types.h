// cmd_types.h — command bookkeeping types for the kart sketch. In a header (not the .ino) because
// the Arduino builder inserts function prototypes near the top of the sketch, ahead of any type
// declared there.
#pragma once
#include <stdint.h>

// One remembered command (per source: pit over LoRa, or USB/local).
struct CmdEnt { uint8_t seq, cmd, arg, result; uint32_t issued, ms; bool used; };
// Stable reference to a history entry; resolves to nothing once the slot has been reused.
struct CmdRef { int8_t src, idx; uint8_t seq; uint32_t ms; };
// What a running boost looks like on the controller, kept in RTC memory so a Heltec that restarts
// mid-boost can recognise its own leftover (see serviceMissedRevert in the sketch).
struct BoostMark { uint32_t magic; char uuid[25]; uint8_t baseMode; float scale, capErpm; uint32_t check; };
