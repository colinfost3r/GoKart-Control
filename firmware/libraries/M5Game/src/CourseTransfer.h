#pragma once
#include "GamePackage.h"
#include <M5DisplayLink.h>
#include <algorithm>
namespace m5game { namespace share {
constexpr size_t CHUNK=192,HEADER_BYTES=30,TAG_BYTES=16,MAX_FRAME=HEADER_BYTES+CHUNK+TAG_BYTES;
enum class Kind:uint8_t{Offer=1,Hello=2,Manifest=3,Get=4,Data=5,Unavailable=6};
struct Message{Kind kind=Kind::Unavailable;uint8_t host=0;uint32_t boot=0,nonceA=0,nonceB=0,digest=0;uint16_t size=0,offset=0,count=0;std::array<uint8_t,CHUNK> bytes{};};
inline bool valid(const Message&m){
 if(m.host<1||m.host>8||unsigned(m.kind)<1||unsigned(m.kind)>6||m.count>CHUNK)return false;
 if(m.kind!=Kind::Data&&m.count)return false;
 if(m.kind==Kind::Hello)return (m.nonceA||m.nonceB)&&!m.boot&&!m.digest&&!m.size&&!m.offset;
 if(m.kind==Kind::Unavailable)return !m.count&&!m.offset;
 if(!m.boot||!m.size||m.size>MAX_PACKAGE)return false;
 if(m.kind==Kind::Offer)return !m.nonceA&&!m.nonceB&&!m.offset;
 if(!(m.nonceA||m.nonceB))return false;
 if(m.kind==Kind::Manifest)return !m.offset;
 if(m.offset>=m.size)return false;
 return m.kind!=Kind::Data||(m.count&&size_t(m.offset)+m.count<=m.size);
}
inline size_t encode(const Message&m,uint8_t*out){if(!valid(m))return 0;
 std::memcpy(out,"GCS1",4);out[4]=uint8_t(m.kind);out[5]=m.host;out[6]=out[7]=0;
 put32(out+8,m.boot);put32(out+12,m.nonceA);put32(out+16,m.nonceB);put32(out+20,m.digest);put16(out+24,m.size);put16(out+26,m.offset);put16(out+28,m.count);
 if(m.count)std::memcpy(out+HEADER_BYTES,m.bytes.data(),m.count);return HEADER_BYTES+m.count;
}
inline bool decode(const uint8_t*p,size_t n,Message&m){if(!p||n<HEADER_BYTES||n>HEADER_BYTES+CHUNK||std::memcmp(p,"GCS1",4)||p[6]||p[7])return false;
 Message next;next.kind=Kind(p[4]);next.host=p[5];next.boot=u32(p+8);next.nonceA=u32(p+12);next.nonceB=u32(p+16);next.digest=u32(p+20);next.size=u16(p+24);next.offset=u16(p+26);next.count=u16(p+28);
 if(n!=HEADER_BYTES+next.count||!valid(next))return false;if(next.count)std::memcpy(next.bytes.data(),p+HEADER_BYTES,next.count);m=next;return true;
}
class Publisher {
 Package active_;std::array<uint8_t,MAX_PACKAGE> staged_{};size_t expected_=0,received_=0;uint32_t digest_=0,started_=0;bool uploading_=false;
 public:
 const char* error="";
 const Package& package()const{return active_;}size_t received()const{return received_;}uint32_t digest()const{return digest_;}
 bool begin(size_t size,uint32_t crc,uint32_t now){uploading_=false;received_=0;expected_=0;error="size";if(size<116||size>MAX_PACKAGE)return false;expected_=size;digest_=crc;started_=now;uploading_=true;error="";return true;}
 bool chunk(size_t offset,const char* hex,uint32_t now){
  if(!uploading_||uint32_t(now-started_)>=60000){error="expired";uploading_=false;return false;}
  size_t chars=std::strlen(hex);if(offset!=received_||!chars||chars%2||chars>128||received_+chars/2>expected_){error="chunk";uploading_=false;return false;}
  uint8_t tmp[64];for(size_t i=0;i<chars/2;++i){uint32_t v;if(!m5link::hex(hex+i*2,2,v)){error="hex";uploading_=false;return false;}tmp[i]=v;}
  std::memcpy(staged_.data()+received_,tmp,chars/2);received_+=chars/2;error="";return true;
 }
 bool commit(uint8_t host,uint32_t now){
  bool ok=uploading_&&uint32_t(now-started_)<60000&&received_==expected_&&expected_>=4&&u32(staged_.data()+expected_-4)==digest_&&staged_[4]==host;
  uploading_=false;if(!ok||!active_.load(staged_.data(),expected_)){error="invalid_package";return false;}error="";return true;
 }
 void clear(){uploading_=false;active_.clear();}
 bool offer(uint8_t host,uint32_t boot,bool hosting,Message&out)const{
  if(!hosting||!boot||!active_.valid()||active_.host()!=host)return false;
  out=Message{};out.kind=Kind::Offer;out.host=host;out.boot=boot;out.digest=active_.digest();out.size=active_.size();return true;
 }
 bool answer(const Message&in,uint8_t host,uint32_t boot,bool hosting,Message&out)const{
  if(in.host!=host||(in.kind!=Kind::Hello&&in.kind!=Kind::Get))return false;
  if(!offer(host,boot,hosting,out)){out=Message{};out.kind=Kind::Unavailable;out.host=host;out.nonceA=in.nonceA;out.nonceB=in.nonceB;return true;}
  out.nonceA=in.nonceA;out.nonceB=in.nonceB;
  if(in.kind==Kind::Hello){out.kind=Kind::Manifest;return true;}
  if(in.boot!=boot||in.digest!=out.digest||in.size!=out.size||in.offset>=out.size)return false;
  out.kind=Kind::Data;out.offset=in.offset;out.count=uint16_t(std::min(size_t(CHUNK),active_.size()-in.offset));std::memcpy(out.bytes.data(),active_.data()+in.offset,out.count);return true;
 }
};
class Receiver {
 std::array<uint8_t,MAX_PACKAGE> staging_{};Message offer_{},expected_{};size_t received_=0;uint32_t offerMs_=0,started_=0,sentMs_=0;uint8_t tries_=0;bool haveOffer_=false,waiting_=false;
 public:
 enum class Stage{Idle,Hello,Data,Complete,Error};Stage stage=Stage::Idle;const char* error="";
 bool available(uint32_t now)const{return haveOffer_&&uint32_t(now-offerMs_)<5000;}
 uint32_t boot()const{return expected_.boot;}
 uint8_t host()const{return offer_.host;}uint32_t digest()const{return offer_.digest;}
 unsigned progress()const{return expected_.size?unsigned(received_*100/expected_.size):0;}
 bool busy()const{return stage==Stage::Hello||stage==Stage::Data;}
 void cancel(const char* why){stage=Stage::Error;waiting_=false;error=why;}
 bool begin(uint32_t a,uint32_t b,uint32_t now){if(!available(now)||(!a&&!b)||busy())return false;
  expected_=Message{};expected_.host=offer_.host;expected_.nonceA=a;expected_.nonceB=b;received_=0;started_=now;tries_=0;waiting_=false;stage=Stage::Hello;error="";return true;}
 bool next(uint32_t now,Message&out){
  if(!busy())return false;if(uint32_t(now-started_)>=30000){cancel("download timeout");return false;}
  if(waiting_&&uint32_t(now-sentMs_)<500)return false;
  if(tries_>=4){cancel("host not responding");return false;}
  out=expected_;out.kind=stage==Stage::Hello?Kind::Hello:Kind::Get;out.offset=received_;out.count=0;
  waiting_=true;sentMs_=now;++tries_;return true;
 }
 bool receive(const Message&m,uint32_t now){
  if(m.kind==Kind::Offer){if((busy()&&m.host!=expected_.host)||(available(now)&&m.host!=offer_.host))return false;offer_=m;offerMs_=now;haveOffer_=true;return true;}
  if(!busy()||m.host!=expected_.host||m.nonceA!=expected_.nonceA||m.nonceB!=expected_.nonceB||uint32_t(now-started_)>=30000)return false;
  if(m.kind==Kind::Unavailable){cancel("host unavailable");return true;}
  if(stage==Stage::Hello&&m.kind==Kind::Manifest){
   if(m.digest!=offer_.digest||m.boot!=offer_.boot||m.size!=offer_.size){cancel("host course changed; join again");return true;}
   expected_=m;expected_.count=0;stage=Stage::Data;waiting_=false;tries_=0;return true;
  }
  if(stage!=Stage::Data||m.kind!=Kind::Data||m.boot!=expected_.boot||m.digest!=expected_.digest||m.size!=expected_.size||m.offset!=received_)return false;
  if(m.count!=std::min(size_t(CHUNK),size_t(expected_.size)-received_))return false;
  std::memcpy(staging_.data()+received_,m.bytes.data(),m.count);received_+=m.count;waiting_=false;tries_=0;
  if(received_==expected_.size){
   if(!Package::validate(staging_.data(),received_)||u32(staging_.data()+received_-4)!=expected_.digest||staging_[4]!=expected_.host){cancel("course validation failed");return true;}
   stage=Stage::Complete;
  }return true;
 }
 const uint8_t* data()const{return staging_.data();}size_t size()const{return stage==Stage::Complete?received_:0;}
 void accepted(){stage=Stage::Idle;waiting_=false;error="";}
};
}}
