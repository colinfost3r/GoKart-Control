// GoKart Control v1.5. Display only: no VESC/BLE client, throttle or saved VESC settings.
#include <M5Unified.h>
#include <SD.h>
#include <SPI.h>
#include <esp_system.h>
#include "config.h"
#include "DisplayState.h"
#include "MapView.h"
#include "CourseStorage.h"
#include "DriverView.h"
#include "ScreenLifecycle.h"
#include "LiveGame.h"
#include "GameStorage.h"
#if M5_DEMO
m5dash::PlayerPreview playerPreview;
#endif
#if M5_USE_ESPNOW
#include <M5EspNowSettings.h>
#include <CourseRadio.h>
#include "DisplayMaintenance.h"
m5now::Link wireless;
m5now::Settings wirelessSettings;
m5dash::DisplayMaintenance maintenance;
bool maintenanceMenu=false;
m5game::share::Radio courseRadio(false);
m5dash::LiveGame liveGame;
m5dash::GameStorage<m5dash::GameNvs> gameStorage;
static bool courseReceive(const esp_now_recv_info_t*i,const uint8_t*d,int n){return courseRadio.receive(i,d,n);}


#endif

M5Canvas canvas(&M5.Display);
m5dash::State state;
m5dash::StartupScreen startupScreen;
m5dash::PageHold pageHold;
m5dash::CourseManager courseManager;
m5dash::Course& course=courseManager.active;
m5link::Lines<1152> lines;
SPIClass sdBus(VSPI);
bool mapPage=true;
bool navigationTouch=false;
uint32_t drawMs=0,requestId=0,holdMs=0;
int heldMode=-1; bool holdFired=false;
const char* localModeNotice=nullptr;uint32_t localModeNoticeMs=0;
m5link::Lines<400> usbLines;
uint32_t touchPresses=0;int touchX=-1,touchY=-1;
static void displayStatus(){
  const uint32_t now=millis();const auto& k=state.karts[state.self];
  bool modeReady=state.canRequest(now);
#if M5_USE_ESPNOW
  Serial.printf("{\"t\":\"m5_game\",\"stage\":%u,\"host\":%u,\"course_bytes\":%u,\"digest\":\"%08lx\",\"progress\":%u,\"item\":\"%s\",\"charges\":%u,\"pending\":%lu,\"result\":%d}\n",unsigned(liveGame.stage),liveGame.package.host(),unsigned(liveGame.package.size()),(unsigned long)liveGame.package.digest(),courseRadio.client.progress(),m5dash::LiveGame::name(liveGame.item()),liveGame.charges(),(unsigned long)liveGame.pending,liveGame.result);
#endif
#if M5_USE_ESPNOW
  modeReady=modeReady&&!maintenance.active()&&wireless.channelAligned(now);
#endif
  Serial.printf("{\"t\":\"m5_status\",\"fw\":\"m5-v1.5\",\"transport\":\"%s\",\"kart\":%d,\"live\":%s,\"vesc\":%s,\"mode_ready\":%s,\"page\":\"%s\",\"touch_enabled\":%s,\"touch_presses\":%lu,\"touch_x\":%d,\"touch_y\":%d,\"heap\":%lu,\"course_proto\":1,\"course_source\":\"%s\",\"course_points\":%u,\"course_error\":\"%s\",\"gps_reported_fix\":%s,\"gps_fresh\":%s,\"gps_has_position\":%s,\"gps_position_age_ms\":%ld,\"gps_sats\":%d,\"parse_errors\":%lu,\"map_follow\":%s}\n",
    M5_DEMO?"demo":M5_USE_ESPNOW?"espnow":"uart",state.self,state.live(now)?"true":"false",
    state.live(now)&&k.vesc?"true":"false",modeReady?"true":"false",mapPage?"map":"dash",
    M5.Touch.isEnabled()?"true":"false",(unsigned long)touchPresses,touchX,touchY,(unsigned long)ESP.getFreeHeap(),courseManager.source(),unsigned(course.count),courseManager.error(),
    k.fixReported?"true":"false",k.positionFresh(now)?"true":"false",k.hasPosition?"true":"false",
    k.hasPosition?(long)(now-k.fixReceived):-1L,k.sats,(unsigned long)state.errors,
    m5dash::MapView::make(state,course,now).following?"true":"false");
}
static void displayUsb(){
  unsigned budget=160;
  while(budget--&&Serial.available()){
    const char* line=usbLines.feed((char)Serial.read(),millis());if(!line)continue;
#if M5_USE_ESPNOW
    if(courseRadio.command(line,Serial,state.self,millis()))continue;
    if(wirelessSettings.command(line,wireless,Serial))continue;
    if(!strcmp(line,"ota on"))wireless.setChannelSearchEnabled(false);
    if(maintenance.command(line,Serial)){
      wireless.setChannelSearchEnabled(!maintenance.active());
      if(maintenance.active())maintenanceMenu=true;
      continue;
    }
#endif
    bool courseBusy=false;
#if M5_USE_ESPNOW
    courseBusy=maintenance.active()||maintenance.updating()||maintenance.restarting();
#endif
#if M5_DEMO
    if(!strncmp(line,"demo ",5)){
      bool ok=playerPreview.scenario(line+5,millis());
      Serial.printf("{\"t\":\"demo\",\"ok\":%s,\"no_output\":true}\n",ok?"true":"false");
      continue;
    }
    (void)courseBusy; // Preview uses RAM only; no course/pairing/config flash writes.
#else
    if(courseManager.command(line,Serial,millis(),courseBusy))continue;
#endif
    if(!strcmp(line,"status"))displayStatus();
    else if(!strcmp(line,"reboot")){Serial.flush();ESP.restart();}
  }
}

void text(const char* s,int x,int y,int size=1,uint16_t color=TFT_WHITE) {
  canvas.setTextColor(color,TFT_BLACK);canvas.setTextSize(size);canvas.setCursor(x,y);canvas.print(s);
}
void metric(float v,const char* suffix,char* b,size_t n,int decimals=1) {
  if(!std::isfinite(v))snprintf(b,n,"-- %s",suffix);else snprintf(b,n,"%.*f %s",decimals,v,suffix);
}
void loadCourse() {
  courseManager.begin();
  // Internal outline wins; SD remains an optional boot-time fallback.
  sdBus.begin(18,38,23,4);
  if(!SD.begin(4,sdBus,20000000))return;
  File f=SD.open("/gokart/course.json",FILE_READ);
  if(!f)return;
  if(f.size()>24576){courseManager.sdError("sd_oversize");f.close();return;}
  JsonDocument d;m5dash::Course next;
  bool valid=!deserializeJson(d,f,DeserializationOption::NestingLimit(5))&&next.load(d.as<JsonVariantConst>());
  f.close();
  if(valid)courseManager.sdFallback(next);else courseManager.sdError("sd_invalid");
}
#if M5_USE_ESPNOW
static void drawMaintenance(){
  canvas.fillScreen(TFT_BLACK);
  text("DISPLAY UPDATES",10,10,2,TFT_CYAN);
  const char* status=maintenance.restarting()?"Update complete / restarting":maintenance.updating()?"Installing authenticated firmware":maintenance.ready()?"Ready for password-protected OTA":maintenance.active()?"Joining saved Wi-Fi...":maintenance.configured()?"Updates are disabled":"Set up update Wi-Fi over USB first";
  text(status,10,43,1,TFT_WHITE);
  if(maintenance.configured()){char host[55];snprintf(host,sizeof host,"%s.local",maintenance.hostname());text(host,10,61,1,TFT_LIGHTGREY);}
  if(maintenance.active()){
    char detail[60];snprintf(detail,sizeof detail,"%u%% uploaded | window %lu:%02lu",unsigned(maintenance.progress()),(unsigned long)(maintenance.remainingMs()/60000),(unsigned long)(maintenance.remainingMs()/1000%60));
    text(detail,10,80,1,TFT_YELLOW);
  }
  if(maintenance.lastError()[0])text(maintenance.lastError(),10,96,1,TFT_YELLOW);
  canvas.drawRoundRect(10,108,300,48,6,TFT_CYAN);
  text(maintenance.active()?"DISABLE UPDATES":"ENABLE UPDATES",23,124,2,maintenance.updating()?TFT_DARKGREY:TFT_WHITE);
  text("Live display data may pause in update mode.",10,166,1,TFT_LIGHTGREY);
  canvas.drawRoundRect(10,186,300,44,6,TFT_LIGHTGREY);text("BACK TO DASHBOARD",22,200,2,TFT_WHITE);
  canvas.pushSprite(0,0);
}
#endif
void draw(uint32_t now) {
#if M5_USE_ESPNOW
  if(maintenanceMenu||maintenance.updating()||maintenance.restarting()){drawMaintenance();return;}
#endif
  if(startupScreen.visible(now)){
    m5dash::DriverView<M5Canvas> bootView(canvas);bootView.startup(M5_DEMO);
    canvas.pushSprite(0,0);return;
  }
  const auto& k=state.karts[state.self];
  const char* note=!state.live(now)?"HELTEC LOST / no automatic commands":k.stopped?"PIT STOP ACTIVE":k.slow?"PIT SLOW ACTIVE":state.pending?"Mode requested; awaiting read-back":state.pendingUnknown?"Outcome unknown; no retry":state.result==2?"Mode applied / read-back received":state.result==4?"Request refused":state.result==3?"VESC unavailable":state.canRequest(now)?"Hold a mode button to request":state.live(now)?"Mode controls unavailable":"No commands on reconnect";
  if(localModeNotice&&uint32_t(now-localModeNoticeMs)<4000&&state.live(now)&&!state.pending&&!k.stopped&&!k.slow)note=localModeNotice;
#if M5_USE_ESPNOW
  if(maintenance.active())note="UPDATE MODE / controls unavailable";
  else if(state.live(now)&&!k.stopped&&!state.pending&&!state.pendingUnknown&&
          !wireless.channelAligned(now))note="Waiting for verified radio channel";
#endif
#if M5_DEMO
  note="SIMULATION / MODE OUTPUT DISABLED";
#endif
  m5dash::DriverView<M5Canvas> view(canvas);
  const m5dash::Course* shownCourse=&course;
#if M5_USE_ESPNOW
  if(liveGame.package.valid())shownCourse=&liveGame.course;
#endif
  view.draw(state,*shownCourse,now,mapPage,M5_DEMO,M5_BEGINNER_MODE,note,heldMode,holdMs,holdFired,
#if M5_DEMO
    &playerPreview
#else
    nullptr
#endif
#if M5_USE_ESPNOW
    , &liveGame, &courseRadio.client
#endif
  );
  canvas.pushSprite(0,0);
}
#if M5_USE_ESPNOW && !M5_DEMO
static bool gameSend(const char*line,uint32_t now){return !maintenanceMenu&&!maintenance.active()&&!maintenance.updating()&&!maintenance.restarting()&&wireless.canSend(now)&&wireless.sendLine(line,now);}
static uint32_t nextRequest(){if(++requestId==0)++requestId;return requestId;}
static void servicePlayer(uint32_t now){
  auto& receiver=courseRadio.client;
  if(maintenanceMenu||maintenance.active()||maintenance.updating()||maintenance.restarting()){
    if(receiver.busy())receiver.cancel("Update mode; join again");
    if(liveGame.active()||liveGame.busy())liveGame.fail("Update mode; join again");
    return;
  }
  liveGame.tick(state,now);
  if(liveGame.stage==m5dash::LiveGame::Stage::Downloading){
    if(!liveGame.intentValid(state,now)){receiver.cancel("Link changed; join again");liveGame.fail("Link changed; join again");}
    else if(receiver.stage==m5game::share::Receiver::Stage::Error)liveGame.fail(receiver.error);
    else if(receiver.stage==m5game::share::Receiver::Stage::Complete){
      if(!gameStorage.save(receiver.data(),receiver.size())||!liveGame.load(receiver.data(),receiver.size()))liveGame.fail("Save failed; previous course kept");
      else {liveGame.courseBoot=receiver.boot();liveGame.stage=m5dash::LiveGame::Stage::Joining;liveGame.note="Course saved; joining";}
      receiver.accepted();
    }
  }
  if(!liveGame.busy()&&receiver.busy())receiver.cancel("Join canceled");
  // This is the one outstanding explicit JOIN gesture, not a reconnect retry.
  if(liveGame.stage==m5dash::LiveGame::Stage::Joining&&!liveGame.pending){
    if(!liveGame.intentValid(state,now))liveGame.fail("Link changed; join again");
    else if(!liveGame.request(m5game::Action::Join,liveGame.joinArg(),state,nextRequest(),now,gameSend))liveGame.fail("Join unavailable; tap JOIN again");
  }
  liveGame.position(state,nextRequest(),now,gameSend,[](){return esp_random();});
}
static void requestWirelessMode(uint8_t mode,uint32_t now) {
  localModeNotice=nullptr;localModeNoticeMs=now;
  // Joined to a game: the own Heltec is locked to the host's game speed and would refuse this.
  if(state.gameMode<3&&mode!=state.gameMode){
    localModeNotice=state.gameMode==1?"Locked: game speed is NORMAL":"Locked: game speed is ECO";return;
  }
  if(maintenance.active()||!state.canRequest(now)){
    localModeNotice="Mode unavailable: release and hold again";return;
  }
  if(!wireless.canSend(now)){
    localModeNotice="Radio busy: release and hold again";return;
  }
  char line[48];if(++requestId==0)++requestId;
  size_t n=state.request(mode,requestId,now,line,sizeof line);
  if(!n){localModeNotice="Mode unavailable: release and hold again";return;}
  if(!wireless.sendLine(line,now)){
    // false means the transport did not enqueue this line. Keep the token
    // consumed, but do not claim a sent request or retry this held gesture.
    state.pending=0;state.requested=-1;state.result=0;state.pendingUnknown=false;
    localModeNotice="Not sent: release and hold again";
  }
}
#endif
void touch(uint32_t now) {
  auto t=M5.Touch.getDetail();
  if(t.wasPressed()){++touchPresses;touchX=t.x;touchY=t.y;}
  if(!t.isPressed()){navigationTouch=false;pageHold.reset();}
  if(startupScreen.visible(now)){
    navigationTouch=t.isPressed();heldMode=-1;holdFired=false;pageHold.reset();return;
  }
  if(navigationTouch){
    heldMode=-1;holdFired=false;
#if M5_USE_ESPNOW
    if(pageHold.maintenance(t.x,t.y,now))maintenanceMenu=true;
#endif
    return;
  }
#if M5_USE_ESPNOW
  if(maintenanceMenu||maintenance.updating()||maintenance.restarting()){
    heldMode=-1;holdFired=false;pageHold.reset();
    if(t.wasPressed())navigationTouch=true; // Every overlay press is consumed through release, including BACK.
    if(!maintenance.updating()&&!maintenance.restarting()&&t.wasPressed()){
      if(t.x>=10&&t.x<310&&t.y>=108&&t.y<156){
        if(maintenance.active())maintenance.stop();
        else {wireless.setChannelSearchEnabled(false);maintenance.start();}
        wireless.setChannelSearchEnabled(!maintenance.active());
      }else if(t.x>=10&&t.x<310&&t.y>=186&&t.y<230)maintenanceMenu=false;
    }
    return;
  }
#endif
#if M5_USE_ESPNOW && !M5_DEMO
  if(liveGame.overlay||(t.wasPressed()&&m5dash::layout::invite.contains(t.x,t.y))){
    heldMode=-1;holdFired=false;
    if(t.wasPressed()){
      navigationTouch=true;
      if(!liveGame.overlay)liveGame.opening();
      else if(m5dash::layout::close.contains(t.x,t.y)){
        if(courseRadio.client.busy())courseRadio.client.cancel("Download canceled");
        if(liveGame.stage==m5dash::LiveGame::Stage::Downloading)liveGame.fail("Download canceled");
        liveGame.overlay=false;
      }else if(m5dash::layout::join.contains(t.x,t.y)&&!liveGame.busy()){
        if(liveGame.active())liveGame.request(m5game::Action::Leave,0,state,nextRequest(),now,gameSend);
        else if(state.live(now)&&state.metadataFresh(now)&&state.gameVersion==m5game::GAME_VERSION&&wireless.canSend(now)&&courseRadio.client.begin(esp_random(),esp_random(),now))liveGame.downloadStarted(state);
        else liveGame.fail("Host unavailable; move closer");
      }
    }
    return;
  }
#endif
#if M5_DEMO
  if(playerPreview.overlay || (t.wasPressed()&&m5dash::layout::invite.contains(t.x,t.y))){
    heldMode=-1;holdFired=false;
    if(t.wasPressed()){playerPreview.tap(t.x,t.y,now);navigationTouch=true;}
    return;
  }
#endif
  if(t.wasPressed()&&m5dash::layout::page.contains(t.x,t.y)){
    mapPage=!mapPage;heldMode=-1;holdFired=false;navigationTouch=true;pageHold.begin(now);return;
  }
  if(mapPage){
    heldMode=-1;holdFired=false;
#if M5_DEMO
    if(t.wasPressed()&&m5dash::layout::fire.contains(t.x,t.y)){playerPreview.fire(now);navigationTouch=true;}
#endif
#if M5_USE_ESPNOW && !M5_DEMO
    if(t.wasPressed()&&m5dash::layout::fire.contains(t.x,t.y)){liveGame.fire(state,nextRequest(),now,gameSend);navigationTouch=true;}
#endif
    return;
  }
  int at=(t.isPressed()&&t.y>=202&&t.y<240&&t.x>=0&&t.x<320)?std::min(2,t.x/107):-1;
  if(at<0||at!=heldMode){heldMode=at;holdMs=now;holdFired=false;}
  if(at>=0&&!holdFired&&uint32_t(now-holdMs)>=M5_MODE_HOLD_MS){
    holdFired=true;
#if !M5_DEMO
#if M5_USE_ESPNOW
    requestWirelessMode(uint8_t(at),now);
#else
    char line[48];
    if(Serial2.availableForWrite()>=40){
      if(++requestId==0)++requestId;
      size_t n=state.request(uint8_t(at),requestId,now,line,sizeof line);
      if(n)Serial2.write((uint8_t*)line,n); // one write; never queued/retried by this app
    }
#endif
#endif
  }
}
#if M5_DEMO
void demo(uint32_t now) {
  playerPreview.tick(now);
  static uint32_t sent=0;if(now-sent<200)return;sent=now;
  if(playerPreview.linkLost)return;
  char line[1000];
  snprintf(line,sizeof line,"{\"t\":\"display\",\"v\":1,\"kart\":3,\"boot\":1,\"token\":0,\"mode_ready\":false,\"radio\":true,\"pit\":true,\"rate\":2,\"speed_cal\":1,\"modes\":[{\"mph\":15,\"scale\":0.5},{\"mph\":25,\"scale\":0.75},{\"mph\":0,\"scale\":1}]}");
  state.ingest(line,now);
  for(int i=1;i<=8;++i){double a=now/9000.0+m5dash::PreviewMap::kartPhase(i);
    snprintf(line,sizeof line,"{\"t\":\"%s\",\"kart\":%d,\"lat\":%.7f,\"lon\":%.7f,\"fix\":true,\"gps_age_s\":0,\"sats\":10,\"gps_kph\":22,\"vesc_link\":true,\"volts\":79.4,\"motor_a\":12,\"batt_a\":4,\"esc_c\":32,\"fault\":0,\"mode_actual\":1,\"mode_confirmed\":true}",i==3?"self":"fleet",i,41.0938+0.0003*sin(a),-73.4163+0.0005*cos(a));
    state.ingest(line,now);
    if(playerPreview.gpsLost&&i==3){state.karts[i].fix=false;state.karts[i].fixReported=false;}
  }
}
#endif
void setup() {
  Serial.begin(115200);
  auto cfg=M5.config();M5.begin(cfg);M5.Display.setRotation(1);M5.Display.setBrightness(160);
  canvas.setColorDepth(16);
  if(!canvas.createSprite(320,240)){M5.Display.println("Display memory unavailable");while(true)delay(1000);}
  requestId=esp_random();
#if M5_USE_ESPNOW
  Serial.begin(115200);
  m5now::Link::setExtraReceiver(courseReceive);
  if(wirelessSettings.load()){
    const auto& p=wirelessSettings.pair;
    wireless.begin(m5now::Role::Display,p.peer,p.lmk,p.pmk);
    courseRadio.begin();
  }
  wirelessSettings.status(wireless,Serial);
  maintenance.begin();
  maintenance.setUiCallback([](){maintenanceMenu=true;draw(millis());});
#elif !M5_DEMO
  Serial2.setRxBufferSize(8192);Serial2.setTxBufferSize(128);
  Serial2.begin(M5_LINK_BAUD,SERIAL_8N1,M5_LINK_RX,M5_LINK_TX);
#endif
#if M5_DEMO
  snprintf(course.name,sizeof course.name,"DEMO LOOP / NOT A SURVEYED COURSE");
  course.closed=true;course.count=48;
  for(size_t i=0;i<course.count;++i){double a=i*6.283185307179586/course.count;
    course.lat[i]=41.0938+0.0003*sin(a);course.lon[i]=-73.4163+0.0005*cos(a);}

#else
  loadCourse();
#if M5_USE_ESPNOW
  if(gameStorage.load(liveGame.package))liveGame.load(liveGame.package.data(),liveGame.package.size());
#endif
#endif
  startupScreen.begin(millis()); // Time five seconds of visible splash, after peripheral/storage initialization.
  draw(millis());displayStatus();
}
void loop() {
  M5.update();displayUsb();uint32_t now=millis();
#if M5_DEMO
  demo(now);
#elif M5_USE_ESPNOW
  maintenance.poll();
  wireless.setChannelSearchEnabled(!maintenance.active());
  now=millis();wireless.poll(now);
  for(unsigned budget=0;budget<12;++budget){
    const char* line=wireless.readLine(millis());if(!line)break;
    state.ingest(line,wireless.receivedMs());
  }
#else
  unsigned budget=4096;
  while(budget--&&Serial2.available()){const char* s=lines.feed((char)Serial2.read(),millis());if(s)state.ingest(s,millis());}
#endif
  now=millis(); // RX parsing can advance time: never test freshness against an earlier timestamp.
  state.tick(now);
#if M5_USE_ESPNOW && !M5_DEMO
  if(wireless.ready())courseRadio.begin();
  courseRadio.poll(state.self,false,!maintenanceMenu&&!maintenance.active()&&!maintenance.updating()&&!maintenance.restarting()&&wireless.canSend(now),now);
  servicePlayer(millis());
#endif
  touch(millis());
  if(uint32_t(now-drawMs)>=M5_DRAW_MS){drawMs=now;draw(now);}
  delay(1);
}
