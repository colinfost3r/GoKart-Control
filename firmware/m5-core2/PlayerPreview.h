#pragma once
// Pure UI rehearsal. No transport, VESC, filesystem or production game authority.
#include <cstdint>
#include <cstring>

namespace m5dash {
struct HitRect {
  int x,y,w,h;
  bool contains(int px,int py) const { return px>=x&&px<x+w&&py>=y&&py<y+h; }
};
namespace layout {
constexpr HitRect page{258,26,58,40}, invite{214,26,40,40};
constexpr HitRect close{20,145,132,36}, join{168,145,132,36};
constexpr HitRect fire{4,202,312,36};
}
class PlayerPreview {
public:
  enum class Stage { Invite, Downloading, Ready, Used, TransferError, HostLost };
  Stage stage=Stage::Invite;
  bool overlay=false,acknowledged=false,gpsLost=false,linkLost=false;
  uint32_t since=0;
  unsigned fired=0;
  bool available() const { return stage!=Stage::HostLost&&!linkLost; }
  bool notify(uint32_t now) const { return available()&&stage==Stage::Invite&&!acknowledged&&((now/500)%2==0); }
  unsigned progress(uint32_t now) const {
    return stage==Stage::Downloading ? (uint32_t(now-since)>=3000?100:unsigned(uint32_t(now-since)/30)) : 0;
  }
  void tick(uint32_t now) {
    if(stage==Stage::Downloading && uint32_t(now-since)>=3000) {stage=Stage::Ready;overlay=false;}
  }
  void open() { if(available()){overlay=true;acknowledged=true;} }
  // Coordinates are display-space, shared with the real renderer.
  bool tap(int x,int y,uint32_t now) {
    if(overlay) {
      if(layout::close.contains(x,y)){overlay=false;return true;}
      if(layout::join.contains(x,y)&&available()) {
        if(stage==Stage::Invite||stage==Stage::TransferError){stage=Stage::Downloading;since=now;}
        else if(stage==Stage::Ready||stage==Stage::Used){stage=Stage::Invite;overlay=false;}
      }
      return true; // Modal input cannot leak to a mode button or FIRE.
    }
    if(layout::invite.contains(x,y)&&available()){open();return true;}
    return false;
  }
  void fire(uint32_t now) {
    if(!overlay&&stage==Stage::Ready&&!linkLost&&!gpsLost){stage=Stage::Used;since=now;++fired;}
  }
  bool scenario(const char* name,uint32_t now) {
    PlayerPreview next;
    if(!std::strcmp(name,"invite")){}
    else if(!std::strcmp(name,"download")){next.stage=Stage::Downloading;next.overlay=true;next.acknowledged=true;}
    else if(!std::strcmp(name,"ready")){next.stage=Stage::Ready;next.acknowledged=true;}
    else if(!std::strcmp(name,"used")){next.stage=Stage::Used;next.acknowledged=true;next.fired=1;}
    else if(!std::strcmp(name,"download-error")){next.stage=Stage::TransferError;next.overlay=true;next.acknowledged=true;}
    else if(!std::strcmp(name,"host-lost")){next.stage=Stage::HostLost;}
    else if(!std::strcmp(name,"gps-lost")){next.gpsLost=true;}
    else if(!std::strcmp(name,"link-lost")){next.linkLost=true;}
    else return false;
    next.since=now;*this=next;return true;
  }
};
}
