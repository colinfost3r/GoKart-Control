// Pit race on the Core2: what the display takes from the Heltec's lines and when it shows it.
// Host test; no device or radio. The Core2 never commands anything here.
#include "DisplayState.h"
#include <cassert>
#include <cstdio>
#include <string>
using namespace m5dash;

static std::string display(const char* race,unsigned boot=7){
  char b[420];std::snprintf(b,sizeof b,
    "{\"t\":\"display\",\"v\":1,\"kart\":3,\"boot\":%u,\"token\":5,\"mode_ready\":false,\"radio\":true,\"pit\":true,"
    "\"modes\":[{\"mph\":15,\"scale\":0.5},{\"mph\":25,\"scale\":0.75},{\"mph\":0,\"scale\":1}]%s}",boot,race);
  return b;
}
static std::string self(const char* extra){
  char b[300];std::snprintf(b,sizeof b,"{\"t\":\"self\",\"kart\":3,\"vesc_link\":true,\"stopped\":false%s}",extra);return b;
}
static void feed(State& s,const std::string& line,uint32_t now){assert(s.ingest(line.c_str(),now));}

int main(){
  // Lines from firmware without the race fields: nothing is shown.
  State old;feed(old,display(""),1000);feed(old,self(""),1000);
  assert(old.raceCountdown(1100)==-1&&!old.raceGo(1100)&&!old.raceShown(1100));

  // Grid hold: whole seconds, rounded up, counted locally between lines and never below zero.
  State s;feed(s,self(""),1000);feed(s,display(",\"race_hold\":true,\"race_go_ms\":3400,\"race_went_ms\":0"),1000);
  assert(s.raceHold&&s.raceCountdown(1000)==4&&s.raceCountdown(1399)==4&&s.raceCountdown(1401)==3);
  feed(s,self(""),2400);feed(s,display(",\"race_hold\":true,\"race_go_ms\":1500,\"race_went_ms\":0"),2900);
  assert(s.raceCountdown(2901)==2&&s.raceCountdown(3400)==1);
  feed(s,self(""),3900);feed(s,display(",\"race_hold\":true,\"race_go_ms\":500,\"race_went_ms\":0"),3900);
  assert(s.raceCountdown(4399)==1&&s.raceCountdown(4400)==0&&s.raceCountdown(4500)==0);   // held until the Heltec says otherwise
  assert(!s.raceGo(4500));                                                               // never GO on the display's own clock
  // A later line re-anchors the deadline; an absurd time is capped at the firmware's own maximum.
  feed(s,display(",\"race_hold\":true,\"race_go_ms\":900,\"race_went_ms\":0"),4500);assert(s.raceCountdown(4500)==1);
  feed(s,display(",\"race_hold\":true,\"race_go_ms\":4000000000,\"race_went_ms\":0"),4600);assert(s.raceCountdown(4600)==31);

  // GO: only when the Heltec reports a release, for three seconds from its own time of release.
  feed(s,self(""),5400);feed(s,display(",\"race_hold\":false,\"race_go_ms\":0,\"race_went_ms\":120"),5400);
  assert(s.raceCountdown(5400)==-1&&s.raceGo(5400)&&s.raceGo(6000));
  feed(s,self(""),6400);feed(s,self(""),7400);feed(s,display(",\"race_hold\":false,\"race_go_ms\":0,\"race_went_ms\":2100"),7400);
  assert(s.raceGo(7400)&&s.raceGo(8200)&&!s.raceGo(8300));
  feed(s,display(",\"race_hold\":false,\"race_go_ms\":0,\"race_went_ms\":0"),8300);assert(!s.raceGo(8300));
  feed(s,display(",\"race_hold\":false,\"race_go_ms\":0,\"race_went_ms\":9999"),8350);assert(!s.raceGo(8350));   // out of range: ignored
  // A hold that ends without a release (abort, pit START) shows neither countdown nor GO.
  State aborted;feed(aborted,self(""),1000);feed(aborted,display(",\"race_hold\":true,\"race_go_ms\":5000,\"race_went_ms\":0"),1000);
  feed(aborted,display(",\"race_hold\":false,\"race_go_ms\":0,\"race_went_ms\":0"),1500);
  assert(aborted.raceCountdown(1500)==-1&&!aborted.raceGo(1500)&&!aborted.raceGo(6100));

  // Never over a pit STOP, which GO does not release.
  State stopped;feed(stopped,display(",\"race_hold\":true,\"race_go_ms\":3000,\"race_went_ms\":0"),1000);
  feed(stopped,"{\"t\":\"self\",\"kart\":3,\"vesc_link\":true,\"stopped\":true}",1000);
  assert(stopped.raceCountdown(1100)==-1&&!stopped.raceGo(1100));
  feed(stopped,self(""),1200);assert(stopped.raceCountdown(1200)==3);

  // Stale input hides it: no own telemetry for 1.5 s, or no display line for 2 s.
  State stale;feed(stale,self(""),1000);feed(stale,display(",\"race_hold\":true,\"race_go_ms\":9000,\"race_went_ms\":0"),1000);
  assert(stale.raceCountdown(2500)==8&&stale.raceCountdown(2501)==-1);             // own telemetry too old
  feed(stale,self(""),2900);assert(stale.raceCountdown(3000)==7&&stale.raceCountdown(3001)==-1);   // display line too old
  // Before any display line the board does not know its kart: nothing.
  State blank;assert(blank.raceCountdown(10)==-1&&!blank.raceGo(10)&&!blank.raceShown(10));

  // Running and finished come from the pit beacon via the own telemetry line.
  State r;feed(r,display(""),1000);feed(r,self(",\"race_pos\":2,\"race_state\":2"),1000);
  assert(r.raceShown(1100)==2&&r.racePos==2);
  feed(r,self(",\"race_pos\":1,\"race_state\":3"),1500);assert(r.raceShown(1600)==3&&r.racePos==1);
  feed(r,self(",\"race_pos\":0,\"race_state\":1"),2000);assert(!r.raceShown(2100));          // countdown alone shows no chip
  feed(r,self(",\"race_pos\":9,\"race_state\":7"),2500);assert(!r.raceShown(2600)&&r.racePos==0);  // out of range
  feed(r,self(",\"race_pos\":3,\"race_state\":2"),3000);assert(r.raceShown(4500)==2&&!r.raceShown(4501));   // stale telemetry
  // Another kart's line never sets this kart's race.
  State other;feed(other,display(""),1000);feed(other,self(""),1000);
  assert(other.ingest("{\"t\":\"fleet\",\"kart\":4,\"race_pos\":1,\"race_state\":2}",1100)&&!other.raceShown(1200));
  // A Heltec restart: nothing from the old boot is shown, before or after its first telemetry line.
  State reboot;feed(reboot,self(",\"race_pos\":2,\"race_state\":2"),1000);
  feed(reboot,display(",\"race_hold\":true,\"race_go_ms\":5000,\"race_went_ms\":0"),1000);
  assert(reboot.raceCountdown(1100)==5&&reboot.raceShown(1100)==2);
  feed(reboot,display("",8),1200);
  assert(reboot.raceCountdown(1200)==-1&&!reboot.raceGo(1200)&&!reboot.raceShown(1200));
  feed(reboot,self(""),1300);
  assert(reboot.raceCountdown(1300)==-1&&!reboot.raceShown(1300)&&!reboot.raceHold);
  std::printf("race view passed\n");
}
