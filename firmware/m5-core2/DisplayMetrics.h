#pragma once
#include "DisplayState.h"

namespace m5dash {
// Match kart/server/kartcore.py battery_percent: the current fleet's linear
// 20S voltage estimate, 60 V empty / 84 V full. Not measured BMS state of charge;
// voltage sag under load lowers the estimate. Missing/stale input stays unknown.
inline float batteryPercent(const State& state,uint32_t now) {
  const auto& k=state.karts[state.self];
  if(!state.live(now)||!k.vesc||!std::isfinite(k.volts)||k.volts<=0)return NAN;
  return std::max(0.0f,std::min(100.0f,(k.volts-60.0f)/24.0f*100.0f));
}
inline float gpsMph(const State& state,uint32_t now) {
  const auto& k=state.karts[state.self];
  if(!state.live(now)||!k.positionFresh(now)||!std::isfinite(k.gpsKph)||k.gpsKph<0||k.gpsKph>=160)return NAN;
  return k.gpsKph*0.621371f;
}
}
