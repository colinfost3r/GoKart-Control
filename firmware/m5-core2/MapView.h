#pragma once
#include "DisplayState.h"
#include <cmath>
#include <algorithm>

namespace m5dash {
// North-up local projection. Distant peers/course points never change follow zoom.
struct MapView {
  double lat=0,lon=0,pixelsPerMeter=1;
  int left=2,top=23,width=316,height=164;
  bool valid=false,following=false;
  static MapView make(const State& state,const Course& course,uint32_t now,double spanMeters=70) {
    MapView v;
    if(!std::isfinite(spanMeters)||spanMeters<20||spanMeters>500)spanMeters=70;
    const auto& own=state.karts[state.self];
    if(state.self&&state.live(now)&&own.positionFresh(now)) {v.lat=own.lat;v.lon=own.lon;v.following=true;v.valid=true;}
    else if(course.count) {
      // Without our own fix show the available course, never follow another kart.
      Bounds b;for(size_t i=0;i<course.count;++i)b.add(course.lat[i],course.lon[i]);
      v.lat=b.lat0+(b.minY+b.maxY)/2/111320.0;
      double cosine=std::max(.0001,std::cos(b.lat0*3.141592653589793/180));
      v.lon=b.lon0+(b.minX+b.maxX)/2/(111320.0*cosine);
      v.pixelsPerMeter=std::min((v.width-16)/std::max(40.0,b.maxX-b.minX),(v.height-16)/std::max(40.0,b.maxY-b.minY));
      v.valid=true;return v;
    }
    if(v.valid)v.pixelsPerMeter=v.height/spanMeters;
    return v;
  }
  bool project(double latitude,double longitude,double& x,double& y) const {
    if(!valid||!location(latitude,longitude))return false;
    double dl=longitude-lon;while(dl>180)dl-=360;while(dl< -180)dl+=360;
    x=left+width/2.0+dl*111320.0*std::cos(lat*3.141592653589793/180)*pixelsPerMeter;
    y=top+height/2.0-(latitude-lat)*111320.0*pixelsPerMeter;
    return std::isfinite(x)&&std::isfinite(y);
  }
  bool contains(double x,double y,int margin=0) const {
    return x>=left+margin&&x<=left+width-1-margin&&y>=top+margin&&y<=top+height-1-margin;
  }
  // Liang-Barsky clipping before integer conversion/drawing: no offscreen giant
  // coordinates, no course line crossing the FIRE or navigation UI.
  bool clip(double& x0,double& y0,double& x1,double& y1) const {
    if(!std::isfinite(x0)||!std::isfinite(y0)||!std::isfinite(x1)||!std::isfinite(y1))return false;
    double dx=x1-x0,dy=y1-y0,lo=0,hi=1;
    const double p[4]={-dx,dx,-dy,dy},q[4]={x0-left,left+width-1-x0,y0-top,top+height-1-y0};
    for(int i=0;i<4;++i){
      if(p[i]==0){if(q[i]<0)return false;continue;}
      double r=q[i]/p[i];
      if(p[i]<0)lo=std::max(lo,r);else hi=std::min(hi,r);
      if(lo>hi)return false;
    }
    double ox=x0,oy=y0;x0=ox+lo*dx;y0=oy+lo*dy;x1=ox+hi*dx;y1=oy+hi*dy;
    x0=std::max(double(left),std::min(double(left+width-1),x0));x1=std::max(double(left),std::min(double(left+width-1),x1));
    y0=std::max(double(top),std::min(double(top+height-1),y0));y1=std::max(double(top),std::min(double(top+height-1),y1));return true;
  }
};
}
