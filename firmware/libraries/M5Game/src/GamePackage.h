#pragma once
#include <array>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cmath>

namespace m5game {
constexpr size_t MAX_TRACK=128,MAX_ZONES=16,MAX_LINES=64,HEADER=96,ZONE_BYTES=96;
constexpr size_t MAX_PACKAGE=HEADER+MAX_TRACK*8+MAX_ZONES*ZONE_BYTES+MAX_LINES*16+4;
inline uint16_t u16(const uint8_t*p){return uint16_t(p[0])|uint16_t(p[1])<<8;}
inline uint32_t u32(const uint8_t*p){return uint32_t(u16(p))|uint32_t(u16(p+2))<<16;}
inline void put16(uint8_t*p,uint16_t v){p[0]=v;p[1]=v>>8;}
inline void put32(uint8_t*p,uint32_t v){put16(p,uint16_t(v));put16(p+2,uint16_t(v>>16));}
inline int32_t i32(const uint8_t*p){uint32_t v=u32(p);return v<=0x7fffffff?int32_t(v):int32_t(int64_t(v)-4294967296LL);}
inline uint32_t crc32(const uint8_t*p,size_t n){uint32_t c=~0U;while(n--){c^=*p++;for(int i=0;i<8;++i)c=(c>>1)^((c&1)?0xedb88320U:0);}return ~c;}
struct Point{double lat=0,lon=0;};
inline Point point(const uint8_t*p){return {i32(p)/1e7,i32(p+4)/1e7};}
inline bool validPoint(const uint8_t*p){return std::abs(int64_t(i32(p)))<=900000000LL&&std::abs(int64_t(i32(p+4)))<=1800000000LL;}
inline double distance(Point a,Point b){double x=(a.lon-b.lon)*111320.0*std::cos((a.lat+b.lat)*0.008726646259972),y=(a.lat-b.lat)*111320.0;return std::sqrt(x*x+y*y);}
enum class ZoneType:uint8_t{Boost=1,Mud=2,Item=3};
struct Zone {
  ZoneType type;uint8_t shape,count,secs,scale;uint16_t radiusCm,cooldownS;Point center;Point points[8];
};
// Compact, versioned binary package. All integers little-endian; positions are signed WGS84 e7.
// Rules v1 is Eamon's multiplayer table (boost/shell/lightning/rocket/boost3/star/shield/magnet/empty).
// A package is geography/rules data only: it contains no console command or vehicle credentials.
class Package {
  std::array<uint8_t,MAX_PACKAGE> data_{};size_t size_=0;
 public:
  static bool validate(const uint8_t*p,size_t n){
    if(!p||n<HEADER+16+4||n>MAX_PACKAGE||std::memcmp(p,"GKG1",4)||p[4]<1||p[4]>8||p[5]!=1||p[6]&~7||!p[7]||p[7]>40||!u32(p+8)||!u32(p+12))return false;
    size_t nt=u16(p+16),nz=u16(p+18),nl=u16(p+20);
    if(nt<2||nt>MAX_TRACK||nz>MAX_ZONES||nl>MAX_LINES||p[22]!=1||p[23]||n!=HEADER+nt*8+nz*ZONE_BYTES+nl*16+4||u32(p+n-4)!=crc32(p,n-4))return false;
    for(size_t i=0;i<40;++i){uint8_t c=p[24+i];if(i<p[7]?(c<32||c>126):c!=0)return false;}
    for(size_t i=84;i<HEADER;++i)if(p[i])return false;
    if(p[6]&4){if(!validPoint(p+64)||!validPoint(p+72)||distance(point(p+64),point(p+72))<1||u32(p+80)<1000||u32(p+80)>300000)return false;}
    else for(size_t i=64;i<84;++i)if(p[i])return false;
    bool distinct=false;Point origin=point(p+HEADER);
    for(size_t i=0;i<nt;++i){const uint8_t*q=p+HEADER+i*8;if(!validPoint(q)||distance(origin,point(q))>5000)return false;if(i&&std::memcmp(q,p+HEADER,8))distinct=true;}
    if(!distinct)return false;
    for(size_t i=0;i<nz;++i){const uint8_t*q=p+HEADER+nt*8+i*ZONE_BYTES;
      if(q[0]<1||q[0]>3||q[1]>1||q[3]<1||q[3]>30||q[4]<10||q[4]>100||!validPoint(q+12)||distance(origin,point(q+12))>5000||u16(q+10)<1||u16(q+10)>600)return false;
      for(size_t j=5;j<8;++j)if(q[j])return false;
      if(!q[1]){if(q[2]||u16(q+8)<300||u16(q+8)>20000)return false;for(size_t j=20;j<84;++j)if(q[j])return false;}
      else {if(q[2]<3||q[2]>8||u16(q+8))return false;for(size_t j=0;j<8;++j){const uint8_t*r=q+20+8*j;if(j<q[2]){if(!validPoint(r)||distance(origin,point(r))>5000)return false;}else for(size_t k=0;k<8;++k)if(r[k])return false;}}
      for(size_t j=84;j<ZONE_BYTES;++j)if(q[j])return false;
    }
    const uint8_t*lines=p+HEADER+nt*8+nz*ZONE_BYTES;
    for(size_t i=0;i<nl*2;++i)if(!validPoint(lines+8*i)||distance(origin,point(lines+8*i))>10000)return false;
    return true;
  }
  bool load(const uint8_t*p,size_t n){if(!validate(p,n))return false;std::memmove(data_.data(),p,n);size_=n;return true;}
  bool valid()const{return size_!=0;}void clear(){size_=0;}
  const uint8_t* data()const{return data_.data();}size_t size()const{return size_;}
  uint8_t host()const{return data_[4];}uint32_t instance()const{return u32(data_.data()+8);}uint32_t revision()const{return u32(data_.data()+12);}
  uint32_t digest()const{return valid()?u32(data()+size()-4):0;}size_t tracks()const{return u16(data()+16);}size_t zones()const{return u16(data()+18);}size_t lines()const{return u16(data()+20);}
  bool closed()const{return data_[6]&1;}bool enabled()const{return data_[6]&2;}bool hasLap()const{return data_[6]&4;}
  uint32_t minLapMs()const{return u32(data()+80);}Point lapA()const{return point(data()+64);}Point lapB()const{return point(data()+72);}
  void name(char*out,size_t cap)const{if(!cap)return;size_t n=data_[7]<cap-1?data_[7]:cap-1;std::memcpy(out,data()+24,n);out[n]=0;}
  Point track(size_t i)const{return i<tracks()?point(data()+HEADER+8*i):Point{};}
  Zone zone(size_t i)const{Zone z{};if(i>=zones())return z;const uint8_t*q=data()+HEADER+tracks()*8+i*ZONE_BYTES;
    z.type=ZoneType(q[0]);z.shape=q[1];z.count=q[2];z.secs=q[3];z.scale=q[4];z.radiusCm=u16(q+8);z.cooldownS=u16(q+10);z.center=point(q+12);
    for(size_t j=0;j<z.count;++j)z.points[j]=point(q+20+8*j);return z;}
  Point line(size_t i,bool end)const{return i<lines()?point(data()+HEADER+tracks()*8+zones()*ZONE_BYTES+i*16+(end?8:0)):Point{};}
};
}
