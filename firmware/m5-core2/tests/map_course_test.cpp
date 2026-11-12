#include "MapView.h"
#include "CourseStorage.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <vector>
using namespace m5dash;
const char* json=R"({"schema":1,"name":"Test outline","closed":true,"points":[[41.0938000,-73.4163000],[41.0940000,-73.4160000]]})";
struct Memory {
 std::vector<uint8_t> bytes;bool fail=false,badRead=false;
 size_t read(uint8_t* p,size_t n){if(bytes.size()>n||badRead)return 0;memcpy(p,bytes.data(),bytes.size());return bytes.size();}
 bool write(const uint8_t* p,size_t n){if(fail)return false;bytes.assign(p,p+n);return true;}
 bool clear(){bytes.clear();return true;}
};
std::string hex(const char* p,size_t n){const char* digits="0123456789abcdef";std::string s;for(size_t i=0;i<n;++i){s+=digits[uint8_t(p[i])>>4];s+=digits[uint8_t(p[i])&15];}return s;}
int main(){
 Course course;assert(courseio::parse(json,strlen(json),course));assert(course.count==2&&course.closed);
 courseio::Record record;size_t n=courseio::encode(course,record);Course loaded;assert(n==68&&courseio::decode(record.data(),n,loaded));
 assert(loaded.lat[0]==course.lat[0]&&loaded.lon[1]==course.lon[1]);
 for(size_t i=0;i<n;++i){auto corrupt=record;corrupt[i]^=1;assert(!courseio::decode(corrupt.data(),n,loaded));assert(loaded.count==2);}
 assert(!courseio::decode(record.data(),n-1,loaded));assert(!courseio::decode(record.data(),n+1,loaded));
 for(const char* bad:{"{}","[]",R"({"schema":1,"name":"","points":[[0,0],[0,1]]})",R"({"schema":1,"name":"x","points":[[0,0],[0,0]]})",R"({"schema":1,"name":"x","closed":1,"points":[[0,0],[0,1]]})",R"({"schema":1,"name":"x\u0000bad","points":[[0,0],[0,1]]})",R"({"schema":1,"name":"x","points":[[91,0],[0,1]]})"}){assert(!courseio::parse(bad,strlen(bad),loaded));assert(loaded.count==2);}
 for(const char* tail:{"extra"," {}"," true"}){std::string bad=std::string(json)+tail;assert(!courseio::parse(bad.c_str(),bad.size(),loaded));}
 courseio::Store<Memory> store;Course active=course;assert(store.save(course,active));assert(store.load(loaded));
 Course different=course;different.lat[0]+=.01;store.backend.fail=true;assert(!store.save(different,active));assert(active.lat[0]==course.lat[0]);assert(store.load(loaded)&&loaded.lat[0]==course.lat[0]);
 store.backend.fail=false;auto original=store.backend.bytes;store.backend.badRead=true;assert(!store.save(different,active));assert(active.lat[0]==course.lat[0]);store.backend.badRead=false;assert(store.load(loaded)&&loaded.lat[0]==different.lat[0]);
 // Complete write with a lost readback is unknown, not silently rolled back.
 store.backend.bytes=original;assert(store.load(loaded)&&loaded.lat[0]==course.lat[0]);
 courseio::Upload up;uint32_t crc=courseio::crc32(reinterpret_cast<const uint8_t*>(json),strlen(json));auto all=hex(json,strlen(json));
 assert(up.begin(strlen(json),crc,100));assert(up.chunk(0,all.c_str(),101));assert(up.finish(loaded,102));assert(!up.finish(loaded,103));
 assert(up.begin(strlen(json),crc,100));assert(!up.chunk(1,"ff",101));assert(!up.active());
 assert(up.begin(strlen(json),crc,100));assert(!up.chunk(0,"gg",101));assert(!up.active());
 assert(up.begin(strlen(json),crc,100));assert(!up.finish(loaded,101));
 assert(up.begin(strlen(json),crc^1,100));assert(up.chunk(0,all.c_str(),101));assert(!up.finish(loaded,102));
 assert(up.begin(strlen(json),crc,100));assert(!up.chunk(0,all.c_str(),30100));
 assert(up.begin(strlen(json),crc,0xfffffff0U));assert(up.chunk(0,all.c_str(),10));assert(up.finish(loaded,11));
 State s;s.self=3;auto& own=s.karts[3];own.seen=own.fix=own.hasPosition=true;own.received=own.fixReceived=100;own.lat=41.0938;own.lon=-73.4163;
 auto view=MapView::make(s,Course{},101);assert(view.valid&&view.following);double x,y;assert(view.project(own.lat,own.lon,x,y));assert(x==160&&y==120);
 State parsed;assert(parsed.ingest(R"({"t":"self","kart":3,"lat":41.0938000,"lon":-73.4163000,"fix":true,"gps_age_s":0,"fix_age_ms":200,"sats":11})",500));assert(parsed.karts[3].fixReported);assert(MapView::make(parsed,Course{},600).following);assert(!MapView::make(parsed,Course{},4000).following);
 const double scale=view.pixelsPerMeter;auto& peer=s.karts[8];peer=own;peer.lat+=3;peer.lon+=3;auto same=MapView::make(s,course,101);assert(same.following&&same.pixelsPerMeter==scale&&same.lat==own.lat&&same.lon==own.lon);
 assert(!MapView::make(s,Course{},1700).valid);auto overview=MapView::make(s,course,1700);assert(overview.valid&&!overview.following);
 double x0=-1e8,y0=100,x1=1e8,y1=100;assert(view.clip(x0,y0,x1,y1));assert(std::fabs(x0-view.left)<1e-5&&std::fabs(x1-(view.left+view.width-1))<1e-5);
 x0=0;y0=-1;x1=500;y1=-1;assert(!view.clip(x0,y0,x1,y1));x0=NAN;assert(!view.clip(x0,y0,x1,y1));
 x0=160;y0=-1000;x1=160;y1=1000;assert(view.clip(x0,y0,x1,y1));assert(y0>=0&&y1<=239);assert(!view.contains(160,240));
 State wrap;wrap.self=3;wrap.karts[3]=own;wrap.karts[3].received=wrap.karts[3].fixReceived=0xfffffff0U;assert(MapView::make(wrap,Course{},20).following);
 std::printf("Map follow/clipping, course validation/CRC/atomic readback and bounded upload tests passed; record_crc=%08x\n",courseio::get32(record.data()+n-4));
}
