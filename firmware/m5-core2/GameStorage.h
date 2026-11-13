#pragma once
#include <GamePackage.h>
#include <memory>
#include <new>
namespace m5dash {
// Two slots plus an atomic NVS selector. Commit only after exact blob readback.
// A cached package is display data; loading it never joins or restores inventory.
template<class Backend> class GameStorage {
 public:
 Backend backend;
 bool load(m5game::Package& package){uint8_t selected=0;if(backend.read("selected",&selected,1)!=1||selected>1)return false;return read(selected,package);}
 bool save(const uint8_t*data,size_t size){
  if(!m5game::Package::validate(data,size))return false;
  uint8_t selected=0;if(backend.read("selected",&selected,1)!=1||selected>1)selected=0;
  uint8_t next=selected^1;const char*key=next?"slot1":"slot0";
  if(!backend.write(key,data,size))return false;
  std::unique_ptr<m5game::Package> check(new(std::nothrow)m5game::Package);
  if(!check||!read(next,*check)||check->size()!=size||memcmp(check->data(),data,size))return false;
  return backend.write("selected",&next,1);
 }
 private:
 bool read(uint8_t slot,m5game::Package&package){
  std::unique_ptr<uint8_t[]> bytes(new(std::nothrow)uint8_t[m5game::MAX_PACKAGE]);if(!bytes)return false;
  size_t n=backend.read(slot?"slot1":"slot0",bytes.get(),m5game::MAX_PACKAGE);return package.load(bytes.get(),n);
 }
};
}
#ifdef ARDUINO
#include <Preferences.h>
namespace m5dash {
struct GameNvs {
 size_t read(const char*key,uint8_t*out,size_t cap){Preferences p;if(!p.begin("m5game",true))return 0;size_t n=p.getBytesLength(key);if(!n||n>cap)n=0;else if(p.getBytes(key,out,n)!=n)n=0;p.end();return n;}
 bool write(const char*key,const uint8_t*data,size_t n){Preferences p;if(!p.begin("m5game",false))return false;bool ok=p.putBytes(key,data,n)==n;p.end();return ok;}
};
}
#endif
