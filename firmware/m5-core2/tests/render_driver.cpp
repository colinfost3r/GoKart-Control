// Off-device visual fixture for the production renderer; never opens a device or radio.
#include "DriverView.h"
#include <iostream>
#include <string>
#include <sstream>
#include <iomanip>

static std::string color(uint16_t c) {
  unsigned r=(c>>11)&31,g=(c>>5)&63,b=c&31;
  std::ostringstream s;s<<'#'<<std::hex<<std::setfill('0')<<std::setw(2)<<((r*255+15)/31)
    <<std::setw(2)<<((g*255+31)/63)<<std::setw(2)<<((b*255+15)/31);return s.str();
}
static std::string escape(const char* text) {
  std::string r;for(const char* p=text;*p;++p)switch(*p){case '&':r+="&amp;";break;case '<':r+="&lt;";break;case '>':r+="&gt;";break;default:r+=*p;}
  return r;
}
struct SvgCanvas {
  uint16_t ink=0;int size=1,x=0,y=0;
  void rect(int xx,int yy,int w,int h,int radius,uint16_t c,bool fill) {
    std::cout<<"<rect x='"<<xx<<"' y='"<<yy<<"' width='"<<w<<"' height='"<<h<<"' rx='"<<radius
      <<"' fill='"<<(fill?color(c):"none")<<"' stroke='"<<(fill?"none":color(c))<<"'/>\n";
  }
  void fillRect(int xx,int yy,int w,int h,uint16_t c){rect(xx,yy,w,h,0,c,true);}
  void drawRect(int xx,int yy,int w,int h,uint16_t c){rect(xx,yy,w,h,0,c,false);}
  void fillScreen(uint16_t c){fillRect(0,0,320,240,c);}
  void fillRoundRect(int xx,int yy,int w,int h,int r,uint16_t c){rect(xx,yy,w,h,r,c,true);}
  void drawRoundRect(int xx,int yy,int w,int h,int r,uint16_t c){rect(xx,yy,w,h,r,c,false);}
  void drawLine(int x0,int y0,int x1,int y1,uint16_t c){std::cout<<"<path d='M"<<x0<<' '<<y0<<" L"<<x1<<' '<<y1<<"' stroke='"<<color(c)<<"'/>\n";}
  void circle(int xx,int yy,int r,uint16_t c,bool fill){std::cout<<"<circle cx='"<<xx<<"' cy='"<<yy<<"' r='"<<r<<"' fill='"<<(fill?color(c):"none")<<"' stroke='"<<(fill?"none":color(c))<<"'/>\n";}
  void fillCircle(int xx,int yy,int r,uint16_t c){circle(xx,yy,r,c,true);}
  void drawCircle(int xx,int yy,int r,uint16_t c){circle(xx,yy,r,c,false);}
  void setTextColor(uint16_t c){ink=c;}
  void setTextSize(int n){size=n;}
  void setCursor(int xx,int yy){x=xx;y=yy;}
  void print(const char* text){if(!*text)return;std::cout<<"<text x='"<<x<<"' y='"<<y+7*size<<"' fill='"<<color(ink)
    <<"' font-family='Menlo,DejaVu Sans Mono,monospace' font-size='"<<8*size<<"' textLength='"<<6*size*std::strlen(text)
    <<"' lengthAdjust='spacingAndGlyphs'>"<<escape(text)<<"</text>\n";}
};
int main(int argc,char** argv){
  const char* scene=argc>1?argv[1]:"invite";
  bool map=argc<=2||std::strcmp(argv[2],"dash");
  const unsigned now=10000;const double phase=argc>3?std::atoi(argv[3])/12.0:0;
  m5dash::PlayerPreview p;p.scenario(scene,now);
  if(!std::strcmp(scene,"invitation"))p.open();
  if(!std::strcmp(scene,"joined")){p.stage=m5dash::PlayerPreview::Stage::Ready;p.open();}
  if(!std::strcmp(scene,"download"))p.since=now-1500;
  m5dash::State state;state.self=3;state.boot=1;state.metaSeen=true;state.metaMs=now;state.radio=true;state.pit=true;
  state.cap[0]=15;state.cap[1]=25;state.cap[2]=0;
  m5dash::Course course;course.closed=true;course.count=48;std::snprintf(course.name,sizeof course.name,"DEMO LOOP / NOT A SURVEYED COURSE");
  for(size_t i=0;i<48;++i){double a=i*6.283185307179586/48;course.lat[i]=41.0938+0.0003*std::sin(a);course.lon[i]=-73.4163+0.0005*std::cos(a);}
  for(unsigned i=1;i<=8;++i){auto& k=state.karts[i];double a=phase+m5dash::PreviewMap::kartPhase(i);
    k.seen=true;k.received=now;k.vesc=true;k.confirmed=true;k.mode=1;k.fault=0;k.fix=true;k.fixReported=true;k.hasPosition=true;k.fixReceived=now;k.sats=10;
    k.lat=41.0938+0.0003*std::sin(a);k.lon=-73.4163+0.0005*std::cos(a);k.gpsKph=22;k.volts=79.4;k.motorA=12;k.battA=4;k.escC=32;
  }
  if(p.gpsLost)state.karts[3].fix=false;
  if(p.linkLost){for(auto& k:state.karts)k.received=now-6000;state.metaMs=now-6000;}
  if(!std::strcmp(scene,"no-course"))course.count=0;
  if(!std::strcmp(scene,"fault"))state.karts[3].fault=5;
  if(!std::strcmp(scene,"stopped"))state.karts[3].stopped=true;
  if(!std::strcmp(scene,"slow"))state.karts[3].slow=5;
  bool live=!std::strcmp(scene,"live");
  std::cout<<"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480' viewBox='0 0 320 240'>\n";
  SvgCanvas canvas;m5dash::DriverView<SvgCanvas> view(canvas);
  if(!std::strcmp(scene,"startup"))view.startup(true);
  else view.draw(state,course,now,map,!live,false,live?"Hold a mode button to request":"Mode controls disabled in demo",-1,0,false,live?nullptr:&p);
  std::cout<<"</svg>\n";
}
