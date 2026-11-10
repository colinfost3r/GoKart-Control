#include "M5EspNowLink.h"
#include <cassert>
#include <string>
#include <iostream>
using namespace m5now;
struct Fixture {
  Link link;Role role;uint32_t ownBoot,id=1;uint8_t key[16]{1},pmk[16]{2},auth[32]{};
  explicit Fixture(Role r):role(r) {
    fake::reset();ownBoot=fake::random+1;assert(link.begin(r,fake::peer,key,pmk));
    const uint8_t label[]="GoKart M5 ESP-NOW frame auth v1";
    mbedtls_md_hmac(nullptr,key,16,label,sizeof(label)-1,auth);
  }
  ~Fixture(){link.end();}
  void poll(uint32_t now){fake::now=now;link.poll(now);}
  void settle(){
    for(unsigned i=0;i<32;++i){
      if(fake::pending)fake::complete();link.poll(fake::now);
      if(!fake::pending){link.poll(fake::now);if(!fake::pending)return;}
    }
    assert(false && "transmit queue did not settle");
  }
  void inject(const std::string& text,uint8_t rx,uint32_t boot=77,bool validTag=true) {
    uint8_t p[PACKET_MAX],digest[32];const auto sender=role==Role::Display?Role::Heltec:Role::Display;
    size_t n=encode(p,sender,Kind::Line,boot,id++,text.c_str(),text.size(),0);assert(n);
    mbedtls_md_hmac(nullptr,auth,32,p,n,digest);std::memcpy(p+n,digest,TAG_SIZE);if(!validTag)p[n]^=1;
    wifi_pkt_rx_ctrl_t ctrl{-40,rx};esp_now_recv_info_t info{fake::peer,fake::own,&ctrl};
    fake::receive(&info,p,int(n+TAG_SIZE));
  }
  void record(bool advert,uint8_t channel,uint32_t challenge,uint32_t grant,uint8_t rx,uint32_t boot=77,bool validTag=true){
    char p[CHANNEL_RECORD_SIZE+1];assert(encodeChannelRecord({advert,channel,challenge,grant},p));inject(p,rx,boot,validTag);
  }
  ChannelRecord lastControl(){
    for(auto i=fake::sentPackets.rbegin();i!=fake::sentPackets.rend();++i) {
      const auto& p=*i;if(p[18]!=uint8_t(Kind::Line))continue;
      std::string text(reinterpret_cast<const char*>(p.data()+HEADER_SIZE),get16(p.data()+12));
      ChannelRecord r;if(decodeChannelRecord(text.c_str(),r))return r;
    }
    assert(false && "no private channel frame sent");return {};
  }
  void alignDisplay(){
    fake::channel=6;poll(100);record(true,6,50,0,6);poll(110);assert(!link.canSend(110));
    poll(600);settle();auto ack=lastControl();assert(!ack.advertisement && ack.challenge==50);
    record(true,6,50,ownBoot,6);poll(610);settle();assert(link.canSend(610));
  }
  uint32_t alignHeltec(){
    inject("legacy request",6);poll(110);assert(!link.readLine(110));
    poll(600);settle();auto adv=lastControl();assert(adv.advertisement && !adv.grant);
    record(false,6,adv.challenge,0,6);poll(610);assert(link.channelAligned(610));return adv.challenge;
  }
};
int main(){
  {
    Fixture f(Role::Display);fake::channel=5;f.poll(100);
    f.record(true,6,50,0,5);f.poll(110);
    assert(fake::channel==6 && f.link.channel()==6 && f.link.receivedChannel()==5);
    assert(!f.link.canSend(110));assert(!f.link.sendLine("M1 request",110));
    // Queued callback from BEFORE retune cannot establish proof, even if metadata claims6.
    f.record(true,6,50,f.ownBoot,6);f.link.setChannelSearchEnabled(false);f.link.setChannelSearchEnabled(true);f.poll(120);
    assert(!f.link.channelAligned(120));
    f.record(true,6,50,0,6);f.poll(130);f.poll(600);f.settle();
    f.record(true,6,50,f.ownBoot,6);f.poll(610);f.settle();assert(f.link.canSend(610));
    assert(f.link.sendLine("M1 explicit request",610));assert(fake::pending);
    // A fresh peer channel change must wait until the outstanding send callback completes.
    f.record(true,11,60,0,6);f.poll(620);assert(fake::channel==6 && !f.link.canSend(620));
    f.settle();f.poll(621);assert(fake::channel==11 && !f.link.canSend(621));
  }
  {
    Fixture f(Role::Display);f.alignDisplay();
    f.link.setChannelSearchEnabled(false);const int calls=fake::setCalls;
    f.record(true,11,60,0,6);f.poll(620);assert(fake::setCalls==calls && !f.link.canSend(620));
    fake::channel=1;f.poll(630);assert(fake::setCalls==calls); // AP owns radio during maintenance
    f.link.setChannelSearchEnabled(true);f.poll(640);assert(!f.link.canSend(640));
    f.record(true,6,50,0,1);fake::scan=WIFI_SCAN_RUNNING;f.poll(650);assert(fake::channel==1);
    fake::scan=0;fake::connected=WL_CONNECTED;f.poll(660);assert(fake::channel==1);
    fake::connected=0;f.poll(670);assert(fake::channel==6 && !f.link.canSend(670));
  }
  {
    Fixture f(Role::Display);fake::channel=5;f.poll(100);
    f.record(true,6,50,f.ownBoot,5,77,false);f.poll(110);assert(fake::channel==5 && !f.link.canSend(110));
    assert(f.link.stats().rxInvalid==1);
    // Legacy peer still supplies telemetry, but cannot unlock controls without handshake.
    f.inject("{\"t\":\"self\",\"kart\":3}",5);f.poll(120);
    assert(f.link.readLine(120) && f.link.connected(120) && !f.link.canSend(120));
  }
  {
    Fixture f(Role::Heltec);const auto challenge=f.alignHeltec();
    f.inject("M1 explicit request",6);f.poll(620);assert(f.link.readLine(620));
    // AP change after poll but before dispatch must discard the completed command.
    f.inject("M1 stale request",6);f.poll(630);fake::channel=11;assert(!f.link.readLine(630));
    assert(!f.link.channelAligned(630));
    f.record(false,11,challenge,0,11);f.poll(640);assert(!f.link.channelAligned(640));
    // Old advertisement cannot be released after channel invalidation.
    f.poll(1200);f.settle();auto updated=f.lastControl();assert(updated.channel==11 && updated.challenge!=challenge && !updated.grant);
  }
  {
    Fixture f(Role::Heltec);f.alignHeltec();
    f.inject("M1 old boot",6);f.poll(620);
    f.inject("M1 new boot",6,88);f.poll(630);
    assert(!f.link.readLine(630) && !f.link.channelAligned(630));
  }
  std::cout<<"ESP-NOW runtime: real adapter auth ordering, adjacent retune, TX/OTA/scan guards, mixed versions, AP/boot invalidation passed\n";
}
