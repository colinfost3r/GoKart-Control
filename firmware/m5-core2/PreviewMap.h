#pragma once
#include "MapView.h"

namespace m5dash {
// Compiled shop-area artwork for the no-output rehearsal only. Real game-package
// background/zone loading is separate work. Coordinates share MapView's projection.
struct PreviewMap {
  static double kartPhase(unsigned id){return id*0.78+(id==2?0.29:0);}
  struct Line {int16_t x0,y0,x1,y1;uint8_t kind;};
  inline static constexpr Line lines[]={
#include "preview_shop_lines.inc"
  };
  template<class Canvas> static void draw(Canvas& c,const MapView& v) {
    if(!v.valid)return;
    constexpr double originLat=41.0938,originLon=-73.4163;
    const double cosine=std::cos(originLat*3.141592653589793/180);
    for(const auto& l:lines){
      double x0,y0,x1,y1;
      if(!v.project(originLat+l.y0/10.0/111320,originLon+l.x0/10.0/(111320*cosine),x0,y0)||
         !v.project(originLat+l.y1/10.0/111320,originLon+l.x1/10.0/(111320*cosine),x1,y1))continue;
      // Quiet buildings, broader roads, muted water/rail outlines; actual OSM geometry.
      const uint16_t ink=l.kind==2?0x5b6f:l.kind==1?0x3a0a:l.kind==0?0x222b:0x39e8;
      for(int offset=l.kind==2?-1:0;offset<=(l.kind==2?1:0);++offset){
        double ax=x0,ay=y0+offset,bx=x1,by=y1+offset;
        if(v.clip(ax,ay,bx,by))c.drawLine(lround(ax),lround(ay),lround(bx),lround(by),ink);
      }
    }
  }
};
}
