#pragma once
#include "M5EspNowFrame.h"

namespace m5now {
// Reserved v1 Line payloads keep old telemetry framing compatible. The transport
// consumes these only AFTER HMAC and assembler replay/age validation.
// G5CH1,06,12345678,12345678 = channel, challenge, acknowledged display boot.
// G5CA1,06,12345678,00000000 = channel, echoed challenge, reserved zero.
struct ChannelRecord { bool advertisement=false; uint8_t channel=0; uint32_t challenge=0, grant=0; };
constexpr size_t CHANNEL_RECORD_SIZE=26;
inline bool validChannel(uint8_t c) { return c>=1 && c<=11; }
inline bool channelRecordPrefix(const char* p) { return p && !std::strncmp(p,"G5C",3); }
inline bool decodeChannelRecord(const char* p,ChannelRecord& out) {
  if(!p || std::strlen(p)!=CHANNEL_RECORD_SIZE || std::strncmp(p,"G5C",3) ||
     (p[3]!='H' && p[3]!='A') || p[4]!='1' || p[5]!=',' || p[8]!=',' || p[17]!=',' ||
     p[6]<'0' || p[6]>'9' || p[7]<'0' || p[7]>'9') return false;
  ChannelRecord v;v.advertisement=p[3]=='H';v.channel=uint8_t((p[6]-'0')*10+p[7]-'0');
  uint32_t* values[]={&v.challenge,&v.grant};
  for(unsigned n=0;n<2;++n) for(unsigned i=0;i<8;++i) {
    char c=p[(n?18:9)+i];unsigned digit;
    if(c>='0' && c<='9')digit=unsigned(c-'0');
    else if(c>='a' && c<='f')digit=unsigned(c-'a'+10);else return false;
    *values[n]=(*values[n]<<4)|digit;
  }
  if(!validChannel(v.channel) || !v.challenge || (!v.advertisement && v.grant))return false;
  out=v;return true;
}
inline bool encodeChannelRecord(const ChannelRecord& v,char out[CHANNEL_RECORD_SIZE+1]) {
  if(!out || !validChannel(v.channel) || !v.challenge || (!v.advertisement && v.grant))return false;
  std::memcpy(out,v.advertisement?"G5CH1,00,00000000,00000000":"G5CA1,00,00000000,00000000",CHANNEL_RECORD_SIZE+1);
  out[6]=char('0'+v.channel/10);out[7]=char('0'+v.channel%10);
  constexpr char hex[]="0123456789abcdef";
  const uint32_t values[]={v.challenge,v.grant};
  for(unsigned n=0;n<2;++n)for(unsigned i=0;i<8;++i)out[(n?18:9)+i]=hex[(values[n]>>(28-i*4))&15];
  return true;
}

class ChannelAlignment {
  Role role_=Role::Display;
  uint32_t ownBoot_=0,peerBoot_=0,challenge_=0,advertMs_=0,proofMs_=0;
  uint8_t driver_=0,peerChannel_=0;
  bool enabled_=true,haveAdvert_=false,haveProof_=false;
  void rotate(uint32_t nonce) {
    if(!nonce || nonce==challenge_)nonce=challenge_+1;
    challenge_=nonce?nonce:1;
  }
public:
  void begin(Role role,uint32_t ownBoot,uint32_t nonce) {
    *this=ChannelAlignment();role_=role;ownBoot_=ownBoot;rotate(nonce);
  }
  void driver(uint8_t value,uint32_t nonce) {
    if(value==driver_)return;
    driver_=value;invalidate();if(role_==Role::Heltec)rotate(nonce);
  }
  bool peerBoot(uint32_t value,uint32_t nonce) {
    if(value==peerBoot_)return false;
    peerBoot_=value;invalidate();if(role_==Role::Heltec)rotate(nonce);
    return true;
  }
  void enable(bool enabled) { if(enabled_!=enabled){enabled_=enabled;invalidate();} }
  void invalidate() { haveAdvert_=haveProof_=false;peerChannel_=0; }
  uint8_t peerChannel() const { return peerChannel_; }
  bool aligned(uint32_t now) const {
    return enabled_ && validChannel(driver_) && haveProof_ &&
      uint32_t(now-proofMs_)<LINK_MS && peerChannel_==driver_ &&
      (role_==Role::Heltec || (haveAdvert_ && uint32_t(now-advertMs_)<LINK_MS));
  }
  // eligible means the callback belongs to the current local radio/maintenance epoch.
  bool accept(const ChannelRecord& record,uint8_t rxChannel,uint32_t arrived,bool eligible) {
    if(!enabled_ || !eligible || !peerBoot_ || !validChannel(driver_) ||
       record.advertisement!=(role_==Role::Display))return false;
    if(role_==Role::Display) {
      if(!record.challenge || !validChannel(record.channel))return false;
      if(challenge_!=record.challenge)haveProof_=false;
      challenge_=record.challenge;peerChannel_=record.channel;advertMs_=arrived;haveAdvert_=true;
      haveProof_=rxChannel==driver_ && driver_==record.channel && record.grant==ownBoot_;
      if(haveProof_)proofMs_=arrived;
      return true;
    }
    if(record.challenge!=challenge_ || record.channel!=driver_ || rxChannel!=driver_ || record.grant)return false;
    peerChannel_=record.channel;proofMs_=arrived;haveProof_=true;return true;
  }
  uint8_t retuneTarget(uint32_t now) const {
    return role_==Role::Display && enabled_ && haveAdvert_ &&
      uint32_t(now-advertMs_)<LINK_MS && peerChannel_!=driver_ ? peerChannel_ : 0;
  }
  bool record(uint32_t now,ChannelRecord& out) const {
    if(!enabled_ || !validChannel(driver_))return false;
    if(role_==Role::Heltec) { out={true,driver_,challenge_,aligned(now)?peerBoot_:0};return true; }
    if(!haveAdvert_ || uint32_t(now-advertMs_)>=LINK_MS || peerChannel_!=driver_)return false;
    out={false,driver_,challenge_,0};return true;
  }
};
} // namespace m5now
