#pragma once
#include <cstdint>
namespace m5game {
// Radio generation freshness, independent of motor state. Sequence is the host's
// existing rolling TX sequence. Retired boot ids cannot displace a newer boot.
struct Generation {
 uint32_t digest=0,boot=0,seen=0,retired[4]{};uint8_t seq=0,cursor=0;bool heard=false;
 bool fresh(uint32_t now)const{return heard&&digest&&uint32_t(now-seen)<6500;}
 bool accept(uint32_t nextBoot,uint32_t nextDigest,uint8_t nextSeq,uint32_t now){
  if(!nextBoot)return false;
  if(heard&&boot==nextBoot&&uint32_t(now-seen)<6500){uint8_t delta=uint8_t(nextSeq-seq);if(!delta||delta>127)return false;}
  if(heard&&boot!=nextBoot){for(auto b:retired)if(b==nextBoot)return false;retired[cursor++%4]=boot;}
  boot=nextBoot;digest=nextDigest;seq=nextSeq;seen=now;heard=true;return true;
 }
};
}
