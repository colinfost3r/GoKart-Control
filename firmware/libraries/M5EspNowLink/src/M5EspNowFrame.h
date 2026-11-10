#pragma once
// Pure bounded framing. Authentication belongs to the ESP-NOW adapter before consume().
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace m5now {
constexpr size_t MAX_LINE = 1151;           // excludes NUL/newline
constexpr size_t PACKET_MAX = 250;         // ESP-NOW v1 interoperable
constexpr size_t HEADER_SIZE = 20;
constexpr size_t TAG_SIZE = 16;
constexpr size_t CHUNK_SIZE = PACKET_MAX - HEADER_SIZE - TAG_SIZE;
constexpr size_t MAX_PARTS = (MAX_LINE + CHUNK_SIZE - 1) / CHUNK_SIZE;
constexpr uint32_t MAX_AGE_MS = 250;
constexpr uint32_t LINK_MS = 1500;
enum class Role : uint8_t { Heltec = 1, Display = 2 };
enum class Kind : uint8_t { Line = 1, Heartbeat = 2 };
enum class Result { Invalid, Partial, Duplicate, Line, Heartbeat };
inline uint16_t crc16(const uint8_t* p, size_t n) {
  uint16_t c = 0;
  for (size_t i=0;i<n;++i) { c ^= uint16_t(p[i]) << 8;
    for (unsigned b=0;b<8;++b) c = c & 0x8000 ? uint16_t((c << 1) ^ 0x1021) : uint16_t(c << 1);
  }
  return c;
}
inline uint16_t get16(const uint8_t* p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline uint32_t get32(const uint8_t* p) { return uint32_t(get16(p)) | (uint32_t(get16(p+2)) << 16); }
inline void put16(uint8_t* p,uint16_t x) { p[0]=uint8_t(x);p[1]=uint8_t(x>>8); }
inline void put32(uint8_t* p,uint32_t x) { put16(p,uint16_t(x));put16(p+2,uint16_t(x>>16)); }
inline bool later(uint32_t a,uint32_t b) { return int32_t(a-b)>0; }
inline size_t parts(size_t length) { return length ? (length+CHUNK_SIZE-1)/CHUNK_SIZE : 1; }

// Returns body length without its trailing authentication tag. Sender appends TAG_SIZE bytes.
inline size_t encode(uint8_t* out, Role role, Kind kind, uint32_t boot, uint32_t id,
                     const char* text, size_t length, uint8_t part) {
  if (!boot || !id || length>MAX_LINE || (kind==Kind::Line && (!text || !length)) ||
      (kind==Kind::Heartbeat && length) || part>=parts(length)) return 0;
  if (role!=Role::Heltec && role!=Role::Display) return 0;
  if (kind!=Kind::Line && kind!=Kind::Heartbeat) return 0;
  const size_t offset=size_t(part)*CHUNK_SIZE;
  const size_t count=length-offset>CHUNK_SIZE ? CHUNK_SIZE : length-offset;
  out[0]='G';out[1]='5';out[2]=1;out[3]=uint8_t(role);
  put32(out+4,boot);put32(out+8,id);put16(out+12,uint16_t(length));
  put16(out+14,crc16(reinterpret_cast<const uint8_t*>(text),length));
  out[16]=part;out[17]=uint8_t(parts(length));out[18]=uint8_t(kind);out[19]=0;
  if(count)std::memcpy(out+HEADER_SIZE,text+offset,count);
  return HEADER_SIZE+count;
}

class Assembler {
  Role local_;
  uint32_t peerBoot_=0,lastComplete_=0,retired_[4]{},retiredAt_=0;
  uint32_t activeBoot_=0,activeId_=0,firstMs_=0;
  uint16_t length_=0,crc_=0;
  uint8_t count_=0,mask_=0;
  char line_[MAX_LINE+1]{};
public:
  explicit Assembler(Role local=Role::Display):local_(local){}
  void setRole(Role role) { local_=role; clear(); peerBoot_=lastComplete_=retiredAt_=0;std::memset(retired_,0,sizeof retired_); }
  void clear() { activeBoot_=activeId_=0;mask_=count_=0;length_=0; }
  bool expire(uint32_t now) { if(activeId_ && uint32_t(now-firstMs_)>MAX_AGE_MS) { clear();return true; }return false; }
  const char* line() const { return line_; }
  uint32_t receivedMs() const { return firstMs_; }
  uint32_t peerBoot() const { return peerBoot_; }
  // authenticated data only; packet body excludes the HMAC tag.
  Result consume(const uint8_t* p,size_t n,uint32_t arrived) {
    expire(arrived);
    if(!p || n<HEADER_SIZE || n>PACKET_MAX-TAG_SIZE || p[0]!='G' || p[1]!='5' || p[2]!=1 ||
       p[3]!=uint8_t(local_==Role::Heltec?Role::Display:Role::Heltec) || p[19])return Result::Invalid;
    const uint32_t boot=get32(p+4),id=get32(p+8);
    const uint16_t length=get16(p+12),crc=get16(p+14);
    const uint8_t part=p[16],count=p[17];const Kind kind=Kind(p[18]);
    if(!boot || !id || length>MAX_LINE || count!=parts(length) || part>=count ||
       (kind!=Kind::Line && kind!=Kind::Heartbeat) ||
       (kind==Kind::Heartbeat && (length||crc)) || (kind==Kind::Line && !length))return Result::Invalid;
    const size_t offset=size_t(part)*CHUNK_SIZE;
    const size_t expected=length-offset>CHUNK_SIZE?CHUNK_SIZE:length-offset;
    if(n!=HEADER_SIZE+expected)return Result::Invalid;
    if(boot!=peerBoot_)for(uint32_t retired:retired_)if(retired==boot)return Result::Invalid;
    if(boot==peerBoot_ && !later(id,lastComplete_))return Result::Duplicate;
    if(activeId_ && (boot!=activeBoot_ || id!=activeId_)) {
      if(boot==activeBoot_ && !later(id,activeId_))return Result::Duplicate;
      clear();
    }
    if(!activeId_) { activeBoot_=boot;activeId_=id;firstMs_=arrived;length_=length;crc_=crc;count_=count;mask_=0; }
    if(length!=length_ || crc!=crc_ || count!=count_) { clear();return Result::Invalid; }
    if(mask_ & (1u<<part)) {
      if(expected && std::memcmp(line_+offset,p+HEADER_SIZE,expected)) {clear();return Result::Invalid;}
      return Result::Partial; // identical duplicate cannot renew the assembly deadline
    }
    if(expected)std::memcpy(line_+offset,p+HEADER_SIZE,expected);
    mask_|=uint8_t(1u<<part);
    if(mask_!=uint8_t((1u<<count_)-1u))return Result::Partial;
    if(crc16(reinterpret_cast<const uint8_t*>(line_),length_)!=crc_) {clear();return Result::Invalid;}
    for(size_t i=0;i<length_;++i)if(uint8_t(line_[i])<32 || line_[i]==127) {clear();return Result::Invalid;}
    line_[length_]=0;
    if(boot!=peerBoot_) {
      if(peerBoot_)retired_[retiredAt_++%4]=peerBoot_;
      peerBoot_=boot;
    }
    lastComplete_=id;activeBoot_=activeId_=0;mask_=count_=0;
    return kind==Kind::Heartbeat?Result::Heartbeat:Result::Line;
  }
};
}
