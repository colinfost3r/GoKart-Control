#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace m5now {
struct Pairing { uint8_t peer[6]{}, lmk[16]{}, pmk[16]{}; };
constexpr size_t PAIR_BYTES = 46;
inline uint32_t pairCrc(const uint8_t* p, size_t n) {
  uint32_t c=0xffffffffu;
  while(n--){c^=*p++;for(int i=0;i<8;++i)c=(c>>1)^(0xedb88320u & (0u-(c&1u)));}
  return ~c;
}
inline bool nonzero(const uint8_t* p,size_t n){uint8_t v=0;while(n--)v|=*p++;return v!=0;}
inline bool validPair(const Pairing& p){return !(p.peer[0]&1)&&nonzero(p.peer,6)&&nonzero(p.lmk,16)&&nonzero(p.pmk,16);}
inline bool encodePair(const Pairing& p,uint8_t* b,size_t n){
  if(n!=PAIR_BYTES||!validPair(p))return false;
  memcpy(b,"MEP1",4);memcpy(b+4,p.peer,6);memcpy(b+10,p.lmk,16);memcpy(b+26,p.pmk,16);
  uint32_t c=pairCrc(b,42);for(int i=0;i<4;++i)b[42+i]=uint8_t(c>>(8*i));return true;
}
inline bool decodePair(const uint8_t* b,size_t n,Pairing& p){
  if(n!=PAIR_BYTES||memcmp(b,"MEP1",4))return false;
  uint32_t c=0;for(int i=0;i<4;++i)c|=uint32_t(b[42+i])<<(8*i);
  if(c!=pairCrc(b,42))return false;
  Pairing v;memcpy(v.peer,b+4,6);memcpy(v.lmk,b+10,16);memcpy(v.pmk,b+26,16);
  if(!validPair(v))return false;p=v;return true;
}
inline int hexNibble(char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1;}
inline bool parseHex(const char* s,uint8_t* out,size_t n){
  if(strlen(s)!=n*2)return false;
  for(size_t i=0;i<n;++i){int a=hexNibble(s[i*2]),b=hexNibble(s[i*2+1]);if(a<0||b<0)return false;out[i]=uint8_t(a*16+b);}return true;
}
inline bool parseMac(const char* s,uint8_t* out){
  if(strlen(s)!=17)return false;
  for(int i=0;i<6;++i){if(i&&s[i*3-1]!=':')return false;int a=hexNibble(s[i*3]),b=hexNibble(s[i*3+1]);if(a<0||b<0)return false;out[i]=uint8_t(a*16+b);}return true;
}
} // namespace m5now
