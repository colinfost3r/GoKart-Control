#pragma once
#include "DisplayState.h"

namespace m5dash {
// Measured VESC pack voltage relayed by Heltec. No local SOC estimate and no
// Core2/Heltec accessory-battery substitution. Missing or stale input is unknown.
inline float packVolts(const State& state,uint32_t now) {
  const auto& k=state.karts[state.self];
  return state.live(now)&&k.vesc&&std::isfinite(k.volts)&&k.volts>0?k.volts:NAN;
}
inline float gpsMph(const State& state,uint32_t now) {
  const auto& k=state.karts[state.self];
  if(!state.live(now)||!k.positionFresh(now)||!std::isfinite(k.gpsKph)||k.gpsKph<0||k.gpsKph>=160)return NAN;
  return k.gpsKph*0.621371f;
}
}
