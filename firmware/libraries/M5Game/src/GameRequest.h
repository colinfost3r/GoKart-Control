#pragma once
#include <M5DisplayLink.h>
namespace m5game {
// Game protocol 2 (owner 2026-11-12): the host's course fixes the speed a joined kart plays at, and a
// boost is a step up from the mode in force, never an absolute scale chosen by the display.
//   Join  arg = game speed + 1 (1 ECO, 2 NORMAL; a game never runs at the top mode).
//   Boost arg = seconds<<8 | level (1 = one mode up, 2 = the top mode).
constexpr uint8_t GAME_VERSION=2,BOOST_STEP=1,BOOST_TOP=2;
enum class Action:uint8_t{Join=1,Leave=2,Shell=3,Lightning=4,Boost=5,Star=6,Shield=7,Mud=8};
struct Request{uint32_t token=0,id=0;uint8_t session=0;Action action=Action::Leave;uint16_t arg=0;uint32_t course=0,boot=0;};
inline bool valid(const Request&r){
 if(!r.boot||!r.course||!r.token||!r.id||!r.session||r.session>8)return false;
 switch(r.action){
 case Action::Join:return r.arg>=1&&r.arg<=2;
 case Action::Leave:case Action::Lightning:case Action::Star:case Action::Shield:return !r.arg;
 case Action::Shell:return r.arg>=1&&r.arg<=8;
 case Action::Boost:return (r.arg>>8)>=1&&(r.arg>>8)<=30&&((r.arg&255)==BOOST_STEP||(r.arg&255)==BOOST_TOP);
 case Action::Mud:return r.arg>=1&&r.arg<=30;
 }return false;
}
// Separate typed allowlist; never forward a display line to the USB console.
inline size_t encode(char*out,size_t n,const Request&r){if(n<62||!valid(r))return 0;
 int got=snprintf(out,n,"m5game %08lx %08lx %02x %02x %04x %08lx %08lx",(unsigned long)r.token,(unsigned long)r.id,r.session,unsigned(r.action),r.arg,(unsigned long)r.course,(unsigned long)r.boot);
 return size_t(got+snprintf(out+got,n-size_t(got)," %04x\n",m5link::crc16(out,size_t(got))));
}
inline bool decode(const char*s,Request&r){
 if(strlen(s)!=58||strncmp(s,"m5game ",7)||s[15]!=' '||s[24]!=' '||s[27]!=' '||s[30]!=' '||s[35]!=' '||s[44]!=' '||s[53]!=' ')return false;
 uint32_t t,i,ss,act,arg,course,boot,crc;
 if(!m5link::hex(s+7,8,t)||!m5link::hex(s+16,8,i)||!m5link::hex(s+25,2,ss)||!m5link::hex(s+28,2,act)||!m5link::hex(s+31,4,arg)||!m5link::hex(s+36,8,course)||!m5link::hex(s+45,8,boot)||!m5link::hex(s+54,4,crc)||m5link::crc16(s,53)!=crc)return false;
 Request next{t,i,uint8_t(ss),Action(act),uint16_t(arg),course,boot};if(!valid(next))return false;r=next;return true;
}
}
