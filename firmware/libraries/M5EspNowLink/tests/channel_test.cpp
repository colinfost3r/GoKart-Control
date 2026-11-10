#include "M5ChannelAlignment.h"
#include <cassert>
#include <cstring>
#include <iostream>
using namespace m5now;
int main() {
  ChannelRecord r{true,6,0x12345678,0xabcdef01},decoded;
  char line[CHANNEL_RECORD_SIZE+1];assert(encodeChannelRecord(r,line));
  assert(!std::strcmp(line,"G5CH1,06,12345678,abcdef01"));
  assert(decodeChannelRecord(line,decoded) && decoded.advertisement && decoded.grant==r.grant);
  for(const char* invalid:{"G5CH1,00,12345678,00000000","G5CH1,12,12345678,00000000",
       "G5CH1,06,00000000,00000000","G5CH1,06,1234567z,00000000",
       "G5CA1,06,12345678,00000001","G5CH1,06,12345678,00000000x","G5CH1,06"})
    assert(!decodeChannelRecord(invalid,decoded));

  ChannelAlignment display,heltec;display.begin(Role::Display,22,5);heltec.begin(Role::Heltec,11,9);
  display.driver(5,100);heltec.driver(6,101);display.peerBoot(11,102);heltec.peerBoot(22,103);
  ChannelRecord adv,ack;assert(heltec.record(100,adv));assert(!adv.grant);
  // Hearing the peer on adjacent5 discovers6 but does not authorize a command or ACK.
  assert(display.accept(adv,5,100,true));assert(display.retuneTarget(100)==6);
  assert(!display.aligned(100) && !display.record(100,ack));
  display.driver(6,104);assert(!display.record(101,ack));
  assert(!display.accept(adv,6,101,false));assert(!display.aligned(101));
  // Must hear another authenticated announcement after the actual retune.
  assert(display.accept(adv,6,110,true));assert(display.record(110,ack));
  assert(!display.aligned(110)); // Heltec has not yet acknowledged this display boot.
  assert(!heltec.accept(ack,5,111,true));assert(!heltec.aligned(111));
  auto wrong=ack;wrong.challenge^=1;assert(!heltec.accept(wrong,6,112,true));
  assert(heltec.accept(ack,6,113,true));assert(heltec.aligned(113));
  assert(heltec.record(114,adv) && adv.grant==22);
  assert(display.accept(adv,6,115,true) && display.aligned(115));
  assert(!display.aligned(115+LINK_MS));assert(!heltec.aligned(113+LINK_MS));

  // Maintenance destroys proof in both directions locally and never schedules a retune.
  display.enable(false);assert(!display.aligned(120) && !display.record(120,ack));
  assert(!display.accept(adv,6,120,true) && !display.retuneTarget(120));
  display.driver(1,105);display.enable(true);assert(!display.retuneTarget(121));
  assert(!display.accept(adv,6,121,false));assert(!display.aligned(121));
  assert(display.accept(adv,1,122,true) && display.retuneTarget(122)==6);

  // Peer replacement and sender channel changes cannot inherit the old grant/challenge.
  display.driver(6,106);display.peerBoot(33,107);assert(!display.aligned(130));
  auto oldAck=ack;assert(heltec.record(130,adv));const auto priorChallenge=adv.challenge;
  heltec.peerBoot(44,108);assert(heltec.record(131,adv));assert(adv.challenge!=priorChallenge && !adv.grant);
  assert(!heltec.accept(oldAck,6,132,true));
  heltec.driver(11,109);assert(heltec.record(133,adv) && adv.channel==11 && !adv.grant);
  assert(!heltec.accept(oldAck,11,134,true));
  heltec.driver(0,110);assert(!heltec.record(135,adv) && !heltec.aligned(135));

  // Proof age is preserved receive time and remains bounded across millis wrap.
  ChannelAlignment wrap;wrap.begin(Role::Display,22,1);wrap.driver(6,2);wrap.peerBoot(11,3);
  assert(wrap.accept({true,6,55,22},6,0xfffffff0u,true));
  assert(wrap.aligned(0x20u));assert(!wrap.aligned(0x800u));
  std::cout<<"Channel alignment: adjacent reception, retune proof, challenge/grant, maintenance, boot, age and bounds passed\n";
}
