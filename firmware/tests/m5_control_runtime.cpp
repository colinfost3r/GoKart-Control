// Actual .ino functions are injected by test_m5_control_runtime.py. This file supplies only
// hardware adapters and scenarios; command/write logic is never copied into this fixture.
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#include <strings.h>
#include "GoKartProtocol.h"
#include "VescLink.h"
#include "M5DisplayLink.h"
#include "GameRequest.h"
#include "GamePackage.h"
#include "CourseGeneration.h"
#include "VerifiedBaseline.h"
#include "config.h"
#include "cmd_types.h"
using std::isfinite;
static uint32_t nowMs=1000;
uint32_t millis(){return nowMs;}
static uint64_t utcNowMs(){return 0;}
static uint32_t gpsUnix(){return 0;}
struct Text:std::string {
  using std::string::string;using std::string::operator=;
  bool equalsIgnoreCase(const char* other)const{return !strcasecmp(c_str(),other);}
};
struct Console {
  std::vector<std::string> lines;
  void print(const char*s){lines.emplace_back(s);}
  int printf(const char* fmt,...){char b[600];va_list args;va_start(args,fmt);
    int n=vsnprintf(b,sizeof b,fmt,args);va_end(args);lines.emplace_back(b);return n;}
} Serial;
static void logf(const char*,...){}
struct Storage {
  std::map<std::string,std::vector<uint8_t>> blobs;
  unsigned writes=0;
  size_t getBytesLength(const char* key){return blobs[key].size();}
  size_t getBytes(const char* key,void* out,size_t n){auto& b=blobs[key];if(b.size()!=n)return 0;memcpy(out,b.data(),n);return n;}
  size_t putBytes(const char* key,const void* data,size_t n){const auto* p=static_cast<const uint8_t*>(data);blobs[key]={p,p+n};++writes;return n;}
  size_t putUChar(const char*,uint8_t){++writes;return 1;}
} prefs;
struct Controller {
  VescActiveLimits live;
  VescValues sample;
  uint32_t fwSeenMs=0,ack=0;
  uint8_t fwMajor=6,fwMinor=2;
  char uuidHex[25]{},hwName[24]="HOST_FIXTURE";
  std::vector<VescTempLimits> writes;
  std::vector<std::vector<uint8_t>> custom;
  unsigned configReads=0,firmwareReads=0,valueReads=0;
  const VescActiveLimits& limits()const{return live;}
  const VescValues& values()const{return sample;}
  bool linkUp(uint32_t age)const{return sample.receivedMs && uint32_t(millis()-sample.receivedMs)<age;}
  uint32_t lastAckMs()const{return ack;}
  void sendTempLimits(const VescTempLimits& limits){writes.push_back(limits);}
  void sendCustomAppData(const uint8_t* p,size_t n){custom.emplace_back(p,p+n);}
  void requestMotorConfig(){++configReads;}
  void requestFirmware(){++firmwareReads;}
  void requestValues(){++valueReads;}
  bool poll(){return false;}
  void markLinkLost(){live.receivedMs=sample.receivedMs=fwSeenMs=0;uuidHex[0]=0;}
} vesc;
#include "production_state.inc"
static constexpr const char* UUID="00112233445566778899aabb";
static uint8_t kartId=3,reportRate=2;
static Text vescUuid=UUID;
static bool vescIdentityBad=false,vescLinkWas=true,otaInProgress=false;
static uint32_t vescLinkUpMs=900,vescIdCheckedMs=0,vescMcconfMs=900,vescPollMs=900;
static bool bleConnected=true,reconnectOnService=false;
static void bleService(){if(reconnectOnService){bleConnected=true;reconnectOnService=false;}}
struct Address {std::string toString()const{return "02:11:22:33:44:55";}} bleTarget;
static Text bleRejectMac;
struct Client {void disconnect(){bleConnected=false;}} client;
static Client* pClient=&client;
static m5link::Gate m5Gate;
static uint32_t m5Request=0;
static CmdRef m5Owner=NO_OWNER;
static uint8_t m5Result=GK_RES_NONE;
static uint32_t m5GameRequest=0,m5JoinedCourse=0,m5JoinedBoot=0;static uint8_t m5GameResult=0,m5Shield=0;static CmdRef m5GameOwner=NO_OWNER;
static uint32_t m5StarUntil=0;static m5game::Generation courseGeneration[9];
static uint8_t gameSession=0,gameScore=0,atkTo=0,atkItem=0,atkSeq=0,atkAckMask=0;static uint32_t atkStartMs=0;
static bool gameLineDirty=false,radioOk=true;static const char*gameEnded=nullptr;
static GkTelemetry fleet[9]{};static uint32_t fleetMs[9]{};
#define GAME_PEER_MAX_AGE_MS 10000
#define GAME_SLOW_MPH 5
#define GAME_LIGHTNING_SECS 3
#define GAME_SHELL_SECS 4
#define GAME_SRC 0xFD
struct CourseRadio {struct Publisher {void clear(){}}server;} courseRadio;
static void attackEnd(const char*,const char*){atkTo=0;}
static void emitAttack(uint8_t,uint8_t,uint8_t,const char*,const char*,uint8_t){}
static void fillTelemetry(GkTelemetry&t,bool){t={};t.flags=GK_FLAG_GPS_FIX;t.lat_e7=410000000;t.lon_e7=-730000000;t.gps_age_s=0;}
#include "production_control.inc"

static void setup(){
  vesc.live.currentMax=120;vesc.live.currentMin=0;
  vesc.live.inCurrentMax=90;vesc.live.inCurrentMin=-90;
  vesc.live.currentMaxScale=1;vesc.live.currentMinScale=1;
  vesc.live.minErpm=-60000;vesc.live.maxErpm=60000;
  vesc.live.minDuty=.005f;vesc.live.maxDuty=.95f;
  vesc.live.wattMin=-30000;vesc.live.wattMax=30000;
  vesc.live.motorPoles=20;vesc.live.gearRatio=2.7692308f;vesc.live.wheelDiameter=.406f;
  vesc.live.signature=VESC_MCCONF_SIGNATURE_6_00;vesc.live.receivedMs=950;
  vesc.sample.receivedMs=950;vesc.fwSeenMs=950;strcpy(vesc.uuidHex,UUID);
  origLimits=vesc.live;origValid=true;speedCal=1;
}
static void advance(uint32_t ms){nowMs+=ms;vesc.sample.receivedMs=nowMs;}
static void refresh(){vesc.live.receivedMs=vesc.sample.receivedMs=nowMs;}
static uint8_t result(int slot=0){const auto* e=lastCmd(slot);assert(e);return e->result;}
static void command(uint8_t code,uint8_t arg,uint8_t seq=1,uint8_t src=GK_ADDR_BASE){handleCommand(src,seq,code,arg,0,0);}
static void completeWrite(){
  assert(wState==W_SENT && !vesc.writes.empty());auto sent=vesc.writes.back();
  advance(1);vesc.ack=nowMs;serviceWrites();assert(wState==W_VERIFY);
  advance(1);vesc.live.currentMaxScale=sent.currentMaxScale;vesc.live.maxErpm=sent.maxErpm;
  vesc.live.minErpm=sent.minErpm;vesc.live.currentMinScale=sent.currentMinScale;
  vesc.live.minDuty=sent.minDuty;vesc.live.maxDuty=sent.maxDuty;
  vesc.live.wattMin=sent.wattMin;vesc.live.wattMax=sent.wattMax;refresh();
  serviceWrites();assert(wState==W_IDLE);
}
static std::string drivingState(){
  std::ostringstream s;s<<unsigned(modeReq)<<':'<<stopActive<<':'<<preStopScale<<':'
    <<slowActive<<':'<<slowErpm<<':'<<unsigned(slowMph)<<':'<<slowTimed<<':'<<slowUntilMs<<':'
    <<slowPrevActive<<':'<<slowPrevErpm<<':'<<unsigned(slowPrevMph)<<':'
    <<ovActive<<':'<<ovScale<<':'<<ovUntilMs<<':'<<raceHold<<':'<<raceGoMs<<':'<<raceGoUnix<<':'
    <<modeConfirmed<<':'<<wState<<':'<<rampIdx<<':'<<rampNextMs<<':'<<stopRampCeiling<<':'<<wroteThisBoot;
  return s.str();
}
static void testGuard(const std::string& reason){
  // Keep the stale sample in the current session; this isolates age from identity/session guards.
  if(reason=="stale"){advance(3000);vesc.live.receivedMs=nowMs-VESC_WRITE_CONFIG_AGE_MS-1;}
  else if(reason=="old-config")vesc.live.receivedMs=vescLinkUpMs-1;
  else if(reason=="no-pin")vescUuid="";
  else if(reason=="old-identity")vesc.fwSeenMs=vescLinkUpMs-1;
  else if(reason=="wrong-identity")vesc.uuidHex[0]='f';
  else if(reason=="suspect")baselineSuspect=true;
  else if(reason=="nan")vesc.live.wattMax=std::numeric_limits<float>::quiet_NaN();
  else if(reason=="invalid-poles")vesc.live.motorPoles=19;
  else if(reason=="changed-drivetrain")vesc.live.gearRatio=3.0f;
  else if(reason=="no-link")vesc.sample.receivedMs=0;
  else assert(false);
  const auto before=drivingState();
  const uint8_t commands[]={GK_CMD_SET_MODE,GK_CMD_STOP,GK_CMD_START,GK_CMD_BOOST,GK_CMD_SLOW,GK_CMD_RACE};
  uint8_t seq=1;for(uint8_t cmd:commands){command(cmd,cmd==GK_CMD_SET_MODE?1:5,seq++);
    assert(drivingState()==before && result()==GK_RES_NO_VESC);}
  command(GK_CMD_RACE,0,seq++);assert(drivingState()==before);
  assert(!startWrite(.5f,NO_OWNER));requestBrake();
  assert(vesc.writes.empty()&&vesc.custom.empty()&&!m5ModeReady());
}
static void testPassthrough(){
  // A previous mode's active cap must not become the saved ceiling; unchanged fields are live.
  vesc.live.maxErpm=9000;vesc.live.minErpm=-9000;
  vesc.live.currentMinScale=.6f;vesc.live.minDuty=.02f;vesc.live.maxDuty=.88f;
  vesc.live.wattMin=-12345;vesc.live.wattMax=23456;refresh();
  command(GK_CMD_SET_MODE,2);assert(vesc.writes.size()==1);
  const auto& sent=vesc.writes.back();
  assert(sent.currentMaxScale==1 && sent.maxErpm==60000 && sent.minErpm==-60000);
  assert(sent.currentMinScale==.6f && sent.minDuty==.02f && sent.maxDuty==.88f);
  assert(sent.wattMin==-12345 && sent.wattMax==23456 && !sent.sendInCurrent);
  assert(vesc.live.inCurrentMax==90 && vesc.live.inCurrentMin==-90);
}
static void testAck(){
  command(GK_CMD_SET_MODE,1,42);assert(vesc.writes.size()==1&&result()==GK_RES_ACCEPTED&&!modeConfirmed);
  assert(wState==W_SENT);completeWrite();assert(result()==GK_RES_APPLIED&&modeConfirmed);
  command(GK_CMD_SET_MODE,1,42);assert(vesc.writes.size()==1&&result()==GK_RES_APPLIED);
  // Same real M5 token/frame is consumed once. Current readiness gates it before command logic.
  m5Gate.rotate(0x12345678,nowMs);m5link::Request request{m5Gate.token,100,0};char line[48];
  size_t n=m5link::encode(line,sizeof line,request);assert(n);line[n-1]=0;
  m5HandleLine(line);assert(vesc.writes.size()==2&&m5Request==100);m5HandleLine(line);assert(vesc.writes.size()==2);
  completeWrite();assert(cmdEnt(m5Owner)&&cmdEnt(m5Owner)->result==GK_RES_APPLIED);
}
static void testStopStart(){
  modeReq=1;vesc.live.currentMaxScale=.75f;
  command(GK_CMD_STOP,0,10);assert(stopActive&&vesc.custom.size()==1);
  assert(vesc.custom[0]==std::vector<uint8_t>({'G','K','B',STOP_BRAKE_AMPS,uint8_t(STOP_BRAKE_SECS*10)}));
  const float expected[]={.5f,.2f,0};
  for(float scale:expected){serviceWrites();assert(wState==W_SENT&&vesc.writes.back().currentMaxScale==scale);
    completeWrite();advance(STOP_RAMP_STEP_MS);refresh();}
  assert(stopActive&&rampIdx<0&&vesc.live.currentMaxScale==0&&result()==GK_RES_APPLIED);
  command(GK_CMD_START,0,11);assert(!stopActive&&vesc.writes.back().currentMaxScale==.75f);
  completeWrite();assert(result()==GK_RES_APPLIED&&modeConfirmed);
}
static void testTimers(){
  modeReq=0;vesc.live.currentMaxScale=.5f;
  boostSecs=2;command(GK_CMD_BOOST,100,10);assert(ovActive&&vesc.writes.back().currentMaxScale==1);
  completeWrite();advance(2000);refresh();serviceWrites();assert(!ovActive&&vesc.writes.back().currentMaxScale==.5f);completeWrite();
  slowSecs=2;command(GK_CMD_SLOW,5,11);assert(slowActive&&slowTimed);completeWrite();
  const float slowed=vesc.live.maxErpm;advance(2000);refresh();serviceWrites();
  assert(!slowActive&&!slowTimed&&vesc.writes.back().maxErpm>slowed);completeWrite();
  command(GK_CMD_RACE,2,12);assert(raceHold&&vesc.writes.back().currentMaxScale==0);completeWrite();
  advance(2000);refresh();serviceWrites();assert(!raceHold&&vesc.writes.back().currentMaxScale==.5f);completeWrite();
  // Telemetry rate and ping are still available; full existing control scope is retained.
  const size_t count=vesc.writes.size();command(GK_CMD_RATE,1,13);assert(reportRate==1&&result()==GK_RES_APPLIED);
  command(GK_CMD_PING,0,14);assert(result()==GK_RES_APPLIED&&vesc.writes.size()==count);
}
static void testLinkChange(){
  command(GK_CMD_SET_MODE,1,1);const size_t count=vesc.writes.size();
  vesc.sample.receivedMs=0;serviceWrites();assert(wState==W_IDLE&&result()==GK_RES_UNKNOWN);
  advance(20);vescLinkUpMs=nowMs;vesc.fwSeenMs=nowMs;refresh();serviceWrites();
  assert(vesc.writes.size()==count&&result()==GK_RES_UNKNOWN);
  advance(1000);refresh();serviceWrites();assert(vesc.writes.size()==count);
  // A fresh operator command is required; a late ACK from the old session is not confirmation.
  vesc.ack=nowMs;serviceWrites();assert(result()==GK_RES_UNKNOWN&&vesc.writes.size()==count);
  command(GK_CMD_SET_MODE,1,2);assert(vesc.writes.size()==count+1);completeWrite();assert(result()==GK_RES_APPLIED);
}
static void testCeiling(){
  origLimits.currentMaxScale=.6f;vesc.live.currentMaxScale=.6f;modeReq=0;
  const auto before=drivingState();command(GK_CMD_SET_MODE,2,1);
  assert(vesc.writes.empty()&&drivingState()==before&&result()==GK_RES_REJECTED);
  command(GK_CMD_BOOST,100,2);assert(vesc.writes.empty()&&drivingState()==before&&result()==GK_RES_REJECTED);
  stopActive=true;modeReq=2;const auto stopped=drivingState();
  command(GK_CMD_START,0,3);assert(vesc.writes.empty()&&drivingState()==stopped&&result()==GK_RES_REJECTED);
}
static void testBaseline(){
  origValid=false;vescLinkWas=false;vesc.fwSeenMs=0;vesc.uuidHex[0]=0;
  vesc.live.receivedMs=0;serviceVesc();assert(!origValid&&vesc.firmwareReads==1&&vesc.configReads==1);
  advance(1);refresh();serviceVesc();assert(!origValid&&prefs.writes==0&&vesc.writes.empty());
  advance(1);vesc.fwSeenMs=nowMs;strcpy(vesc.uuidHex,UUID);serviceVesc();
  assert(origValid&&!baselineSuspect&&prefs.writes==1&&vesc.writes.empty()&&vesc.custom.empty());
  // Merely maintaining a healthy link or adopting a live mode must never emit a motor write.
  advance(50);refresh();serviceVesc();serviceWrites();assert(vesc.writes.empty()&&vesc.custom.empty());
}

static void testDurations(){
  modeReq=0;vesc.live.currentMaxScale=.5f;
  vescIdentityBad=true;boostSecs=30;
  command(GK_CMD_BOOST,100,1,0xFE);
  assert(result(1)==GK_RES_NO_VESC&&!ovActive&&boostSecs==0&&vesc.writes.empty());
  vescIdentityBad=false;command(GK_CMD_BOOST,100,2);
  assert(ovActive&&ovUntilMs-nowMs==5000);completeWrite();
  advance(5000);refresh();serviceWrites();completeWrite();
  vescIdentityBad=true;slowSecs=30;const size_t count=vesc.writes.size();
  command(GK_CMD_SLOW,5,3,0xFE);
  assert(result(1)==GK_RES_NO_VESC&&!slowActive&&slowSecs==0&&vesc.writes.size()==count);
  vescIdentityBad=false;command(GK_CMD_SLOW,5,4);
  assert(slowActive&&!slowTimed&&slowUntilMs==0);completeWrite();
  // The duplicate fast path must consume one-call USB options too.
  boostSecs=30;command(GK_CMD_BOOST,100,1,0xFE);assert(boostSecs==0);
  command(GK_CMD_BOOST,100,5);assert(ovUntilMs-nowMs==5000);
}
static void testLowStop(){
  origLimits.currentMaxScale=.3f;vesc.live.currentMaxScale=.1f;
  command(GK_CMD_STOP,0,20);assert(stopActive&&result()==GK_RES_ACCEPTED);
  const float expected[]={.1f,.1f,0};
  float previous=vesc.live.currentMaxScale;
  for(float target:expected){serviceWrites();assert(wState==W_SENT);
    const float sent=vesc.writes.back().currentMaxScale;
    assert(sent==target&&sent<=previous);previous=sent;
    completeWrite();advance(STOP_RAMP_STEP_MS);refresh();}
  assert(result()==GK_RES_APPLIED&&vesc.live.currentMaxScale==0);
  command(GK_CMD_START,0,21);assert(vesc.writes.back().currentMaxScale==.3f);
  completeWrite();assert(!stopActive&&result()==GK_RES_APPLIED);
}
static void testRampLinkChange(bool between){
  modeReq=1;vesc.live.currentMaxScale=.75f;
  command(GK_CMD_STOP,0,30);
  if(between){serviceWrites();completeWrite();assert(wState==W_IDLE&&rampIdx==1);}
  const size_t count=vesc.writes.size(),customCount=vesc.custom.size();
  if(between){advance(1);vescLinkUpMs=nowMs;vesc.fwSeenMs=nowMs;refresh();}
  else vesc.sample.receivedMs=0;
  serviceWrites();assert(wState==W_IDLE&&rampIdx<0&&result()==GK_RES_UNKNOWN);
  advance(STOP_RAMP_STEP_MS+1000);vescLinkUpMs=nowMs;vesc.fwSeenMs=nowMs;refresh();
  serviceWrites();command(GK_CMD_STOP,0,30);
  assert(result()==GK_RES_UNKNOWN&&vesc.writes.size()==count&&vesc.custom.size()==customCount);
}
static void testVerificationFailure(bool mismatch){
  command(GK_CMD_SET_MODE,1,40);assert(vesc.writes.size()==1);
  if(mismatch){
    advance(1);vesc.ack=nowMs;serviceWrites();assert(wState==W_VERIFY);
    const unsigned reads=vesc.configReads;
    advance(1);refresh();serviceWrites();assert(wState==W_VERIFY&&vesc.configReads==reads+1);
    advance(1);refresh();serviceWrites();
  }else{advance(VESC_ACK_TIMEOUT_MS+1);serviceWrites();}
  assert(wState==W_IDLE&&result()==GK_RES_UNKNOWN&&!modeConfirmed&&vesc.writes.size()==1);
  advance(1000);refresh();vesc.ack=nowMs;serviceWrites();command(GK_CMD_SET_MODE,1,40);
  assert(result()==GK_RES_UNKNOWN&&vesc.writes.size()==1);
}
static void testM5Blocked(){
  stopActive=true;const auto before=drivingState();m5Gate.rotate(0x12345678,nowMs);
  m5link::Request request{m5Gate.token,101,0};char line[48];
  size_t n=m5link::encode(line,sizeof line,request);assert(n);line[n-1]=0;
  m5HandleLine(line);assert(m5Request==101&&m5Result==GK_RES_REJECTED);
  assert(drivingState()==before&&vesc.writes.empty());
  stopActive=false;refresh();serviceWrites();assert(m5ModeReady());
  m5HandleLine(line);assert(vesc.writes.empty());
  // A newly advertised token and explicit selection can work after the blocked request.
  m5Gate.rotate(0x87654321,nowMs);request={m5Gate.token,102,0};
  n=m5link::encode(line,sizeof line,request);assert(n);line[n-1]=0;
  m5HandleLine(line);assert(vesc.writes.size()==1);completeWrite();
  assert(cmdEnt(m5Owner)&&cmdEnt(m5Owner)->result==GK_RES_APPLIED);
}
static void testWrongBaselineIdentity(){
  origValid=false;vescLinkWas=false;vesc.fwSeenMs=0;vesc.uuidHex[0]=0;
  vesc.live.receivedMs=0;serviceVesc();
  advance(1);refresh();serviceVesc();assert(!origValid&&prefs.writes==0);
  advance(1);vesc.fwSeenMs=nowMs;strcpy(vesc.uuidHex,"ffeeddccbbaa998877665544");
  serviceVesc();assert(!origValid&&vescIdentityBad&&!bleConnected);
  assert(prefs.writes==0&&vesc.writes.empty()&&vesc.custom.empty());
}
static void testGame(){
  courseGeneration[2].accept(222,0x12345,1,nowMs);fleetMs[2]=nowMs;fleet[2].session=2;
  fleet[2].flags=GK_FLAG_GPS_FIX;fleet[2].lat_e7=410000000;fleet[2].lon_e7=-730000000;
  uint32_t requestId=500;
  auto send=[&](m5game::Action action,uint16_t arg=0,uint32_t digest=0x12345){
    m5Gate.rotate(++requestId,nowMs);char line[62];size_t n=m5game::encode(line,sizeof line,{m5Gate.token,requestId,2,action,arg,digest,222});assert(n);line[n-1]=0;
    assert(m5HandleGame(line));auto count=vesc.writes.size();m5HandleGame(line);assert(vesc.writes.size()==count);
  };
  send(m5game::Action::Join);assert(gameSession==2&&m5JoinedCourse==0x12345&&m5GameResult==GK_RES_APPLIED);
  send(m5game::Action::Shell,2);assert(atkTo==2&&atkItem==GK_ITEM_SHELL&&vesc.writes.empty());atkTo=0;
  send(m5game::Action::Boost,7<<8|75,0x98765);assert(m5GameResult==GK_RES_REJECTED&&vesc.writes.empty());
  send(m5game::Action::Boost,7<<8|75);assert(vesc.writes.size()==1);completeWrite();assert(cmdEnt(m5GameOwner)->result==GK_RES_APPLIED);
  stopActive=true;send(m5game::Action::Boost,7<<8|75);assert(m5GameResult==GK_RES_REJECTED&&vesc.writes.size()==1);stopActive=false;
  slowActive=true;send(m5game::Action::Boost,7<<8|75);assert(m5GameResult==GK_RES_REJECTED&&vesc.writes.size()==1);slowActive=false;
  send(m5game::Action::Shield);assert(m5Shield==1);applyHit(2,GK_ITEM_SHELL,8);assert(!m5Shield&&vesc.writes.size()==1);
  send(m5game::Action::Star);completeWrite();assert(m5StarUntil>nowMs);auto count=vesc.writes.size();send(m5game::Action::Mud,4);assert(vesc.writes.size()==count);
  courseGeneration[2].seen=nowMs-6501;send(m5game::Action::Shell,2);assert(!atkTo&&m5GameResult==GK_RES_REJECTED);
  send(m5game::Action::Leave);assert(!gameSession&&!m5JoinedCourse&&!m5Shield&&!m5StarUntil&&vesc.writes.size()==count);
}
int main(int argc,char** argv){
  assert(argc>=2);setup();std::string scenario=argv[1];
  if(scenario=="game")testGame();
  else if(scenario=="guard"){assert(argc==3);testGuard(argv[2]);}
  else if(scenario=="passthrough")testPassthrough();else if(scenario=="ack")testAck();
  else if(scenario=="stop-start")testStopStart();else if(scenario=="timers")testTimers();
  else if(scenario=="link-change")testLinkChange();else if(scenario=="ceiling")testCeiling();
  else if(scenario=="baseline")testBaseline();
  else if(scenario=="baseline-wrong-identity")testWrongBaselineIdentity();
  else if(scenario=="durations")testDurations();else if(scenario=="low-stop")testLowStop();
  else if(scenario=="ramp-link-change"){assert(argc==3);testRampLinkChange(std::string(argv[2])=="between");}
  else if(scenario=="verification-failure"){assert(argc==3);testVerificationFailure(std::string(argv[2])=="mismatch");}
  else if(scenario=="m5-blocked")testM5Blocked();else assert(false);
  std::cout<<"Production control runtime: "<<scenario<<" passed\n";
}
