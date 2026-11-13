#include "DisplayMetrics.h"
#include <cassert>
#include <cstdio>
using namespace m5dash;
int main(){
 State s;assert(std::isnan(packVolts(s,100)));assert(std::isnan(gpsMph(s,100)));
 s.self=3;auto& k=s.karts[3];k.seen=k.vesc=k.fix=k.hasPosition=true;k.received=k.fixReceived=100;
 const float volts[]={50,60,72,78.4,84,90},want[]={50,60,72,78.4f,84,90};
 for(unsigned i=0;i<6;++i){k.volts=volts[i];assert(std::fabs(packVolts(s,101)-want[i])<.001f);}
 k.gpsKph=22;assert(std::fabs(gpsMph(s,101)-13.670162f)<.001f);
 k.vesc=false;assert(std::isnan(packVolts(s,101)));assert(std::isfinite(gpsMph(s,101)));
 k.vesc=true;k.volts=NAN;assert(std::isnan(packVolts(s,101)));k.volts=79.4;
 k.fix=false;assert(std::isnan(gpsMph(s,101)));assert(std::isfinite(packVolts(s,101)));k.fix=true;
 for(float invalid:{-1.0f,160.0f,NAN}){k.gpsKph=invalid;assert(std::isnan(gpsMph(s,101)));}
 k.gpsKph=22;assert(std::isnan(packVolts(s,1700)));assert(std::isnan(gpsMph(s,1700)));
 k.received=0xfffffff0U;k.fixReceived=0xfffffff0U;assert(std::isfinite(packVolts(s,20)));assert(std::isfinite(gpsMph(s,20)));
 puts("Heltec pack voltage, speed units and unavailable/stale telemetry passed");
}
