// Built-in site street lines: data sanity, culling against an unculled reference, the
// no-position overview and the remembered site. Host test; no device, radio or storage.
#include "SiteMap.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <vector>
using namespace m5dash;

struct Stroke {long x0,y0,x1,y1;uint16_t ink;};
struct Recorder {
  std::vector<Stroke> lines;
  void drawLine(long x0,long y0,long x1,long y1,uint16_t ink){lines.push_back({x0,y0,x1,y1,ink});}
};
static bool near(const Stroke& a,const Stroke& b){
  return a.ink==b.ink&&std::labs(a.x0-b.x0)<=1&&std::labs(a.y0-b.y0)<=1&&std::labs(a.x1-b.x1)<=1&&std::labs(a.y1-b.y1)<=1;
}
// Slow reference: every stored line of every site through MapView::project, nothing skipped.
static std::vector<Stroke> reference(const MapView& v){
  Recorder r;
  for(const Site& s:sites){
    const double cosine=std::cos(s.lat*3.141592653589793/180);
    for(size_t i=0;i<s.count;++i){const SiteLine& l=s.lines[i];double x0,y0,x1,y1;
      if(!v.project(s.lat+l.y0/10.0/111320,s.lon+l.x0/10.0/(111320*cosine),x0,y0)||
         !v.project(s.lat+l.y1/10.0/111320,s.lon+l.x1/10.0/(111320*cosine),x1,y1))continue;
      SiteMap::stroke(r,v,x0,y0,x1,y1,l.kind);
    }
  }
  return r.lines;
}
static MapView follow(double lat,double lon,double span=70){
  MapView v;v.lat=lat;v.lon=lon;v.valid=v.following=true;v.pixelsPerMeter=v.height/span;return v;
}
// A single pixel on a screen edge. The fast path works in single precision, so a line that
// only touches an edge at one point may be kept by one path and clipped away by the other.
// Longer strokes along an edge get no allowance: losing those is a culling fault.
static bool edge(const Stroke& s){
  const bool onEdge=(s.x0<=1&&s.x1<=1)||(s.x0>=318&&s.x1>=318)||(s.y0<=1&&s.y1<=1)||(s.y0>=238&&s.y1>=238);
  return onEdge&&std::labs(s.x1-s.x0)<=1&&std::labs(s.y1-s.y0)<=1;
}
// The fast path must draw what the reference draws: the same strokes in the same order,
// within one pixel of rounding, except for strokes that only touch a screen edge.
static size_t same(const MapView& v,bool expectCharted){
  Recorder fast;const bool charted=SiteMap::draw(fast,v);assert(charted==expectCharted);
  const auto slow=reference(v);
  size_t i=0,j=0,skipped=0;
  while(i<fast.lines.size()||j<slow.size()){
    if(i<fast.lines.size()&&j<slow.size()&&near(fast.lines[i],slow[j])){++i;++j;}
    else if(j<slow.size()&&edge(slow[j])){++j;++skipped;}
    else if(i<fast.lines.size()&&edge(fast.lines[i])){++i;++skipped;}
    else {
      std::printf("view %.6f,%.6f at %.3f px/m: stroke %zu of %zu differs from reference %zu of %zu\n",v.lat,v.lon,v.pixelsPerMeter,i,fast.lines.size(),j,slow.size());
      assert(false);
    }
  }
  assert(skipped<=4);   // a handful at most; anything more is a culling fault, not rounding
  for(const auto& s:fast.lines)assert(s.x0>=0&&s.x0<=319&&s.x1>=0&&s.x1<=319&&s.y0>=0&&s.y0<=239&&s.y1>=0&&s.y1<=239);
  return fast.lines.size();
}
struct Memory {
  bool has=false,fail=false;uint8_t value=0;unsigned writes=0;
  bool read(uint8_t& out){if(!has)return false;out=value;return true;}
  bool write(uint8_t v){++writes;if(fail)return false;has=true;value=v;return true;}
};

int main(){
  assert(SiteMap::count==2);
  const Site& shop=sites[0];const Site& manresa=sites[1];
  assert(!std::strcmp(shop.name,"SHOP")&&!std::strcmp(manresa.name,"MANRESA"));
  // Stored data: inside its rectangle, drawable kinds only, no empty strokes, bounded size.
  size_t total=0;
  for(const Site& s:sites){
    assert(s.count>0&&s.count<=6000&&s.halfEast>0&&s.halfNorth>0&&s.overviewMeters>=20);
    assert(std::strlen(s.name)<=12&&location(s.lat,s.lon));
    for(size_t i=0;i<s.count;++i){const SiteLine& l=s.lines[i];
      assert(std::abs(l.x0)<=s.halfEast&&std::abs(l.x1)<=s.halfEast&&std::abs(l.y0)<=s.halfNorth&&std::abs(l.y1)<=s.halfNorth);
      assert(l.kind<=3&&(l.x0!=l.x1||l.y0!=l.y1));
    }
    total+=s.count;
  }
  // Sites never overlap, so a position belongs to at most one.
  double east,north;SiteMap::local(shop,manresa.lat,manresa.lon,east,north);
  assert(std::fabs(east)>shop.halfEast+manresa.halfEast||std::fabs(north)>shop.halfNorth+manresa.halfNorth);

  assert(SiteMap::containing(shop.lat,shop.lon)==0&&SiteMap::containing(manresa.lat,manresa.lon)==1);
  assert(SiteMap::containing((shop.lat+manresa.lat)/2,(shop.lon+manresa.lon)/2)==-1);
  assert(SiteMap::containing(0,0)==-1&&SiteMap::containing(NAN,-73.4)==-1&&SiteMap::containing(91,-73.4)==-1);
  const double metre=1/111320.0,shopEast=metre/std::cos(shop.lat*3.141592653589793/180);
  assert(SiteMap::containing(shop.lat+299*metre,shop.lon)==0&&SiteMap::containing(shop.lat+301*metre,shop.lon)==-1);
  assert(SiteMap::containing(shop.lat,shop.lon-299*shopEast)==0&&SiteMap::containing(shop.lat,shop.lon-301*shopEast)==-1);
  assert(!SiteMap::get(-1)&&!SiteMap::get(SiteMap::count)&&SiteMap::get(1)==&manresa);

  // Following a fix: only nearby lines are drawn, and they match the unculled reference.
  const size_t atShop=same(follow(shop.lat,shop.lon),true);
  const size_t atManresa=same(follow(manresa.lat,manresa.lon),true);
  assert(atShop>20&&atShop<total/4&&atManresa>0&&atManresa<total/4);
  same(follow(shop.lat,shop.lon,20),true);same(follow(shop.lat,shop.lon,500),true);
  same(follow(shop.lat+120*metre,shop.lon-200*shopEast),true);
  same(follow(manresa.lat-600*metre,manresa.lon+500*shopEast),true);
  // Just outside a site its edge is still on screen, but the view is no longer covered by it.
  assert(same(follow(shop.lat,shop.lon+310*shopEast),false)>0);
  // Well outside every site: nothing is drawn.
  assert(same(follow(shop.lat,shop.lon+400*shopEast),false)==0);
  assert(same(follow(shop.lat+400*metre,shop.lon),false)==0);
  assert(same(follow(0,0),false)==0&&same(follow(41.2,-73.0),false)==0);

  // No position to follow: the whole-site view is valid, follows nothing and stays on screen.
  for(int i=0;i<SiteMap::count;++i){
    const MapView v=SiteMap::overview(i);
    assert(v.valid&&!v.following&&v.lat==sites[i].lat&&v.lon==sites[i].lon);
    assert(std::fabs(v.pixelsPerMeter*sites[i].overviewMeters-v.height)<1e-9);
    assert(same(v,true)>100);
  }
  assert(!SiteMap::overview(-1).valid&&!SiteMap::overview(SiteMap::count).valid);
  // An unusable view draws nothing and reports no cover.
  Recorder none;MapView bad;assert(!SiteMap::draw(none,bad));
  bad=follow(shop.lat,shop.lon);bad.pixelsPerMeter=0;assert(!SiteMap::draw(none,bad));
  bad=follow(NAN,shop.lon);assert(!SiteMap::draw(none,bad));
  bad=follow(shop.lat,shop.lon);bad.pixelsPerMeter=NAN;assert(!SiteMap::draw(none,bad));
  assert(none.lines.empty());

  // Remembered site: defaults to the first, follows real positions, writes only on a change.
  HomeSite<Memory> home;home.load();assert(home.site==0&&home.backend.writes==0);
  assert(!home.seen(shop.lat,shop.lon)&&home.backend.writes==0);          // already there
  assert(!home.seen(41.2,-73.0)&&!home.seen(NAN,NAN)&&home.site==0&&home.backend.writes==0);   // nowhere known
  assert(home.seen(manresa.lat,manresa.lon)&&home.site==1&&home.backend.writes==1&&home.backend.value==1);
  assert(!home.seen(manresa.lat+10*metre,manresa.lon)&&home.backend.writes==1);
  HomeSite<Memory> restarted;restarted.backend=home.backend;restarted.load();assert(restarted.site==1);
  HomeSite<Memory> corrupt;corrupt.backend.has=true;corrupt.backend.value=9;corrupt.load();assert(corrupt.site==0);
  // A failed write is not retried every frame, and the display still shows where the kart is.
  HomeSite<Memory> failing;failing.backend.fail=true;failing.load();
  assert(failing.seen(manresa.lat,manresa.lon)&&failing.site==1&&failing.backend.writes==1);
  assert(!failing.seen(manresa.lat,manresa.lon)&&failing.backend.writes==1);

  std::printf("site map passed: %zu lines in %d sites; %zu drawn at the shop, %zu on the island\n",total,SiteMap::count,atShop,atManresa);
}
