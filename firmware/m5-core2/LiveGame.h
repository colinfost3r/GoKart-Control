#pragma once
#include "DisplayState.h"
#include "PlayerPreview.h"
#include <GamePackage.h>
#include <GameRequest.h>
#include <CourseTransfer.h>
#include <memory>

namespace m5dash {
class LiveGame {
 public:
 enum class Item:uint8_t{None=0,Boost=1,Rocket=2,Shell=3,Lightning=4,Mud=5,Triple=6,Star=7,Magnet=8,Shield=10};
 enum class Stage{Idle,Downloading,Joining,Playing,Error};
 Stage stage=Stage::Idle;bool overlay=false,acknowledged=false;const char* note="Move near host to download";
 uint32_t courseBoot=0;
 m5game::Package package;Course course;uint32_t pending=0,pendingMs=0;int result=0;unsigned laps=0;uint32_t lastLapMs=0,bestLapMs=0;
 private:
 struct Held{Item item=Item::None;uint8_t charges=1;};Held inventory_[3]{};unsigned inventoryCount_=0;Item attack_=Item::None;
 bool inside_[m5game::MAX_ZONES]{},fired_[m5game::MAX_ZONES]{};uint32_t firedMs_[m5game::MAX_ZONES]{};
 uint32_t ownerBoot_=0,intentBoot_=0,lastFix_=0,magnetUntil_=0,lapAt_=0;
 bool priorFix_=false,lapStarted_=false; m5game::Point prior_{};m5game::Action pendingAction_=m5game::Action::Leave;
 static bool future(uint32_t until,uint32_t now){return int32_t(until-now)>0;}
 static double signedDistance(const m5game::Zone&z,m5game::Point p){
  if(!z.shape)return m5game::distance(z.center,p)-z.radiusCm/100.0;
  bool in=false;double closest=1e20;
  for(unsigned i=0,j=z.count-1;i<z.count;j=i++){
   auto a=z.points[i],b=z.points[j];double ay=(a.lat-p.lat)*111320,by=(b.lat-p.lat)*111320;
   double co=std::cos(p.lat*.0174532925199433),ax=(a.lon-p.lon)*111320*co,bx=(b.lon-p.lon)*111320*co;
   if((ay>0)!=(by>0)&&0<(bx-ax)*(-ay)/(by-ay)+ax)in=!in;
   double dx=bx-ax,dy=by-ay,den=dx*dx+dy*dy,t=den?std::max(0.0,std::min(1.0,-(ax*dx+ay*dy)/den)):0;
   closest=std::min(closest,std::hypot(ax+t*dx,ay+t*dy));
  }return in?-closest:closest;
 }
 void clearItems(){inventoryCount_=0;attack_=Item::None;magnetUntil_=0;priorFix_=lapStarted_=false;lastFix_=0;}
 void beginPlay(){std::memset(inside_,0,sizeof inside_);std::memset(fired_,0,sizeof fired_);clearItems();laps=0;lastLapMs=bestLapMs=0;stage=Stage::Playing;overlay=false;note="Joined";}
 static double cross(m5game::Point a,m5game::Point b,m5game::Point c){return (b.lon-a.lon)*(c.lat-a.lat)-(b.lat-a.lat)*(c.lon-a.lon);}
 void lap(m5game::Point p,uint32_t now){
  if(package.hasLap()&&priorFix_){auto a=package.lapA(),b=package.lapB();double c1=cross(a,b,prior_),c2=cross(a,b,p),c3=cross(prior_,p,a),c4=cross(prior_,p,b);
   bool crosses=c1*c2<0&&c3*c4<=0;
   if(crosses&&(!lapStarted_||uint32_t(now-lapAt_)>=package.minLapMs())){if(lapStarted_){lastLapMs=now-lapAt_;++laps;if(!bestLapMs||lastLapMs<bestLapMs)bestLapMs=lastLapMs;}lapStarted_=true;lapAt_=now;}
  }prior_=p;priorFix_=true;
 }
 public:
 bool active()const{return stage==Stage::Playing;}
 bool busy()const{return pending||stage==Stage::Downloading||stage==Stage::Joining;}
 static const char* name(Item i){switch(i){case Item::Boost:return "BOOST";case Item::Rocket:return "ROCKET";case Item::Shell:return "SHELL";case Item::Lightning:return "BOLT";case Item::Triple:return "BOOST3";case Item::Star:return "STAR";case Item::Magnet:return "MAGNET";case Item::Shield:return "SHIELD";case Item::Mud:return "MUD";default:return "--";}}
 Item item()const{return attack_!=Item::None?attack_:inventoryCount_?inventory_[0].item:Item::None;}
 unsigned charges()const{return attack_!=Item::None?1:inventoryCount_?inventory_[0].charges:0;}
 bool available(const State&s,const m5game::share::Receiver&r,uint32_t now)const{return active()||busy()||(s.live(now)&&s.metadataFresh(now)&&s.gameVersion==1&&(s.hosts||r.available(now)));}
 bool notify(const State&s,const m5game::share::Receiver&r,uint32_t now)const{return !active()&&!acknowledged&&available(s,r,now)&&((now/500)%2==0);}
 bool generation(const State&s)const{return package.valid()&&(s.courseHosts&(1u<<(package.host()-1)))&&s.hostCourse[package.host()]==package.digest()&&courseBoot&&s.hostBoot[package.host()]==courseBoot;}
 bool controlReady(const State&s,uint32_t now)const{return !pending&&!s.pending&&s.live(now)&&s.metadataFresh(now)&&s.gameVersion==1&&s.gameReady&&s.token&&s.karts[s.self].vesc&&!s.karts[s.self].stopped&&s.gameSession==package.host()&&generation(s);}
 uint8_t target(const State&s,uint32_t now)const{if(!s.live(now)||!s.karts[s.self].positionFresh(now))return 0;auto&k=s.karts[s.self];double best=25.000001;uint8_t id=0;for(unsigned i=1;i<=8;++i){auto&p=s.karts[i];if(i==s.self||p.session!=package.host()||!p.positionFresh(now))continue;double d=m5game::distance({k.lat,k.lon},{p.lat,p.lon});if(d<best){best=d;id=i;}}return id;}
 bool hasPeer(const State&s,uint32_t now)const{for(unsigned i=1;i<=8;++i)if(i!=s.self&&s.karts[i].session==package.host()&&s.karts[i].online(now))return true;return false;}
 bool canFire(const State&s,uint32_t now)const{return active()&&!overlay&&item()!=Item::None&&controlReady(s,now)&&(item()!=Item::Shell||target(s,now))&&(item()!=Item::Lightning||hasPeer(s,now))&&(!(item()==Item::Boost||item()==Item::Rocket||item()==Item::Triple||item()==Item::Star)||!s.karts[s.self].slow);}
 bool load(const uint8_t*data,size_t n){if(!package.load(data,n))return false;course.count=package.tracks();course.closed=package.closed();package.name(course.name,sizeof course.name);for(size_t i=0;i<course.count;++i){auto p=package.track(i);course.lat[i]=p.lat;course.lon[i]=p.lon;}return true;}
 void opening(){overlay=true;acknowledged=true;}
 void downloadStarted(const State&s){stage=Stage::Downloading;ownerBoot_=intentBoot_=s.boot;clearItems();note="Downloading host course";}
 bool intentValid(const State&s,uint32_t now)const{return intentBoot_&&s.boot==intentBoot_&&s.live(now)&&s.metadataFresh(now)&&s.gameVersion==1;}
 void fail(const char*why){stage=Stage::Error;pending=0;clearItems();note=why;overlay=true;}
 template<class Send> bool request(m5game::Action action,uint16_t arg,State&s,uint32_t id,uint32_t now,Send send){
  uint8_t host=package.host();if(pending||s.pending||!s.token||!id||!s.live(now)||!s.metadataFresh(now)||s.gameVersion!=1||!host)return false;
  if(action!=m5game::Action::Leave&&(!s.gameReady||!s.karts[s.self].vesc||s.karts[s.self].stopped))return false;
  if(action==m5game::Action::Join&&(!(s.hosts&(1u<<(host-1)))||host==s.self))return false;
  if(action!=m5game::Action::Join&&s.gameSession!=host)return false;
  if(action!=m5game::Action::Leave&&!generation(s))return false;
  char line[62];size_t n=m5game::encode(line,sizeof line,{s.token,id,host,action,arg,package.digest(),courseBoot});if(!n||!send(line,now))return false;
  s.token=0;pending=id;pendingMs=now;pendingAction_=action;ownerBoot_=s.boot;result=1;note="Request sent";return true;
 }
 void tick(State&s,uint32_t now){
  if((ownerBoot_&&s.boot!=ownerBoot_)||!s.live(now)||!s.metadataFresh(now)){
   if(pending||active()||stage==Stage::Joining||stage==Stage::Downloading){pending=0;stage=Stage::Error;clearItems();note="Link lost; no retry";}return;
  }
  if(pending&&s.gameRequest==pending&&s.gameResult>=2){result=s.gameResult;pending=0;
   if(pendingAction_==m5game::Action::Join){if(result==2&&s.gameSession==package.host())beginPlay();else fail("Join not confirmed");}
   else if(pendingAction_==m5game::Action::Leave){clearItems();stage=Stage::Idle;overlay=false;note=result==2?"Left game":"Leave not confirmed";}
   else note=result==2?"Applied":result==4?"Refused":"Outcome unknown";
  }
  if(pending&&uint32_t(now-pendingMs)>3000){pending=0;result=5;note="Outcome unknown; no retry";if(stage==Stage::Joining)fail(note);}
  if(active()&&!generation(s)){fail("Host course changed or lost");return;}
  if(active()&&s.gameSession!=package.host()){clearItems();stage=Stage::Idle;note="Session ended";}
 }
 static Item roll(uint32_t random){unsigned n=random%100;const uint8_t weights[]={22,24,12,8,6,6,8,6,8};const Item items[]={Item::Boost,Item::Shell,Item::Lightning,Item::Rocket,Item::Triple,Item::Star,Item::Shield,Item::Magnet,Item::None};for(unsigned i=0;i<9;++i){if(n<weights[i])return items[i];n-=weights[i];}return Item::None;}
 void collect(Item i){if(i==Item::None){note="Empty box";return;}if(i==Item::Shell||i==Item::Lightning){attack_=i;note="Item collected";return;}if(inventoryCount_<3){inventory_[inventoryCount_++]={i,uint8_t(i==Item::Triple?3:1)};note="Item collected";}else note="Inventory full";}
 template<class Send> bool fire(State&s,uint32_t id,uint32_t now,Send send){
  if(!canFire(s,now))return false;Item i=item();bool ok=false;
  if(i==Item::Magnet){magnetUntil_=now+20000;ok=true;note="Magnet active";}
  else if(i==Item::Shell)ok=request(m5game::Action::Shell,target(s,now),s,id,now,send);
  else if(i==Item::Lightning)ok=request(m5game::Action::Lightning,0,s,id,now,send);
  else if(i==Item::Shield)ok=request(m5game::Action::Shield,0,s,id,now,send);
  else if(i==Item::Star)ok=request(m5game::Action::Star,0,s,id,now,send);
  else {unsigned secs=i==Item::Rocket?10:7,scale=i==Item::Rocket?100:75;
   ok=request(m5game::Action::Boost,uint16_t(secs<<8|scale),s,id,now,send);
  }
  if(ok){if(attack_!=Item::None)attack_=Item::None;else if(--inventory_[0].charges==0){for(unsigned j=1;j<inventoryCount_;++j)inventory_[j-1]=inventory_[j];--inventoryCount_;}}
  return ok;
 }
 template<class Send,class Random> void position(State&s,uint32_t id,uint32_t now,Send send,Random random){
  if(!active()||!package.enabled()||!s.live(now))return;auto&k=s.karts[s.self];
  if(!k.positionFresh(now)||k.stopped||!s.gameReady){priorFix_=false;return;}
  if(lastFix_==k.fixReceived)return;lastFix_=k.fixReceived;m5game::Point p{k.lat,k.lon};lap(p,now);
  bool mud=false;int effect=-1;
  for(size_t j=0;j<package.zones();++j){auto z=package.zone(j);double d=signedDistance(z,p);if(z.type==m5game::ZoneType::Item&&future(magnetUntil_,now)&&!z.shape)d-=z.radiusCm/100.0;
   bool entered=!inside_[j]&&d<=0;if(d>3)inside_[j]=false;else if(d<=0)inside_[j]=true;
   if(z.type==m5game::ZoneType::Mud&&inside_[j]){mud=true;if((!fired_[j]||uint32_t(now-firedMs_[j])>=2000)&&controlReady(s,now))effect=int(j);continue;}
   if(!entered||(fired_[j]&&uint32_t(now-firedMs_[j])<uint32_t(z.cooldownS)*1000))continue;
   fired_[j]=true;firedMs_[j]=now;
   if(z.type==m5game::ZoneType::Item)collect(roll(random()));else if(effect<0)effect=int(j);
  }
  if(effect>=0&&controlReady(s,now)){auto z=package.zone(size_t(effect));if(mud&&z.type!=m5game::ZoneType::Mud)return;
   bool sent=request(z.type==m5game::ZoneType::Mud?m5game::Action::Mud:m5game::Action::Boost,z.type==m5game::ZoneType::Mud?z.secs:uint16_t(z.secs<<8|z.scale),s,id,now,send);
   if(sent){fired_[effect]=true;firedMs_[effect]=now;}
  }
 }
};
}
