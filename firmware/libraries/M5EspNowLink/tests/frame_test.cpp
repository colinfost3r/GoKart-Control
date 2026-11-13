#include "M5EspNowFrame.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using namespace m5now;
using Packet=std::vector<uint8_t>;
static std::vector<Packet> frames(const std::string& text,uint32_t boot=7,uint32_t id=1,Role sender=Role::Heltec) {
  std::vector<Packet> result;
  for(size_t part=0;part<parts(text.size());++part) {
    uint8_t p[PACKET_MAX];auto n=encode(p,sender,Kind::Line,boot,id,text.c_str(),text.size(),uint8_t(part));
    assert(n);result.emplace_back(p,p+n);
  }
  return result;
}
static Result feed(Assembler& a,const Packet& p,uint32_t time) {return a.consume(p.data(),p.size(),time);}
int main() {
  assert(crc16(reinterpret_cast<const uint8_t*>("123456789"),9)==0x31c3);
  // Largest supported JSON fits six ESP-NOW-v1 packets including authentication tags.
  std::string text(MAX_LINE,'x');text.front()='{';text.back()='}';auto f=frames(text);
  assert(f.size()==6);for(auto& p:f)assert(p.size()+TAG_SIZE<=250);
  Assembler a;for(size_t i=0;i<f.size();++i)assert(feed(a,f[i],100+uint32_t(i))==(i+1==f.size()?Result::Line:Result::Partial));
  assert(std::string(a.line())==text && a.receivedMs()==100);
  assert(feed(a,f.front(),110)==Result::Duplicate); // no whole-line replay

  // Out-of-order fragments and exact duplicate fragments assemble once; never renew age.
  Assembler reordered;assert(feed(reordered,f[2],100)==Result::Partial);
  assert(feed(reordered,f[2],130)==Result::Partial);
  assert(feed(reordered,f[0],140)==Result::Partial);assert(feed(reordered,f[5],150)==Result::Partial);
  assert(feed(reordered,f[1],160)==Result::Partial);assert(feed(reordered,f[4],170)==Result::Partial);
  assert(feed(reordered,f[3],180)==Result::Line);assert(reordered.receivedMs()==100);

  // A lost part times out, but a fresh later line recovers without replaying the old one.
  Assembler lost;assert(feed(lost,f[0],10)==Result::Partial);assert(lost.expire(261));
  auto next=frames("{\"fresh\":true}",7,2);assert(feed(lost,next[0],270)==Result::Line);
  assert(feed(lost,f[1],280)==Result::Duplicate);

  // millis wrap is normal. This deadline is based on first arrival, not final fragment.
  Assembler wrapping;for(size_t i=0;i<f.size();++i)
    assert(feed(wrapping,f[i],0xfffffff0u+uint32_t(i)*10)==(i+1==f.size()?Result::Line:Result::Partial));
  assert(wrapping.receivedMs()==0xfffffff0u);

  // A genuinely new sender boot can start after lost early messages. Retired boot cannot return.
  Assembler boots;auto old=frames("old",11,800);auto fresh=frames("new",12,33);
  assert(feed(boots,old[0],0)==Result::Line);assert(feed(boots,fresh[0],20)==Result::Line);
  assert(feed(boots,frames("replayed",11,900)[0],30)==Result::Invalid);
  assert(std::string(boots.line())=="new");

  // Altered content is detected by CRC even if framing remains plausible.
  Assembler corrupt;auto bad=f;bad[3][HEADER_SIZE]^=1;
  for(size_t i=0;i<bad.size();++i)assert(feed(corrupt,bad[i],100+uint32_t(i))==(i+1==bad.size()?Result::Invalid:Result::Partial));
  assert(feed(corrupt,next[0],200)==Result::Line);

  // Malformed size/count/index/version/role must not change the accepted sequence.
  for(unsigned variation=0;variation<8;++variation) {
    Assembler malformed;auto p=next[0];
    switch(variation) {
      case 0:p[2]=2;break;case 1:p[3]=uint8_t(Role::Display);break;
      case 2:p[16]=7;break;case 3:p[17]=7;break;case 4:p[19]=1;break;
      case 5:put16(p.data()+12,MAX_LINE+1);break;case 6:p.pop_back();break;
      case 7:put32(p.data()+8,0);break;
    }
    assert(feed(malformed,p,10)==Result::Invalid);assert(feed(malformed,next[0],20)==Result::Line);
  }
  // Conflicting duplicate data invalidates an in-flight line.
  Assembler conflict;assert(feed(conflict,f[0],10)==Result::Partial);
  auto wrong=f[0];wrong[HEADER_SIZE]^=1;assert(feed(conflict,wrong,20)==Result::Invalid);

  // Mixing lengths/CRC in a shared boot/message cannot make a valid line.
  Assembler mixed;assert(feed(mixed,f[0],10)==Result::Partial);
  auto changed=f[1];changed[14]^=1;assert(feed(mixed,changed,20)==Result::Invalid);
  Assembler controls;assert(feed(controls,frames("status\n")[0],10)==Result::Invalid);

  // Heartbeats have no command string and cannot bypass direction/schema checks.
  uint8_t p[250];size_t n=encode(p,Role::Display,Kind::Heartbeat,123,1,nullptr,0,0);
  assert(n==HEADER_SIZE);Assembler supervisor(Role::Heltec);
  assert(supervisor.consume(p,n,42)==Result::Heartbeat && !*supervisor.line());
  assert(supervisor.consume(p,n,43)==Result::Duplicate);
  assert(supervisor.consume(p,n-1,44)==Result::Invalid);

  // Bounds checked at source, including empty text and attempts to create >6 fragments.
  assert(!encode(p,Role::Heltec,Kind::Line,1,1,"",0,0));
  assert(!encode(p,Role::Heltec,Kind::Line,1,1,text.c_str(),MAX_LINE+1,0));
  assert(!encode(p,Role::Heltec,Kind::Line,1,1,text.c_str(),MAX_LINE,6));
  // Deterministic malformed-packet fuzzing under ASan/UBSan, including truncated headers.
  uint32_t rng=0x45c21a3u;
  for(unsigned sample=0;sample<10000;++sample) {
    uint8_t fuzz[251];for(auto& value:fuzz){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;value=uint8_t(rng);}
    Assembler parser;parser.consume(fuzz,sample%sizeof fuzz,sample);
  }
  std::cout<<"ESP-NOW framing: size, loss/recovery, reordering, duplicate/replay, boot change, corruption, wrap and bounds passed\n";
}
