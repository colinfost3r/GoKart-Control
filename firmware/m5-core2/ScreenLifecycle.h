#pragma once
#include "PlayerPreview.h"
namespace m5dash {
// Neither timer owns transport or driving state. Wrap-safe, nonblocking UI only.
class StartupScreen {
  bool enabled=false;uint32_t began=0;
public:
  void begin(uint32_t now){enabled=true;began=now;}
  bool visible(uint32_t now){if(enabled&&uint32_t(now-began)>=5000)enabled=false;return enabled;}
};
class PageHold {
  bool tracking=false,cancelled=false,fired=false;uint32_t began=0;
public:
  void begin(uint32_t now){tracking=true;cancelled=fired=false;began=now;}
  void reset(){tracking=false;}
  bool maintenance(int x,int y,uint32_t now){
    if(!tracking||fired)return false;
    if(!layout::page.contains(x,y))cancelled=true;
    if(cancelled||uint32_t(now-began)<1800)return false;
    fired=true;return true;
  }
};
}
