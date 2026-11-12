#pragma once
// Native 320x240 adaptation of Hunter's 5629924 retro.css/display-theme.css.
// Procedural seven-segment numerals are original; no embedded font artwork.
#include "MapView.h"
#include "PlayerPreview.h"
#include "PreviewMap.h"
#include "DisplayMetrics.h"
#include <cstdio>

namespace m5dash {
namespace palette {
constexpr uint16_t rgb(unsigned r,unsigned g,unsigned b){return uint16_t(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
constexpr uint16_t bg=rgb(17,30,40),panel=rgb(41,55,68),text=rgb(237,244,248),muted=rgb(187,203,213);
constexpr uint16_t line=rgb(116,140,156),cyan=rgb(164,229,238),amber=rgb(247,206,121),dim=rgb(68,88,100);
constexpr uint16_t eco=rgb(140,235,196),normal=rgb(139,211,255),sport=rgb(255,154,185),bad=rgb(255,120,120);
constexpr uint16_t modes[3]={eco,normal,sport};
}
template<class Canvas> class DriverView {
  Canvas& c;
  void label(const char* s,int x,int y,int size=1,uint16_t color=palette::text) {
    c.setTextColor(color);c.setTextSize(size);c.setCursor(x,y);c.print(s);
  }
  void box(HitRect r,uint16_t color=palette::line) {
    c.fillRoundRect(r.x,r.y,r.w,r.h,5,palette::panel);c.drawRoundRect(r.x,r.y,r.w,r.h,5,color);
  }
  void number(float n,const char* unit,char* b,size_t len,int decimals=1) {
    if(std::isfinite(n))std::snprintf(b,len,"%.*f %s",decimals,n,unit);else std::snprintf(b,len,"-- %s",unit);
  }
  void digit(int d,int x,int y,int w,int h,uint16_t color) {
    static constexpr unsigned masks[10]={0x3f,0x06,0x5b,0x4f,0x66,0x6d,0x7d,0x07,0x7f,0x6f};
    const unsigned bits=d>=0&&d<=9?masks[d]:0x40;
    const int t=4,half=h/2;
    const HitRect seg[7]={{x+t,y,w-2*t,t},{x+w-t,y+t,t,half-t},{x+w-t,y+half+t,t,half-2*t},
      {x+t,y+h-t,w-2*t,t},{x,y+half+t,t,half-2*t},{x,y+t,t,half-t},{x+t,y+half-2,w-2*t,t}};
    for(unsigned i=0;i<7;++i)if(bits&(1u<<i))c.fillRoundRect(seg[i].x,seg[i].y,seg[i].w,seg[i].h,1,color);
  }
  void navigation(bool map,uint32_t now,const PlayerPreview* preview) {
    box(layout::page,palette::cyan);label(map?"DASH":"MAP",layout::page.x+8,layout::page.y+15,1,palette::cyan);
    if(preview&&preview->available()) {
      box(layout::invite,preview->notify(now)?palette::amber:palette::line);
      c.fillCircle(234,39,4,preview->notify(now)?palette::amber:palette::dim);
      label(preview->stage==PlayerPreview::Stage::Ready||preview->stage==PlayerPreview::Stage::Used?"GAME":"JOIN",222,51,1,palette::amber);
    }
  }
  void previewMarks(const MapView& v,const Course& course) {
    // These points refer ONLY to the 48-point demo loop, never to a live course.
    if(course.count!=48)return;
    auto point=[&](size_t i,double& x,double& y,int margin){
      return v.project(course.lat[i],course.lon[i],x,y)&&v.contains(x,y,margin);
    };
    double x,y;
    if(point(12,x,y,30)){
      int px=lround(x),py=lround(y);
      c.fillRect(px-5,py-13,10,26,palette::bg);
      for(int row=0;row<6;++row)for(int col=0;col<2;++col)
        c.fillRect(px-4+col*4,py-12+row*4,4,4,(row+col)%2?palette::bg:palette::text);
      const int lx=std::max(5,std::min(239,px-36));
      c.fillRoundRect(lx-2,py+15,78,12,2,palette::panel);
      label("START/FINISH",lx,py+17,1,palette::text);
    }
    if(point(21,x,y,12)){
      int px=lround(x),py=lround(y);
      c.fillRoundRect(px-9,py-9,19,19,3,palette::panel);
      c.drawRoundRect(px-9,py-9,19,19,3,palette::eco);
      for(int dy=-3;dy<=3;dy+=6){
        c.drawLine(px-5,py+dy+2,px,py+dy-2,palette::eco);
        c.drawLine(px,py+dy-2,px+5,py+dy+2,palette::eco);
      }
    }
    if(point(8,x,y,12)){
      int px=lround(x),py=lround(y);
      c.fillRoundRect(px-8,py-8,17,17,3,palette::panel);
      c.drawRoundRect(px-8,py-8,17,17,3,palette::amber);
      label("?",px-3,py-4,1,palette::amber);
    }
  }
  void mapTelemetry(const State& state,uint32_t now) {
    box({7,26,187,40},palette::line);
    const float mph=gpsMph(state,now),pct=batteryPercent(state,now);char b[16];
    if(std::isfinite(mph))std::snprintf(b,sizeof b,"%.0f",mph);else std::snprintf(b,sizeof b,"--");
    label(b,15,35,2,palette::cyan);label("MPH",49,42,1,palette::muted);
    c.drawLine(82,32,82,59,palette::line);
    const uint16_t ink=!std::isfinite(pct)?palette::muted:pct<20?palette::bad:pct<40?palette::amber:palette::eco;
    c.drawRect(93,39,16,11,ink);c.fillRect(109,42,2,5,ink);
    if(std::isfinite(pct))c.fillRect(95,41,int(std::lround(pct*12/100)),7,ink);
    if(std::isfinite(pct))std::snprintf(b,sizeof b,"~%.0f%%",pct);else std::snprintf(b,sizeof b,"--%%");
    label(b,119,35,2,ink);
  }
  void map(const State& state,const Course& course,uint32_t now,const PlayerPreview* preview) {
    const auto v=MapView::make(state,course,now);
    if(preview)PreviewMap::draw(c,v);
    else {
      for(int x=20;x<320;x+=40)c.drawLine(x,v.top,x,v.top+v.height-1,palette::panel);
      for(int y=27;y<v.top+v.height;y+=40)c.drawLine(2,y,317,y,palette::panel);
    }
    if(v.valid) {
      auto segment=[&](size_t a,size_t b){double x0,y0,x1,y1;
        if(v.project(course.lat[a],course.lon[a],x0,y0)&&v.project(course.lat[b],course.lon[b],x1,y1)&&v.clip(x0,y0,x1,y1)){
          c.drawLine(lround(x0),lround(y0),lround(x1),lround(y1),palette::cyan);
        }
      };
      for(size_t i=1;i<course.count;++i)segment(i-1,i);
      if(course.closed&&course.count>2)segment(course.count-1,0);
      if(preview)previewMarks(v,course);
      for(unsigned i=1;i<=8;++i) {
        const auto& k=state.karts[i];if(!k.positionFresh(now)||(i==state.self&&!state.live(now)))continue;
        double x,y;if(!v.project(k.lat,k.lon,x,y)||!v.contains(x,y,11))continue;
        int px=lround(x),py=lround(y);bool own=i==state.self;
        c.fillCircle(px,py,own?9:7,own?palette::amber:palette::normal);
        if(own)c.drawCircle(px,py,12,palette::amber);
        char n[3];std::snprintf(n,sizeof n,"%u",i);label(n,px-3,py-3,1,palette::bg);
      }
    }
    if(!v.following){box({9,83,302,38},palette::amber);label(v.valid?"OWN GPS UNAVAILABLE / COURSE OVERVIEW":"WAITING FOR OWN GPS / COURSE",17,98,1,palette::amber);}
    mapTelemetry(state,now);
    const char* status=!state.live(now)?"LINK LOST / POSITION UNAVAILABLE":!v.following?"Waiting for a fresh own GPS fix":course.count?course.name:"GPS ONLY / NO COURSE LOADED";
    if(preview&&preview->stage==PlayerPreview::Stage::HostLost)status="HOST LOST / DEMO SESSION ENDED";
    label(status,8,190,1,palette::muted);
    bool armed=preview&&preview->stage==PlayerPreview::Stage::Ready&&!preview->gpsLost&&!preview->linkLost;
    box(layout::fire,armed?palette::amber:palette::dim);
    label("FIRE",15,213,2,armed?palette::amber:palette::muted);
    const char* item=armed?"SHELL / SIMULATED":preview?(preview->stage==PlayerPreview::Stage::Used?"USED / SIMULATED":"NO ITEM / SIMULATED"):"UNAVAILABLE / NO ITEM DATA";
    label(item,86,216,1,armed?palette::amber:palette::muted);
  }
  void dash(const State& state,uint32_t now,const char* notice,int heldMode,uint32_t holdMs,bool holdFired) {
    const auto& k=state.karts[state.self];const bool live=state.live(now),vesc=live&&k.vesc;
    const float speedMph=gpsMph(state,now);const bool speed=std::isfinite(speedMph);
    int mph=speed?int(std::lround(speedMph)):-1;
    label("VELOCITY",12,31,1,palette::muted);
    digit(mph<0?-1:mph/10,12,52,42,63,speed?palette::cyan:palette::dim);
    digit(mph<0?-1:mph%10,64,52,42,63,speed?palette::cyan:palette::dim);
    label("MPH",116,90,1,palette::amber);label("GPS SPEED",12,123,1,palette::muted);
    c.drawLine(156,76,156,175,palette::line);
    char b[40];
    label("BATTERY",169,77,1,palette::muted);number(vesc?k.volts:NAN,"V",b,sizeof b);label(b,169,89,2,palette::cyan);
    label("ESC TEMP",169,111,1,palette::muted);number(vesc?k.escC:NAN,"C",b,sizeof b,0);label(b,169,123,2);
    label("POWER",169,145,1,palette::muted);number(vesc?k.volts*k.battA:NAN,"W",b,sizeof b,0);label(b,169,157,2);
    number(vesc?k.motorA:NAN,"A MOTOR",b,sizeof b);label(b,12,145,1);
    number(vesc?k.battA:NAN,"A BAT",b,sizeof b);label(b,12,161,1);
    const char* names[3]={"ECO","NORMAL","SPORT"};
    if(vesc&&k.confirmed&&k.mode>=0)std::snprintf(b,sizeof b,"%s VERIFIED / %d SATS",names[k.mode],k.sats);
    else std::snprintf(b,sizeof b,"%s",!live?"HELTEC DATA LOST":!k.vesc?"VESC DISCONNECTED":"MODE UNVERIFIED");
    label(b,10,180,1,vesc&&k.confirmed?palette::cyan:palette::amber);
    label(notice?notice:"",8,191,1,palette::muted);
    for(int i=0;i<3;++i){int x=i*107;bool selected=vesc&&k.confirmed&&k.mode==i;
      box({x+2,202,102,36},selected?palette::modes[i]:palette::dim);
      label(names[i],x+10,208,1,selected?palette::modes[i]:palette::muted);
      if(!state.metadataFresh(now)||!std::isfinite(state.cap[i]))std::snprintf(b,sizeof b,"CAP ?");
      else if(state.cap[i]==0)std::snprintf(b,sizeof b,"UNCAPPED");else std::snprintf(b,sizeof b,"%.0f MPH",state.cap[i]);
      label(b,x+10,223,1,palette::muted);
      if(i==heldMode&&!holdFired)c.fillRect(x+4,235,std::min(98,int(uint32_t(now-holdMs)*98/650)),2,palette::cyan);
    }
  }
  void invitation(const PlayerPreview& p,uint32_t now) {
    if(!p.overlay)return;
    box({12,69,296,118},palette::amber);
    label("KART 2 / GAME PREVIEW",24,80,1,palette::amber);
    const char* line="Download course and join?";
    if(p.stage==PlayerPreview::Stage::Downloading)line="SIMULATED COURSE DOWNLOAD";
    else if(p.stage==PlayerPreview::Stage::Ready||p.stage==PlayerPreview::Stage::Used)line="Joined / simulated course cached";
    else if(p.stage==PlayerPreview::Stage::TransferError)line="Download failed / old course kept";
    label(line,24,101,1);
    if(p.stage==PlayerPreview::Stage::Downloading){c.drawRect(24,121,272,8,palette::line);c.fillRect(25,122,int(p.progress(now)*270/100),6,palette::cyan);}
    label("(c) OpenStreetMap contributors",24,132,1,palette::muted);
    box(layout::close);label("CLOSE",58,158,1);
    box(layout::join,p.stage==PlayerPreview::Stage::Downloading?palette::dim:palette::amber);
    label(p.stage==PlayerPreview::Stage::Downloading?"WAIT":p.stage==PlayerPreview::Stage::Ready||p.stage==PlayerPreview::Stage::Used?"LEAVE":"JOIN",215,158,1,palette::amber);
  }
public:
  explicit DriverView(Canvas& canvas):c(canvas){}
  void draw(const State& state,const Course& course,uint32_t now,bool mapPage,bool demo,bool beginner,
            const char* notice=nullptr,int heldMode=-1,uint32_t holdMs=0,bool holdFired=false,const PlayerPreview* preview=nullptr) {
    c.fillScreen(palette::bg);char b[54];const auto& k=state.karts[state.self];
    std::snprintf(b,sizeof b,"KART %02u",unsigned(state.self));label(b,9,7,1,palette::cyan);
    if(demo)std::snprintf(b,sizeof b,"DEMO / NO OUTPUT");
    else if(!state.live(now))std::snprintf(b,sizeof b,"LINK LOST");
    else std::snprintf(b,sizeof b,"LIVE  PIT %s  RF %s",state.metadataFresh(now)?(state.pit?"+":"-"):"?",state.metadataFresh(now)?(state.radio?"+":"-"):"?");
    label(b,112,7,1,demo?palette::amber:palette::muted);
    c.drawLine(0,21,319,21,palette::line);
    if(mapPage)map(state,course,now,preview);else dash(state,now,notice,heldMode,holdMs,holdFired);
    navigation(mapPage,now,preview);if(preview)invitation(*preview,now);
    // Controller restrictions/faults remain visible on either page and above game overlays.
    const char* alert=nullptr;
    if(state.live(now)&&k.vesc){
      if(k.stopped)alert="PIT STOP ACTIVE";
      else if(k.slow){std::snprintf(b,sizeof b,"PIT SLOW / %d MPH",k.slow);alert=b;}
      else if(!beginner&&k.fault>0){std::snprintf(b,sizeof b,"VESC FAULT %d",k.fault);alert=b;}
    }
    if(alert){c.fillRect(0,173,320,25,palette::bad);label(alert,10,181,1,palette::bg);}
  }
};
}
