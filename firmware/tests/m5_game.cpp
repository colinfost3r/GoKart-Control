#include "LiveGame.h"
#include "GameStorage.h"
#include "CourseGeneration.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <map>
#include <vector>
using namespace m5game;
struct Memory {std::map<std::string,std::vector<uint8_t>> data;bool fail=false,corrupt=false;
 size_t read(const char*k,uint8_t*out,size_t cap){auto&v=data[k];if(v.size()>cap)return 0;memcpy(out,v.data(),v.size());if(corrupt&&v.size()>20)out[10]^=1;return v.size();}
 bool write(const char*k,const uint8_t*p,size_t n){if(fail)return false;data[k]={p,p+n};return true;}
};
int main(int argc,char**argv){
 assert(argc==2);std::ifstream file(argv[1],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)),{});Package pkg;assert(pkg.load(bytes.data(),bytes.size())&&pkg.hasLap());
 share::Publisher host;assert(host.begin(bytes.size(),pkg.digest(),100));
 for(size_t off=0;off<bytes.size();off+=64){char hex[129];size_t n=std::min(size_t(64),bytes.size()-off);for(size_t i=0;i<n;++i)snprintf(hex+i*2,3,"%02x",bytes[off+i]);assert(host.chunk(off,hex,200));}
 assert(host.commit(2,300));share::Message offer;assert(host.offer(2,222,true,offer));share::Receiver rx;rx.receive(offer,400);assert(rx.begin(111,333,400));
 share::Message request,response;assert(rx.next(400,request));assert(!rx.next(500,request));assert(rx.next(901,request));assert(host.answer(request,2,222,true,response));
 auto wrong=response;wrong.nonceA++;assert(!rx.receive(wrong,902));assert(rx.receive(response,902));uint32_t now=1000;
 while(rx.busy()){assert(rx.next(now,request));assert(host.answer(request,2,222,true,response));uint8_t frame[share::MAX_FRAME];auto n=share::encode(response,frame);share::Message decoded;assert(share::decode(frame,n,decoded));assert(rx.receive(decoded,now+1));assert(!rx.receive(decoded,now+2));now+=100;}
 assert(rx.stage==share::Receiver::Stage::Complete&&rx.size()==bytes.size()&&rx.progress()==100);
 m5dash::GameStorage<Memory> store;assert(store.save(rx.data(),rx.size()));Package cached;assert(store.load(cached)&&cached.digest()==pkg.digest());
 auto broken=bytes;broken.back()^=1;assert(!store.save(broken.data(),broken.size()));assert(store.load(cached)&&cached.digest()==pkg.digest());
 store.backend.fail=true;assert(!store.save(bytes.data(),bytes.size()));store.backend.fail=false;assert(store.load(cached));
 store.backend.corrupt=true;assert(!store.save(bytes.data(),bytes.size()));store.backend.corrupt=false;assert(store.load(cached));
 // Bad upload cannot destroy the host's last committed course.
 assert(host.begin(bytes.size(),1,now));assert(!host.commit(2,now));assert(host.package().digest()==pkg.digest());
 // Fresh nonce is required each transfer; old response is never a completed download.
 rx.accepted();assert(rx.begin(444,555,now));assert(!rx.receive(response,now));rx.next(now,request);rx.next(now+500,request);rx.next(now+1000,request);rx.next(now+1500,request);assert(!rx.next(now+2000,request)&&rx.stage==share::Receiver::Stage::Error);
 m5dash::State s;m5dash::LiveGame game;assert(game.load(bytes.data(),bytes.size()));game.courseBoot=222;
 auto ready=[&](uint32_t t){s.self=3;s.boot=10;s.metaSeen=true;s.metaMs=t;s.karts[3].seen=true;s.karts[3].received=t;s.karts[3].vesc=true;s.gameVersion=1;s.gameReady=true;s.token=77;s.hosts=s.courseHosts=2;s.hostCourse[2]=pkg.digest();s.hostBoot[2]=222;};
 std::vector<Request> sent;auto send=[&](const char*line,uint32_t){std::string text=line;text.pop_back();Request decoded;assert(decode(text.c_str(),decoded));sent.push_back(decoded);return true;};
 ready(5000);game.downloadStarted(s);game.stage=m5dash::LiveGame::Stage::Joining;assert(game.request(Action::Join,0,s,1,5000,send));assert(!game.request(Action::Join,0,s,2,5001,send));
 ready(5100);s.gameRequest=1;s.gameResult=2;s.gameSession=2;game.tick(s,5100);assert(game.active());
 // Actual GPS item-box entry rolls a shell; nearest same-session peer is the target.
 auto&own=s.karts[3];own.fix=own.hasPosition=true;own.lat=41;own.lon=-73;own.fixReceived=5100;
 auto&peer=s.karts[2];peer=own;peer.session=2;peer.received=peer.fixReceived=5100;
 game.position(s,2,5100,send,[](){return 25;});assert(game.item()==m5dash::LiveGame::Item::Shell&&game.canFire(s,5100));
 assert(game.fire(s,3,5100,send));assert(sent.back().action==Action::Shell&&sent.back().arg==2);assert(!game.fire(s,4,5101,send));
 ready(5200);s.gameRequest=3;s.gameResult=2;game.tick(s,5200);assert(game.item()==m5dash::LiveGame::Item::None);
 // Refused/unknown boost cannot add time to another fresh press.
 game.collect(m5dash::LiveGame::Item::Boost);assert(game.fire(s,4,5200,send));assert(sent.back().arg==(7<<8|75));
 ready(5300);s.gameRequest=4;s.gameResult=4;game.tick(s,5300);game.collect(m5dash::LiveGame::Item::Boost);assert(game.fire(s,5,5300,send));assert(sent.back().arg==(7<<8|75));
 // A lost link destroys pending intent/inventory and never sends on recovery.
 auto count=sent.size();game.tick(s,9000);assert(!game.active()&&!game.pending);ready(9100);game.tick(s,9100);assert(sent.size()==count);
 s.boot=11;game.downloadStarted(s);game.tick(s,9100);assert(game.stage==m5dash::LiveGame::Stage::Downloading);
 game.stage=m5dash::LiveGame::Stage::Playing;s.hostCourse[2]++;game.tick(s,9100);assert(!game.active()&&game.item()==m5dash::LiveGame::Item::None);
 Generation gen;assert(gen.accept(100,5,10,1000));assert(!gen.accept(100,4,9,1100));assert(!gen.accept(100,5,10,1200));assert(gen.accept(100,6,11,1300));assert(gen.accept(200,7,1,1400));assert(!gen.accept(100,6,12,1500));assert(!gen.fresh(8000));
 std::cout<<"Host export -> transfer/retry -> validated cache -> JOIN -> GPS pickup -> FIRE -> generation/loss guards passed\n";
}
