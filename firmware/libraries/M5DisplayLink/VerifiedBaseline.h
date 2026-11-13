#pragma once
// Controller ceiling cache for strict M5 commissioning. This stores only the three fields
// copied into RAM after a fresh identity match; it never sends a VESC command.
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <limits>

namespace m5link { namespace baseline {
struct Ceiling { float scale=0, minErpm=0, maxErpm=0; };
constexpr size_t BYTES=48;
constexpr const char* KEY="m5_bl_v1"; // new key: never import the legacy separate-field cache
constexpr float MAX_ERPM=2000000.0f; // serialization sanity bound, not an approved tuning value
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559,
              "Baseline record requires IEEE-754 binary32 floats");

inline uint32_t crc32(const uint8_t* p,size_t n) {
  uint32_t c=0xffffffffu;
  while(n--) { c^=*p++;for(unsigned i=0;i<8;++i)c=(c>>1)^(0xedb88320u & (0u-(c&1u))); }
  return ~c;
}
inline uint32_t read32(const uint8_t* p) {
  return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);
}
inline void write32(uint8_t* p,uint32_t n) {
  for(unsigned i=0;i<4;++i)p[i]=uint8_t(n>>(i*8));
}
inline void writeFloat(uint8_t* p,float value) {
  uint32_t bits;std::memcpy(&bits,&value,sizeof bits);write32(p,bits);
}
inline float readFloat(const uint8_t* p) {
  const uint32_t bits=read32(p);float value;std::memcpy(&value,&bits,sizeof value);return value;
}
inline bool canonicalUuid(const char* uuid,char out[24]) {
  if(!uuid)return false;
  bool nonzero=false;
  for(unsigned i=0;i<24;++i) {
    char c=uuid[i];
    if(c>='A'&&c<='F')c=char(c-'A'+'a');
    if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
    out[i]=c;nonzero|=c!='0';
  }
  // An all-zero UUID is not a usable identity, even though it consists of hex digits.
  return !uuid[24] && nonzero;
}
inline bool valid(const Ceiling& c) {
  return std::isfinite(c.scale) && c.scale>0 && c.scale<=1 &&
         std::isfinite(c.minErpm) && c.minErpm>=-MAX_ERPM && c.minErpm<=0 &&
         std::isfinite(c.maxErpm) && c.maxErpm>0 && c.maxErpm<=MAX_ERPM;
}
// Layout: magic M5BC (4), version1 (1), reserved zero (3), lowercase UUID hex (24),
// scale/min/max IEEE-754 float32 LE (12), CRC32 over the preceding44bytes (4).
inline bool encode(const char* freshUuid,const Ceiling& ceiling,uint8_t* out,size_t size=BYTES) {
  char uuid[24];
  if(!out || size!=BYTES || !valid(ceiling) || !canonicalUuid(freshUuid,uuid))return false;
  uint8_t data[BYTES]{};std::memcpy(data,"M5BC",4);data[4]=1;std::memcpy(data+8,uuid,24);
  writeFloat(data+32,ceiling.scale);writeFloat(data+36,ceiling.minErpm);writeFloat(data+40,ceiling.maxErpm);
  write32(data+44,crc32(data,44));std::memcpy(out,data,BYTES);return true;
}
// Caller must supply a UUID freshly read from this connection and already checked against
// its pin. This pure helper validates that value/record match; it cannot establish freshness.
// Any failure leaves the output ceiling unchanged.
inline bool decode(const uint8_t* data,size_t size,const char* freshUuid,Ceiling& out) {
  char uuid[24];
  if(!data || size!=BYTES || !canonicalUuid(freshUuid,uuid) || std::memcmp(data,"M5BC",4) ||
     data[4]!=1 || data[5] || data[6] || data[7] || read32(data+44)!=crc32(data,44) ||
     std::memcmp(data+8,uuid,24))return false;
  Ceiling result{readFloat(data+32),readFloat(data+36),readFloat(data+40)};
  if(!valid(result))return false;
  out=result;return true;
}

// Storage adapter: compatible with an open Arduino Preferences namespace, while remaining
// testable without Arduino. The storage object needs only getBytesLength/getBytes/putBytes.
// No legacy keys, individual field writes, global Preferences instance, or hardware commands.
template<class Nvs> bool load(Nvs& nvs,const char* freshUuid,Ceiling& out) {
  uint8_t data[BYTES];
  return nvs.getBytesLength(KEY)==BYTES && nvs.getBytes(KEY,data,BYTES)==BYTES &&
         decode(data,BYTES,freshUuid,out);
}
template<class Nvs> bool save(Nvs& nvs,const char* freshUuid,const Ceiling& ceiling) {
  uint8_t data[BYTES],check[BYTES];
  if(!encode(freshUuid,ceiling,data) || nvs.putBytes(KEY,data,BYTES)!=BYTES)return false;
  // One blob is the NVS commit unit. Confirm the exact stored record before reporting success.
  return nvs.getBytesLength(KEY)==BYTES && nvs.getBytes(KEY,check,BYTES)==BYTES &&
         std::memcmp(data,check,BYTES)==0;
}
}} // namespace m5link::baseline
