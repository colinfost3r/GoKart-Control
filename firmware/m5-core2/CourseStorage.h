#pragma once
#include "DisplayState.h"
#include <array>
#include <cstring>
#include <cstdint>
#include <memory>
#include <new>

namespace m5dash { namespace courseio {
constexpr size_t MAX_JSON=8192,MAX_RECORD=52+8*Course::MAX,CHUNK_BYTES=128;
constexpr uint32_t UPLOAD_MS=30000;
inline uint32_t crc32(const uint8_t* p,size_t n) {
  uint32_t c=0xffffffffU;
  for(size_t i=0;i<n;++i){c^=p[i];for(int b=0;b<8;++b)c=(c>>1)^((c&1)?0xedb88320U:0);}
  return c^0xffffffffU;
}
inline void put32(uint8_t* p,uint32_t n){p[0]=n>>24;p[1]=n>>16;p[2]=n>>8;p[3]=n;}
inline uint32_t get32(const uint8_t* p){return uint32_t(p[0])<<24|uint32_t(p[1])<<16|uint32_t(p[2])<<8|p[3];}
using Record=std::array<uint8_t,MAX_RECORD>;
inline bool decode(const uint8_t* p,size_t n,Course& out) {
  if(n<68||n>MAX_RECORD||memcmp(p,"GKC1",4))return false;
  size_t count=(size_t(p[4])<<8)|p[5];size_t names=p[7];
  if(count<2||count>Course::MAX||n!=52+count*8||p[6]>1||names<1||names>40||get32(p+n-4)!=crc32(p,n-4))return false;
  Course next;next.count=count;next.closed=p[6];
  for(size_t i=0;i<40;++i){if(i<names){if(p[8+i]<32||p[8+i]==127)return false;next.name[i]=char(p[8+i]);}else if(p[8+i])return false;}
  next.name[names]=0;bool distinct=false;
  for(size_t i=0;i<count;++i){
    uint32_t a=get32(p+48+i*8),b=get32(p+52+i*8);
    next.lat[i]=(a<=0x7fffffffU?double(a):double(a)-4294967296.0)/1e7;
    next.lon[i]=(b<=0x7fffffffU?double(b):double(b)-4294967296.0)/1e7;
    if(!location(next.lat[i],next.lon[i]))return false;
    if(i&&(next.lat[i]!=next.lat[0]||next.lon[i]!=next.lon[0]))distinct=true;
  }
  if(!distinct)return false;out=next;return true;
}
inline size_t encode(const Course& c,Record& out) {
  size_t names=strnlen(c.name,41);if(c.count<2||c.count>Course::MAX||names<1||names>40)return 0;
  out.fill(0);memcpy(out.data(),"GKC1",4);out[4]=c.count>>8;out[5]=c.count;out[6]=c.closed;out[7]=names;memcpy(out.data()+8,c.name,names);
  for(size_t i=0;i<names;++i)if(uint8_t(c.name[i])<32||c.name[i]==127)return 0;
  bool distinct=false;int32_t firstLat=0,firstLon=0;
  for(size_t i=0;i<c.count;++i){
    if(!location(c.lat[i],c.lon[i]))return 0;
    int32_t lat=int32_t(llround(c.lat[i]*1e7)),lon=int32_t(llround(c.lon[i]*1e7));
    if(!i){firstLat=lat;firstLon=lon;}else if(lat!=firstLat||lon!=firstLon)distinct=true;
    put32(out.data()+48+i*8,uint32_t(lat));put32(out.data()+52+i*8,uint32_t(lon));
  }
  if(!distinct)return 0;
  size_t n=52+c.count*8;put32(out.data()+n-4,crc32(out.data(),n-4));return n;
}
inline bool singleObject(const char* p,size_t n) {
  size_t i=0;while(i<n&&(p[i]==' '||p[i]=='\t'||p[i]=='\r'||p[i]=='\n'))++i;
  if(i==n||p[i]!='{')return false;
  int depth=0;bool quoted=false,escaped=false;
  for(;i<n;++i){char c=p[i];if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;continue;}
    if(c=='"')quoted=true;else if(c=='{'||c=='[')++depth;else if(c=='}'||c==']'){
      if(--depth<0)return false;if(depth==0){for(++i;i<n;++i)if(p[i]!=' '&&p[i]!='\t'&&p[i]!='\r'&&p[i]!='\n')return false;return true;}
    }
  }
  return false;
}
inline bool parse(const char* p,size_t n,Course& out) {
  if(!p||n<2||n>MAX_JSON||strlen(p)!=n||!singleObject(p,n))return false;
  JsonDocument d;if(deserializeJson(d,p,n,DeserializationOption::NestingLimit(5)))return false;
  std::unique_ptr<Course> next(new(std::nothrow) Course);
  if(!next||!next->load(d.as<JsonVariantConst>()))return false;
  Record r;size_t len=encode(*next,r);return len&&decode(r.data(),len,out);
}
// Backend writes one complete NVS blob. No separate count/pointer metadata can
// become committed ahead of the points. Immediate readback is required for success.
template<class Backend> class Store {
 public:
  Backend backend;
  bool load(Course& out) {Record r;size_t n=backend.read(r.data(),r.size());return n&&decode(r.data(),n,out);}
  bool save(const Course& next,Course& active) {
    Record r,check;size_t n=encode(next,r);if(!n||!backend.write(r.data(),n))return false;
    size_t got=backend.read(check.data(),check.size());if(got!=n||memcmp(r.data(),check.data(),n))return false;
    return decode(check.data(),got,active);
  }
  bool clear(){return backend.clear();}
};
class Upload {
  std::array<char,MAX_JSON+1> bytes_{};
  size_t expected_=0,received_=0;uint32_t crc_=0,started_=0;bool active_=false;
 public:
  const char* error="";
  bool active()const{return active_;}size_t received()const{return received_;}
  void abort(){active_=false;expected_=received_=0;}
  bool begin(size_t n,uint32_t crc,uint32_t now){abort();if(n<2||n>MAX_JSON){error="size";return false;}expected_=n;crc_=crc;started_=now;active_=true;error="";return true;}
  bool fresh(uint32_t now){if(!active_){error="no_upload";return false;}if(uint32_t(now-started_)>=UPLOAD_MS){abort();error="upload_expired";return false;}return true;}
  bool chunk(size_t offset,const char* hex,uint32_t now) {
    if(!fresh(now))return false;size_t chars=strlen(hex);
    if(offset!=received_||!chars||chars>CHUNK_BYTES*2||chars%2||received_+chars/2>expected_){abort();error="chunk_order_or_size";return false;}
    uint8_t tmp[CHUNK_BYTES];
    for(size_t i=0;i<chars/2;++i){uint32_t v;if(!m5link::hex(hex+2*i,2,v)){abort();error="chunk_hex";return false;}tmp[i]=uint8_t(v);}
    memcpy(bytes_.data()+received_,tmp,chars/2);received_+=chars/2;return true;
  }
  bool finish(Course& out,uint32_t now) {
    if(!fresh(now))return false;active_=false;
    if(received_!=expected_){error="incomplete";return false;}
    bytes_[received_]=0;
    if(crc32(reinterpret_cast<const uint8_t*>(bytes_.data()),received_)!=crc_){error="crc";return false;}
    if(!parse(bytes_.data(),received_,out)){error="invalid_course";return false;}
    error="";return true;
  }
};
}}

#ifdef ARDUINO
#include <Preferences.h>
namespace m5dash {
class CoursePreferences {
 public:
  bool present(){Preferences p;if(!p.begin("m5course",true))return false;bool yes=p.isKey("outline_v1");p.end();return yes;}
  size_t read(uint8_t* out,size_t capacity){Preferences p;if(!p.begin("m5course",true))return 0;size_t n=p.getBytesLength("outline_v1");if(!n||n>capacity){p.end();return 0;}size_t got=p.getBytes("outline_v1",out,n);p.end();return got==n?n:0;}
  bool write(const uint8_t* data,size_t n){Preferences p;if(!p.begin("m5course",false))return false;bool ok=p.putBytes("outline_v1",data,n)==n;p.end();return ok;}
  bool clear(){Preferences p;if(!p.begin("m5course",false))return false;bool ok=!p.isKey("outline_v1")||p.remove("outline_v1");p.end();return ok;}
};
class CourseManager {
  courseio::Store<CoursePreferences> store_;
  courseio::Upload upload_;
  Course fallback_;
  bool internal_=false;
  const char* error_="";
  static bool decimal(const char* s,size_t n,uint32_t& v){if(!n||n>8)return false;v=0;for(size_t i=0;i<n;++i){if(s[i]<'0'||s[i]>'9')return false;v=v*10+unsigned(s[i]-'0');}return true;}
 public:
  Course active;
  const char* source()const{return internal_?"internal":fallback_.count?"sd":"none";}
  const char* error()const{return error_;}
  void begin(){internal_=store_.load(active);if(!internal_&&store_.backend.present())error_="internal_invalid";}
  void sdFallback(const Course& c){fallback_=c;if(!internal_)active=c;}
  void sdError(const char* error){if(!internal_)error_=error;}
  void status(Print& out,const char* action="status",bool ok=true){
    JsonDocument d;d["t"]="course";d["v"]=1;d["action"]=action;d["ok"]=ok;d["source"]=source();d["name"]=active.name;d["points"]=active.count;d["closed"]=active.closed;d["error"]=error_;d["upload_active"]=upload_.active();d["received"]=upload_.received();
    courseio::Record r;size_t n=courseio::encode(active,r);char hash[9];snprintf(hash,sizeof hash,"%08lx",(unsigned long)(n?courseio::get32(r.data()+n-4):0));d["record_crc32"]=hash;
    serializeJson(d,out);out.println();
  }
  bool command(const char* line,Print& out,uint32_t now,bool busy=false){
    if(strncmp(line,"course",6)||(line[6]&&line[6]!=' '))return false;
    if(!strcmp(line,"course status")){status(out);return true;}
    if(busy){error_="maintenance_active";status(out,"rejected",false);return true;}
    bool ok=false;const char* action="invalid";error_="invalid_command";
    if(!strncmp(line,"course begin ",13)){
      action="begin";const char* a=line+13;const char* space=strchr(a,' ');uint32_t n=0,crc=0;
      if(space&&decimal(a,space-a,n)&&strlen(space+1)==8&&m5link::hex(space+1,8,crc)){ok=upload_.begin(n,crc,now);error_=upload_.error;}else upload_.abort();
    }else if(!strncmp(line,"course chunk ",13)){
      action="chunk";const char* a=line+13;const char* space=strchr(a,' ');uint32_t offset=0;
      if(space&&decimal(a,space-a,offset)){ok=upload_.chunk(offset,space+1,now);error_=upload_.error;}else upload_.abort();
    }else if(!strcmp(line,"course commit")){
      action="commit";std::unique_ptr<Course> next(new(std::nothrow) Course);
      if(!next){upload_.abort();error_="allocation_failed";}
      else {ok=upload_.finish(*next,now);error_=upload_.error;}
      if(ok){ok=store_.save(*next,active);if(ok){internal_=true;error_="";}else error_="store_failed_readback_unknown";}
    }else if(!strcmp(line,"course abort")){action="abort";upload_.abort();ok=true;error_="";}
    else if(!strcmp(line,"course clear")){action="clear";upload_.abort();ok=store_.clear();if(ok){internal_=false;active=fallback_;error_="";}else error_="clear_failed";}
    status(out,action,ok);return true;
  }
};
}
#endif
