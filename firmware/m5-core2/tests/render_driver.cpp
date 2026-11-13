// Off-device visual fixture for the production renderer; never opens a device or radio.
#include "DriverView.h"
#include <iostream>
#include <string>
#include <sstream>
#include <iomanip>
#include <fstream>
#include <vector>

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
  // Live scenes without a preview: "live-manresa" follows a fix on the island; "site-shop" and
  // "site-manresa" have no fix and no course, so the remembered site is shown instead.
  int homeSite=-1;double baseLat=41.0938,baseLon=-73.4163;
  const bool siteOnly=!std::strncmp(scene,"site-",5);
  if(!std::strcmp(scene,"site-shop"))homeSite=0;
  if(!std::strcmp(scene,"site-manresa"))homeSite=1;
  if(!std::strcmp(scene,"live-manresa")){baseLat=41.0748;baseLon=-73.4101;}
  m5dash::Course course;course.closed=true;course.count=48;std::snprintf(course.name,sizeof course.name,"DEMO LOOP / NOT A SURVEYED COURSE");
  for(size_t i=0;i<48;++i){double a=i*6.283185307179586/48;course.lat[i]=baseLat+0.0003*std::sin(a);course.lon[i]=baseLon+0.0005*std::cos(a);}
  for(unsigned i=1;i<=8;++i){auto& k=state.karts[i];double a=phase+m5dash::PreviewMap::kartPhase(i);
    k.seen=true;k.received=now;k.vesc=true;k.confirmed=true;k.mode=1;k.fault=0;k.fix=true;k.fixReported=true;k.hasPosition=true;k.fixReceived=now;k.sats=10;
    k.lat=baseLat+0.0003*std::sin(a);k.lon=baseLon+0.0005*std::cos(a);k.gpsKph=22;k.volts=79.4;k.motorA=12;k.battA=4;k.escC=32;
  }
  if(p.gpsLost)state.karts[3].fix=false;
  if(p.linkLost){for(auto& k:state.karts)k.received=now-6000;state.metaMs=now-6000;}
  if(!std::strcmp(scene,"no-course")||!std::strcmp(scene,"live-manresa")||siteOnly)course.count=0;
  if(siteOnly)for(auto& k:state.karts)k.fix=false;
  if(!std::strcmp(scene,"fault"))state.karts[3].fault=5;
  if(!std::strcmp(scene,"stopped"))state.karts[3].stopped=true;
  if(!std::strcmp(scene,"slow"))state.karts[3].slow=5;
  // Pit race scenes, as the own Heltec would report them: grid hold, GO, running, finished.
  const bool raceScene=!std::strncmp(scene,"race-",5);
  if(!std::strcmp(scene,"race-grid")){state.raceHold=true;state.raceGoAt=now+3400;}
  if(!std::strcmp(scene,"race-grid-long")){state.raceHold=true;state.raceGoAt=now+11200;}
  if(!std::strcmp(scene,"race-go")){state.raceWent=true;state.raceWentAt=now-400;}
  if(!std::strcmp(scene,"race-running")){state.raceState=2;state.racePos=2;}
  if(!std::strcmp(scene,"race-finished")){state.raceState=3;state.racePos=1;}
  if(!std::strcmp(scene,"race-stopped")){state.raceHold=true;state.raceGoAt=now+3400;state.karts[3].stopped=true;}
  bool live=!std::strncmp(scene,"live",4)||siteOnly||raceScene;
  m5dash::LiveGame game;m5game::share::Receiver receiver;
  bool native=argc>4&&!std::strncmp(scene,"native-",7);
  if(native){
    std::ifstream f(argv[4],std::ios::binary);std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)),{});
    if(!game.load(bytes.data(),bytes.size()))return 2;course=game.course;
    // "native-there": every kart at the package's first course point, wherever that is.
    if(!std::strcmp(scene,"native-there"))for(auto& k:state.karts){k.lat=course.lat[0];k.lon=course.lon[0];}
    state.gameVersion=m5game::GAME_VERSION;state.gameReady=true;state.token=123;state.gameSession=game.package.host();state.hosts=state.courseHosts=1u<<(state.gameSession-1);
    state.hostCourse[state.gameSession]=game.package.digest();state.hostBoot[state.gameSession]=game.courseBoot=222;
    for(auto&k:state.karts)k.session=state.gameSession;
    game.stage=m5dash::LiveGame::Stage::Playing;game.collect(m5dash::LiveGame::Item::Shell);
    if(!std::strcmp(scene,"native-join")){game.stage=m5dash::LiveGame::Stage::Idle;game.overlay=true;game.note="Download course and join?";m5game::share::Message offer;offer.kind=m5game::share::Kind::Offer;offer.host=2;offer.boot=222;offer.digest=game.package.digest();offer.size=game.package.size();receiver.receive(offer,now);}
    if(!std::strcmp(scene,"native-lost")){game.fail("Host course changed or lost");}
  }
  std::cout<<"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480' viewBox='0 0 320 240'>\n";
  SvgCanvas canvas;m5dash::DriverView<SvgCanvas> view(canvas);
  if(!std::strcmp(scene,"startup"))view.startup(true);
  else if(native)view.draw(state,course,now,map,false,false,"Hold a mode button to request",-1,0,false,nullptr,&game,&receiver,homeSite);
  else view.draw(state,course,now,map,!live,false,live?"Hold a mode button to request":"Mode controls disabled in demo",-1,0,false,live?nullptr:&p,nullptr,nullptr,homeSite);
  std::cout<<"</svg>\n";
}
