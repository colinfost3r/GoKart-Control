// GoKart Control v1.5. Display only: no VESC/BLE client, throttle or saved VESC settings.
#include <M5Unified.h>
#include <SD.h>
#include <SPI.h>
#include <esp_system.h>
#include "config.h"
#include "DisplayState.h"
#if M5_USE_ESPNOW
#include <M5EspNowSettings.h>
#include "DisplayMaintenance.h"
m5now::Link wireless;
m5now::Settings wirelessSettings;
m5dash::DisplayMaintenance maintenance;
bool maintenanceMenu=false,headerHolding=false;
uint32_t headerHoldMs=0;

#endif

M5Canvas canvas(&M5.Display);
m5dash::State state;
m5dash::Course course;
m5link::Lines<1152> lines;
SPIClass sdBus(VSPI);
bool mapPage=false,onlineOnly=true;
struct TabRect {int x,y,w,h;bool contains(int px,int py)const{return px>=x&&px<x+w&&py>=y&&py<y+h;}};
// Visible buttons and touch targets share exactly the same bounds.
constexpr TabRect tabs[3]={{4,23,94,40},{103,23,94,40},{202,23,114,40}};
uint32_t drawMs=0,requestId=0,holdMs=0;
int heldMode=-1; bool holdFired=false;
m5link::Lines<400> usbLines;
uint32_t touchPresses=0;int touchX=-1,touchY=-1;
static void displayStatus(){
  const uint32_t now=millis();const auto& k=state.karts[state.self];
  bool modeReady=state.canRequest(now);
#if M5_USE_ESPNOW
  modeReady=modeReady&&!maintenance.active();
#endif
  Serial.printf("{\"t\":\"m5_status\",\"fw\":\"m5-v1.5\",\"transport\":\"%s\",\"kart\":%d,\"live\":%s,\"vesc\":%s,\"mode_ready\":%s,\"page\":\"%s\",\"touch_enabled\":%s,\"touch_presses\":%lu,\"touch_x\":%d,\"touch_y\":%d,\"heap\":%lu}\n",
    M5_DEMO?"demo":M5_USE_ESPNOW?"espnow":"uart",state.self,state.live(now)?"true":"false",
    state.live(now)&&k.vesc?"true":"false",modeReady?"true":"false",mapPage?"map":"dash",
    M5.Touch.isEnabled()?"true":"false",(unsigned long)touchPresses,touchX,touchY,(unsigned long)ESP.getFreeHeap());
}
static void displayUsb(){
  unsigned budget=160;
  while(budget--&&Serial.available()){
    const char* line=usbLines.feed((char)Serial.read(),millis());if(!line)continue;
#if M5_USE_ESPNOW
    if(wirelessSettings.command(line,wireless,Serial))continue;
    if(!strcmp(line,"ota on"))wireless.setChannelSearchEnabled(false);
    if(maintenance.command(line,Serial)){
      wireless.setChannelSearchEnabled(!maintenance.active());
      if(maintenance.active())maintenanceMenu=true;
      continue;
    }
#endif
    if(!strcmp(line,"status"))displayStatus();
    else if(!strcmp(line,"reboot")){Serial.flush();ESP.restart();}
  }
}
const char* names[3]={"ECO","NORMAL","SPORT"};
const uint16_t colors[9]={0,0xf986,0x3e49,0xff20,0x535a,0xfc20,0x801f,0x3e9f,0xf81f};

void text(const char* s,int x,int y,int size=1,uint16_t color=TFT_WHITE) {
  canvas.setTextColor(color,TFT_BLACK);canvas.setTextSize(size);canvas.setCursor(x,y);canvas.print(s);
}
void metric(float v,const char* suffix,char* b,size_t n,int decimals=1) {
  if(!std::isfinite(v))snprintf(b,n,"-- %s",suffix);else snprintf(b,n,"%.*f %s",decimals,v,suffix);
}
void loadCourse() {
  // Optional offline outline: export the pit's track with tools/m5/export_course.py.
  sdBus.begin(18,38,23,4);
  if(!SD.begin(4,sdBus,20000000))return;
  File f=SD.open("/gokart/course.json",FILE_READ);
  if(!f || f.size()>24576)return;
  JsonDocument d;
  if(!deserializeJson(d,f,DeserializationOption::NestingLimit(5)))course.load(d.as<JsonVariantConst>());
  f.close();
}
void drawMap(uint32_t now) {
  auto b=state.bounds(course,now,onlineOnly);
  if(!b.valid){text("Waiting for GPS / course",10,85,1,TFT_YELLOW);return;}
  double spanX=std::max(40.0,b.maxX-b.minX),spanY=std::max(40.0,b.maxY-b.minY);
  double scale=std::min(288.0/spanX,98.0/spanY);
  double cx=(b.maxX+b.minX)/2,cy=(b.maxY+b.minY)/2;
  auto px=[&](double lon){return 160+int((b.x(lon)-cx)*scale);};
  auto py=[&](double lat){return 119-int((b.y(lat)-cy)*scale);};
  canvas.drawRect(3,66,314,106,TFT_DARKGREY);
  for(size_t i=1;i<course.count;++i)canvas.drawLine(px(course.lon[i-1]),py(course.lat[i-1]),px(course.lon[i]),py(course.lat[i]),TFT_CYAN);
  if(course.closed&&course.count>2)canvas.drawLine(px(course.lon[course.count-1]),py(course.lat[course.count-1]),px(course.lon[0]),py(course.lat[0]),TFT_CYAN);
  for(int i=1;i<=8;++i){
    const auto& k=state.karts[i];
    if(!k.hasPosition || uint32_t(now-k.fixReceived)>15000 || (onlineOnly&&!k.positionFresh(now)))continue;
    int x=px(k.lon),y=py(k.lat); bool fresh=k.positionFresh(now);
    uint16_t c=fresh?colors[i]:TFT_DARKGREY;
    if(i==state.self)canvas.drawCircle(x,y,10,TFT_WHITE);
    if(fresh)canvas.fillCircle(x,y,7,c);else canvas.drawCircle(x,y,7,c);
    canvas.setTextColor(fresh?TFT_BLACK:TFT_WHITE);canvas.setTextSize(1);canvas.setCursor(x-3,y-3);canvas.print(i);
  }
  char label[50];snprintf(label,sizeof label,"N up | %.0f m wide | %s",288/scale,course.count?"course":"GPS only");text(label,5,175,1,TFT_LIGHTGREY);
}
void drawDash(uint32_t now) {
  const auto& k=state.karts[state.self]; bool live=state.live(now),vesc=live&&k.vesc;
  char b[48];
  if(live&&k.positionFresh(now)&&std::isfinite(k.gpsKph)){snprintf(b,sizeof b,"%.0f",k.gpsKph*0.621371);text(b,10,68,6);}
  else text("--",10,68,6,TFT_DARKGREY);
  text("MPH GPS",12,119,1,TFT_LIGHTGREY);
  metric(vesc?k.volts:NAN,"V",b,sizeof b);text(b,173,68,2);
  metric(vesc?k.escC:NAN,"C ESC",b,sizeof b,0);text(b,173,93,2);
  metric(vesc?k.volts*k.battA:NAN,"W",b,sizeof b,0);text(b,173,118,2);
  metric(vesc?k.motorA:NAN,"A motor",b,sizeof b);text(b,10,138,1);
  metric(vesc?k.battA:NAN,"A battery",b,sizeof b);text(b,173,138,1);
  if(!live)snprintf(b,sizeof b,"HELTEC DATA LOST");
  else if(!k.vesc)snprintf(b,sizeof b,"VESC DISCONNECTED");
  else if(k.stopped)snprintf(b,sizeof b,"PIT STOP ACTIVE");
  else if(k.slow)snprintf(b,sizeof b,"PIT SLOW: %d mph",k.slow);
  else if(!M5_BEGINNER_MODE&&k.fault>0)snprintf(b,sizeof b,"VESC FAULT %d",k.fault);
  else snprintf(b,sizeof b,"%s %s | GPS %d sats",k.mode>=0?names[k.mode]:"MODE ?",k.confirmed?"verified":"unconfirmed",k.sats);
  text(b,10,161,1,TFT_YELLOW);
  if(state.metadataFresh(now)&&std::isfinite(state.speedCal)){snprintf(b,sizeof b,"RF %d Hz / %d dBm | Cal %.3f",state.rate,state.baseRssi,state.speedCal);text(b,10,177,1,TFT_LIGHTGREY);}
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
  canvas.fillScreen(TFT_BLACK);char b[64];const auto& k=state.karts[state.self];
  bool meta=state.metadataFresh(now);
  if(M5_DEMO)snprintf(b,sizeof b,"DEMO / NO OUTPUT   K%d",state.self);
  else snprintf(b,sizeof b,"K%d  %s  PIT %s  %s",state.self,state.live(now)?"LINK":"NO LINK",meta?(state.pit?"OK":"LOST"):"?",meta?(state.radio?"RADIO OK":"RADIO FAIL"):"");
  text(b,5,5,1,state.live(now)?TFT_WHITE:TFT_YELLOW);
  canvas.drawFastHLine(0,20,320,TFT_DARKGREY);
  for(int i=0;i<2;++i){
    const auto& t=tabs[i];bool selected=(i==1)==mapPage;
    canvas.drawRoundRect(t.x,t.y,t.w,t.h,5,selected?TFT_CYAN:TFT_LIGHTGREY);
    text(i?"MAP":"DASH",t.x+14,t.y+12,2,selected?TFT_CYAN:TFT_WHITE);
  }
  if(mapPage){const auto& t=tabs[2];canvas.drawRoundRect(t.x,t.y,t.w,t.h,5,TFT_YELLOW);text(onlineOnly?"FRESH ONLY":"STALE TOO",t.x+11,t.y+16,1,TFT_YELLOW);}
  if(mapPage)drawMap(now);else drawDash(now);
  const char* note=!state.live(now)?"HELTEC LOST / no automatic commands":k.stopped?"PIT STOP ACTIVE":k.slow?"PIT SLOW ACTIVE":state.pending?"Mode requested; awaiting read-back":state.pendingUnknown?"Outcome unknown; no retry":state.result==2?"Mode applied / read-back received":state.result==4?"Request refused":state.result==3?"VESC unavailable":state.canRequest(now)?"Hold a mode button to request":state.live(now)?"Mode controls unavailable":"No commands on reconnect";
#if M5_USE_ESPNOW
  if(maintenance.active())note="UPDATE MODE / controls unavailable";
#endif
  text(note,5,189,1,TFT_LIGHTGREY);
  for(int i=0;i<3;++i){
    int x=i*107;bool selected=state.live(now)&&k.vesc&&k.confirmed&&k.mode==i;
    canvas.drawRoundRect(x+2,202,102,36,4,selected?TFT_YELLOW:TFT_DARKGREY);
    text(names[i],x+8,207,1,selected?TFT_YELLOW:TFT_WHITE);
    if(!meta||!std::isfinite(state.cap[i]))snprintf(b,sizeof b,"cap ?");
    else if(state.cap[i]==0)snprintf(b,sizeof b,"no cap");
    else snprintf(b,sizeof b,"%.0f mph",state.cap[i]);
    text(b,x+8,222,1,TFT_LIGHTGREY);
    if(heldMode==i&&!holdFired)canvas.fillRect(x+3,235,std::min(100,(int)((now-holdMs)*100/M5_MODE_HOLD_MS)),2,TFT_CYAN);
  }
  canvas.pushSprite(0,0);
}
void touch(uint32_t now) {
  auto t=M5.Touch.getDetail();
  if(t.wasPressed()){++touchPresses;touchX=t.x;touchY=t.y;}
#if M5_USE_ESPNOW
  if(maintenanceMenu||maintenance.updating()||maintenance.restarting()){
    heldMode=-1;holdFired=false;headerHolding=false;
    if(!maintenance.updating()&&!maintenance.restarting()&&t.wasPressed()){
      if(t.x>=10&&t.x<310&&t.y>=108&&t.y<156){
        if(maintenance.active())maintenance.stop();
        else {wireless.setChannelSearchEnabled(false);maintenance.start();}
        wireless.setChannelSearchEnabled(!maintenance.active());
      }else if(t.x>=10&&t.x<310&&t.y>=186&&t.y<230)maintenanceMenu=false;
    }
    return;
  }
  if(t.isPressed()&&t.x>=0&&t.x<320&&t.y>=0&&t.y<22){
    if(!headerHolding){headerHolding=true;headerHoldMs=now;}
    if(uint32_t(now-headerHoldMs)>=1800){maintenanceMenu=true;heldMode=-1;return;}
  }else headerHolding=false;
#endif
  if(t.wasPressed()){
    if(tabs[0].contains(t.x,t.y))mapPage=false;
    else if(tabs[1].contains(t.x,t.y))mapPage=true;
    else if(mapPage&&tabs[2].contains(t.x,t.y))onlineOnly=!onlineOnly;
  }
  int at=(t.isPressed()&&t.y>=202&&t.y<240&&t.x>=0&&t.x<320)?std::min(2,t.x/107):-1;
  if(at<0||at!=heldMode){heldMode=at;holdMs=now;holdFired=false;}
  if(at>=0&&!holdFired&&uint32_t(now-holdMs)>=M5_MODE_HOLD_MS){
    holdFired=true;
#if !M5_DEMO
    char line[48];
#if M5_USE_ESPNOW
    if(!maintenance.active()&&wireless.canSend(now)){
#else
    if(Serial2.availableForWrite()>=40){
#endif
      if(++requestId==0)++requestId;
      size_t n=state.request(uint8_t(at),requestId,now,line,sizeof line);
#if M5_USE_ESPNOW
      if(n)wireless.sendLine(line,now); // immediate attempt; never replayed after a loss
#else
      if(n)Serial2.write((uint8_t*)line,n); // one write; never queued/retried by this app
#endif
    }
#endif
  }
}
#if M5_DEMO
void demo(uint32_t now) {
  static uint32_t sent=0;if(now-sent<200)return;sent=now;
  char line[1000];
  snprintf(line,sizeof line,"{\"t\":\"display\",\"v\":1,\"kart\":1,\"boot\":1,\"token\":0,\"mode_ready\":false,\"radio\":true,\"pit\":true,\"rate\":2,\"speed_cal\":1,\"modes\":[{\"mph\":15,\"scale\":0.5},{\"mph\":25,\"scale\":0.75},{\"mph\":0,\"scale\":1}]}");
  state.ingest(line,now);
  for(int i=1;i<=8;++i){double a=now/9000.0+i*0.78;
    snprintf(line,sizeof line,"{\"t\":\"%s\",\"kart\":%d,\"lat\":%.7f,\"lon\":%.7f,\"fix\":true,\"gps_age_s\":0,\"sats\":10,\"gps_kph\":22,\"vesc_link\":true,\"volts\":79.4,\"motor_a\":12,\"batt_a\":4,\"esc_c\":32,\"fault\":0,\"mode_actual\":1,\"mode_confirmed\":true}",i==1?"self":"fleet",i,41.0938+0.0003*sin(a),-73.4163+0.0005*cos(a));
    state.ingest(line,now);
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
  if(wirelessSettings.load()){
    const auto& p=wirelessSettings.pair;
    wireless.begin(m5now::Role::Display,p.peer,p.lmk,p.pmk);
  }
  wirelessSettings.status(wireless,Serial);
  maintenance.begin();
  maintenance.setUiCallback([](){maintenanceMenu=true;draw(millis());});
#elif !M5_DEMO
  Serial2.setRxBufferSize(8192);Serial2.setTxBufferSize(128);
  Serial2.begin(M5_LINK_BAUD,SERIAL_8N1,M5_LINK_RX,M5_LINK_TX);
#endif
  loadCourse();draw(millis());displayStatus();
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
  state.tick(now);touch(now);
  if(uint32_t(now-drawMs)>=M5_DRAW_MS){drawMs=now;draw(now);}
  delay(1);
}
