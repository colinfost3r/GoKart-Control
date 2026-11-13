#pragma once
#include "CourseTransfer.h"
#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_system.h>
#include <esp_mac.h>
#include <mbedtls/md.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

namespace m5game { namespace share {
// Course-only trust, separate from every kart's encrypted vehicle-control pairing.
// Radio lifecycle and the single receive callback remain owned by the existing application.
class Radio {
 struct Peer {uint8_t id=0,mac[6]{},key[32]{};};
 struct Pairing {uint8_t magic[4]{'G','C','P','1'};Peer peer[8]{};uint32_t crc=0;};
 struct Packet {uint32_t arrived;uint16_t size;uint8_t peer;uint8_t bytes[MAX_FRAME];};
 Pairing pairing_{};QueueHandle_t queue_=nullptr;uint8_t own_[6]{};bool up_=false,publisher_=false,loaded_=false;
 uint32_t boot_=0,lastTx_=0,lastOffer_=0;unsigned offerPeer_=0;uint8_t ownId_=0;
 static bool unicast(const uint8_t*p){uint8_t v=0;for(int i=0;i<6;++i)v|=p[i];return v&&!(p[0]&1);}
 static bool keyPresent(const uint8_t*p){uint8_t v=0;for(int i=0;i<32;++i)v|=p[i];return v;}
 static bool parseMac(const char*s,uint8_t*out){if(strlen(s)!=17)return false;for(int i=0;i<6;++i){uint32_t n;if(!m5link::hex(s+i*3,2,n)||(i<5&&s[i*3+2]!=':'))return false;out[i]=n;}return unicast(out);}
 bool authenticate(const Peer&p,const uint8_t*data,size_t n,uint8_t*out)const{
  static const uint8_t label[]="GoKart course-only ESP-NOW v1";uint8_t key[32],digest[32];
  const auto* alg=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if(mbedtls_md_hmac(alg,p.key,32,label,sizeof(label)-1,key)||mbedtls_md_hmac(alg,key,32,data,n,digest))return false;
  std::memcpy(out,digest,TAG_BYTES);return true;
 }
 bool send(unsigned peer,const Message&m){if(!up_||peer>=8||!pairing_.peer[peer].id)return false;
  uint8_t frame[MAX_FRAME];size_t n=encode(m,frame);if(!n||!authenticate(pairing_.peer[peer],frame,n,frame+n))return false;
  return esp_now_send(pairing_.peer[peer].mac,frame,n+TAG_BYTES)==ESP_OK;
 }
 void load(){if(loaded_)return;loaded_=true;Preferences prefs;Pairing candidate{};
  if(!prefs.begin("coursepeer",true))return;
  bool ok=prefs.getBytesLength("v1")==sizeof(candidate)&&prefs.getBytes("v1",&candidate,sizeof candidate)==sizeof candidate;prefs.end();
  if(!ok||std::memcmp(candidate.magic,"GCP1",4)||candidate.crc!=crc32(reinterpret_cast<const uint8_t*>(&candidate),offsetof(Pairing,crc)))return;
  for(unsigned i=0;i<8;++i){auto&p=candidate.peer[i];if(p.id&&(p.id!=i+1||!unicast(p.mac)||!keyPresent(p.key)))return;}
  pairing_=candidate;
 }
 void reply(Print&out,const char*action,bool ok){out.printf("{\"t\":\"share\",\"action\":\"%s\",\"ok\":%s,\"received\":%u,\"digest\":\"%08lx\",\"error\":\"%s\"}\n",action,ok?"true":"false",unsigned(server.received()),(unsigned long)server.digest(),server.error);}
 public:
 Publisher server;Receiver client;
 explicit Radio(bool publisher=false):publisher_(publisher){}
 uint32_t boot()const{return boot_;}
 bool ready()const{return up_;}
 // Called only after the existing paired link or legacy inventory service initialized ESP-NOW.
 bool begin(){load();if(up_)return true;bool any=false;for(auto&p:pairing_.peer)if(p.id)any=true;if(!any)return false;
  if(esp_wifi_get_mac(WIFI_IF_STA,own_)!=ESP_OK)return false;
  if(!queue_)queue_=xQueueCreate(8,sizeof(Packet));if(!queue_)return false;
  for(auto&p:pairing_.peer)if(p.id&&(!std::memcmp(p.mac,own_,6)||esp_now_is_peer_exist(p.mac)))return false;
  unsigned added=0;
  for(auto&p:pairing_.peer)if(p.id){esp_now_peer_info_t peer{};std::memcpy(peer.peer_addr,p.mac,6);peer.ifidx=WIFI_IF_STA;peer.channel=0;peer.encrypt=false;
   // Never replace an existing encrypted control peer or change its key.
   if(esp_now_add_peer(&peer)!=ESP_OK){for(unsigned i=0;i<8;++i)if(added&(1u<<i))esp_now_del_peer(pairing_.peer[i].mac);return false;}
   added|=1u<<(p.id-1);
  }
  boot_=esp_random();if(!boot_)boot_=1;up_=true;return true;
 }
 // Returns true for this protocol, even when unconfigured: it never reaches another parser.
 bool receive(const esp_now_recv_info_t*info,const uint8_t*data,int n){
  if(!data||n<4||std::memcmp(data,"GCS1",4))return false;
  if(!up_||!info||!info->src_addr||!info->des_addr||std::memcmp(info->des_addr,own_,6)||n<int(HEADER_BYTES+TAG_BYTES)||n>int(MAX_FRAME))return true;
  for(unsigned i=0;i<8;++i)if(pairing_.peer[i].id&&!std::memcmp(pairing_.peer[i].mac,info->src_addr,6)){
   Packet p{};p.arrived=millis();p.size=n;p.peer=i;std::memcpy(p.bytes,data,size_t(n));xQueueSend(queue_,&p,0);break;
  }return true;
 }
 void poll(uint8_t ownId,bool hosting,bool mayTransmit,uint32_t now){
  ownId_=ownId;if(!up_)return;Packet p;unsigned budget=4;
  while(budget--&&xQueueReceive(queue_,&p,0)==pdTRUE){
   now=millis();if(uint32_t(now-p.arrived)>250)continue;uint8_t tag[TAG_BYTES];size_t n=p.size-TAG_BYTES;
   if(!authenticate(pairing_.peer[p.peer],p.bytes,n,tag))continue;uint8_t different=0;for(unsigned i=0;i<TAG_BYTES;++i)different|=tag[i]^p.bytes[n+i];if(different)continue;
   Message m;if(!decode(p.bytes,n,m))continue;
   if(publisher_){Message response;if(mayTransmit&&uint32_t(now-lastTx_)>=20&&server.answer(m,ownId,boot_,hosting,response)){send(p.peer,response);lastTx_=now;}}
   else if(m.host==pairing_.peer[p.peer].id&&m.host!=ownId)client.receive(m,now);
  }
  now=millis();if(!mayTransmit||uint32_t(now-lastTx_)<40)return;
  if(publisher_){if(uint32_t(now-lastOffer_)<125)return;lastOffer_=now;
   for(unsigned i=0;i<8;++i){unsigned index=offerPeer_++%8;if(pairing_.peer[index].id){Message offer;if(server.offer(ownId,boot_,hosting,offer)){send(index,offer);lastTx_=now;}break;}}
  }else{Message request;if(client.next(now,request)&&request.host>=1&&request.host<=8&&pairing_.peer[request.host-1].id){send(request.host-1,request);lastTx_=now;}}
 }
 bool command(const char*line,Print&out,uint8_t ownId,uint32_t now){
  if(std::strncmp(line,"share ",6))return false;load();
  if(!std::strcmp(line,"share status")){uint8_t mac[6];esp_read_mac(mac,ESP_MAC_WIFI_STA);uint8_t channel=0;wifi_second_chan_t second;esp_wifi_get_channel(&channel,&second);out.printf("{\"t\":\"share_radio\",\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"channel\":%u}\n",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5],channel);out.printf("{\"t\":\"share\",\"action\":\"status\",\"ready\":%s,\"publisher\":%s,\"bytes\":%u,\"host\":%u,\"progress\":%u,\"configured\":[",up_?"true":"false",publisher_?"true":"false",unsigned(server.package().size()),client.host(),client.progress());bool comma=false;for(auto&p:pairing_.peer)if(p.id){out.printf("%s%u",comma?",":"",p.id);comma=true;}out.println("]}");return true;}
  if(!std::strncmp(line,"share pair ",11)){
   unsigned id;char mac[18]{},key[65]{},tail;bool ok=sscanf(line+11,"%u %17s %64s %c",&id,mac,key,&tail)==3&&id>=1&&id<=8&&strlen(key)==64;
   Pairing next=pairing_;Preferences prior;if(prior.begin("coursepeer",true)){Pairing saved{};if(prior.getBytesLength("v1")==sizeof saved&&prior.getBytes("v1",&saved,sizeof saved)==sizeof saved&&saved.crc==crc32(reinterpret_cast<const uint8_t*>(&saved),offsetof(Pairing,crc)))next=saved;prior.end();}Peer p{};if(ok){p.id=id;ok=parseMac(mac,p.mac);for(unsigned i=0;ok&&i<32;++i){uint32_t value;ok=m5link::hex(key+i*2,2,value);p.key[i]=value;}ok=ok&&keyPresent(p.key);}
   if(ok){for(auto&q:next.peer)if(q.id&&q.id!=id&&!std::memcmp(q.mac,p.mac,6))ok=false;}
   if(ok){next.peer[id-1]=p;next.crc=crc32(reinterpret_cast<const uint8_t*>(&next),offsetof(Pairing,crc));Preferences prefs;ok=prefs.begin("coursepeer",false);if(ok){ok=prefs.putBytes("v1",&next,sizeof next)==sizeof next;Pairing check{};ok=ok&&prefs.getBytes("v1",&check,sizeof check)==sizeof check&&!std::memcmp(&next,&check,sizeof next);prefs.end();}}
   out.printf("{\"t\":\"share\",\"action\":\"pair\",\"ok\":%s,\"restart_required\":true}\n",ok?"true":"false");return true;
  }
  if(!publisher_){out.println("{\"t\":\"share\",\"ok\":false,\"error\":\"publisher_only\"}");return true;}
  bool ok=false;const char* action="invalid";
  if(!std::strncmp(line,"share begin ",12)){unsigned size;char hash[9]{},tail;uint32_t crc;action="begin";if(sscanf(line+12,"%u %8s %c",&size,hash,&tail)==2&&strlen(hash)==8&&m5link::hex(hash,8,crc))ok=server.begin(size,crc,now);}
  else if(!std::strncmp(line,"share chunk ",12)){unsigned offset;char hex[129]{},tail;action="chunk";if(sscanf(line+12,"%u %128s %c",&offset,hex,&tail)==2)ok=server.chunk(offset,hex,now);}
  else if(!std::strcmp(line,"share commit")){action="commit";ok=server.commit(ownId,now);}
  else if(!std::strcmp(line,"share clear")){action="clear";server.clear();ok=true;}
  reply(out,action,ok);return true;
 }
};
}}
