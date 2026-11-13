#include "PlayerPreview.h"
#include <cassert>
#include <cstdio>
#include <cstdint>
int main(){
  using P=m5dash::PlayerPreview;P p;
  assert(p.notify(0)&&!p.notify(500));
  p.open();assert(p.overlay&&!p.notify(1000));
  assert(p.tap(200,160,100));assert(p.stage==P::Stage::Downloading);
  p.tick(3099);assert(p.progress(3099)==99&&p.stage==P::Stage::Downloading);
  p.tick(3100);assert(p.stage==P::Stage::Ready&&!p.overlay);
  p.fire(4000);p.fire(4001);assert(p.fired==1&&p.stage==P::Stage::Used);
  p.scenario("ready",5000);p.open();p.fire(5100);assert(p.fired==0);
  p.tap(30,160,5200);p.gpsLost=true;p.fire(5300);assert(p.fired==0);
  p.gpsLost=false;p.linkLost=true;p.fire(5400);assert(p.fired==0);
  p.scenario("host-lost",6000);assert(!p.available());p.open();assert(!p.overlay);
  assert(!p.scenario("bad",6100));assert(p.stage==P::Stage::HostLost);
  p.scenario("download-error",6200);assert(p.overlay);p.tap(200,160,6300);assert(p.stage==P::Stage::Downloading);
  p.scenario("download",UINT32_MAX-1000);p.tick(1999);assert(p.stage==P::Stage::Ready);
  p.scenario("invite",7000);p.open();assert(p.tap(0,239,7010)&&p.overlay); // modal consumes touches outside controls
  puts("Preview states: freshness presentation, modal isolation, one-shot FIRE and timer wrap passed");
}
