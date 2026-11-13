#include "VerifiedBaseline.h"
#include <array>
#include <cassert>
#include <iostream>
#include <map>
#include <string>
#include <vector>
namespace bl=m5link::baseline;
constexpr const char* UUID="2c004c000951343037353739";
constexpr const char* OTHER="2c004c000951343037353738";
struct FakeNvs {
  std::map<std::string,std::vector<uint8_t>> blobs;
  unsigned writes=0;
  bool refuseCommit=false,corruptCommit=false,shortRead=false;
  size_t getBytesLength(const char* key) {auto p=blobs.find(key);return p==blobs.end()?0:p->second.size();}
  size_t getBytes(const char* key,void* out,size_t n) {
    auto p=blobs.find(key);if(p==blobs.end()||p->second.size()!=n)return 0;
    std::memcpy(out,p->second.data(),n);return shortRead?n-1:n;
  }
  size_t putBytes(const char* key,const void* bytes,size_t n) {
    assert(std::string(key)==bl::KEY && n==bl::BYTES);++writes;
    if(refuseCommit)return 0;
    const uint8_t* p=static_cast<const uint8_t*>(bytes);blobs[key]={p,p+n};
    if(corruptCommit)blobs[key][40]^=1;
    return n;
  }
};
static void seal(std::array<uint8_t,bl::BYTES>& data){bl::write32(data.data()+44,bl::crc32(data.data(),44));}
static bool same(const bl::Ceiling& a,const bl::Ceiling& b){return a.scale==b.scale&&a.minErpm==b.minErpm&&a.maxErpm==b.maxErpm;}
int main(){
  const bl::Ceiling ceiling{1,-150000,150000},sentinel{.25f,-12,34};
  std::array<uint8_t,bl::BYTES> good{};assert(bl::encode(UUID,ceiling,good.data()));
  assert(bl::crc32(reinterpret_cast<const uint8_t*>("123456789"),9)==0xcbf43926u);
  assert(good[32]==0&&good[33]==0&&good[34]==0x80&&good[35]==0x3f); // explicit LE binary32
  bl::Ceiling out=sentinel;assert(bl::decode(good.data(),good.size(),UUID,out)&&same(out,ceiling));
  assert(bl::decode(good.data(),good.size(),"2C004C000951343037353739",out));
  out=sentinel;assert(!bl::decode(good.data(),good.size(),OTHER,out)&&same(out,sentinel));
  for(size_t i=0;i<good.size();++i){auto bad=good;bad[i]^=1;out=sentinel;assert(!bl::decode(bad.data(),bad.size(),UUID,out)&&same(out,sentinel));}
  for(unsigned where: {0u,4u,5u,6u,7u,8u}) {auto bad=good;bad[where]^=1;seal(bad);assert(!bl::decode(bad.data(),bad.size(),UUID,out));}
  for(size_t n: {size_t(0),size_t(47),size_t(49)})assert(!bl::decode(good.data(),n,UUID,out));
  assert(!bl::decode(nullptr,good.size(),UUID,out));
  for(const char* uuid:{"","2c004c00095134303735373","2c004c0009513430373537390","2g004c000951343037353739","000000000000000000000000"}){
    auto data=good;assert(!bl::encode(uuid,ceiling,data.data()));assert(data==good);
    assert(!bl::decode(good.data(),good.size(),uuid,out));
  }
  assert(!bl::encode(nullptr,ceiling,good.data()));
  const float nan=std::numeric_limits<float>::quiet_NaN(),inf=std::numeric_limits<float>::infinity();
  const std::vector<bl::Ceiling> invalid={{0,-1,1},{-.1f,-1,1},{1.001f,-1,1},{nan,-1,1},{inf,-1,1},
    {1,1,1},{1,-2000001,1},{1,-inf,1},{1,nan,1},{1,-1,0},{1,-1,-1},{1,-1,2000001},{1,-1,inf},{1,-1,nan}};
  for(auto c:invalid){auto data=good;assert(!bl::encode(UUID,c,data.data()));assert(data==good);
    bl::writeFloat(data.data()+32,c.scale);bl::writeFloat(data.data()+36,c.minErpm);bl::writeFloat(data.data()+40,c.maxErpm);seal(data);
    out=sentinel;assert(!bl::decode(data.data(),data.size(),UUID,out)&&same(out,sentinel));
  }
  assert(bl::valid({.0001f,-2000000,2000000}));assert(bl::valid({1,0,.0001f}));

  FakeNvs nvs;nvs.blobs["bl_uuid"]={UUID,UUID+24};nvs.blobs["bl_scale"]={0,0,128,63};
  out=sentinel;assert(!bl::load(nvs,UUID,out)&&same(out,sentinel)); // never import legacy split fields
  assert(bl::save(nvs,UUID,ceiling)&&nvs.writes==1);assert(bl::load(nvs,UUID,out)&&same(out,ceiling));
  out=sentinel;assert(!bl::load(nvs,OTHER,out)&&same(out,sentinel));
  nvs.refuseCommit=true;assert(!bl::save(nvs,UUID,{.5f,-100,100})&&nvs.writes==2);
  assert(bl::load(nvs,UUID,out)&&same(out,ceiling)); // interrupted commit retains complete old blob
  nvs.refuseCommit=false;nvs.corruptCommit=true;assert(!bl::save(nvs,UUID,{.5f,-100,100}));
  out=sentinel;assert(!bl::load(nvs,UUID,out)&&same(out,sentinel));
  nvs.corruptCommit=false;assert(bl::save(nvs,UUID,ceiling));nvs.shortRead=true;
  assert(!bl::load(nvs,UUID,out));assert(!bl::save(nvs,UUID,ceiling));
  const unsigned writes=nvs.writes;assert(!bl::save(nvs,UUID,{nan,-1,1})&&nvs.writes==writes);
  std::cout<<"Verified baseline: identity, version/CRC corruption, finite/range bounds and single-blob storage recovery passed\n";
}
