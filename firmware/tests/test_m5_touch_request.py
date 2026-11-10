"""Exercise production Core2 touch/request functions; mocked touch/radio, no hardware."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


def function(source, signature):
    start=source.index(signature)
    match=re.search(r'^}',source[start:],re.M)
    if not match:raise AssertionError('Production function end missing')
    return source[start:start+match.end()]


class TouchRequestTests(unittest.TestCase):
    def test_busy_hold_is_visible_not_deferred_and_send_refusal_is_not_pending(self):
        source=(ROOT/'firmware/m5-core2/m5-core2.ino').read_text()
        include=next((p for p in [Path(os.environ.get('ARDUINOJSON_DIR','/nonexistent')),
            Path('/private/tmp/gokart-arduino/user/libraries/ArduinoJson/src'),
            Path.home()/'Arduino/libraries/ArduinoJson/src',
            Path.home()/'Documents/Arduino/libraries/ArduinoJson/src'] if (p/'ArduinoJson.h').exists()),None)
        self.assertIsNotNone(include,'ArduinoJson required')
        harness=r'''
#include <cassert>
#include <cstring>
#include "DisplayState.h"
#define M5_USE_ESPNOW 1
#define M5_DEMO 0
#define M5_MODE_HOLD_MS 650
m5dash::State state;
const char* localModeNotice=nullptr;uint32_t localModeNoticeMs=0;
uint32_t requestId=10,holdMs=0,touchPresses=0,headerHoldMs=0;
int heldMode=-1,touchX=-1,touchY=-1;
bool holdFired=false,maintenanceMenu=false,headerHolding=false,mapPage=false,onlineOnly=true;
struct TabRect {int x,y,w,h;bool contains(int px,int py)const{return px>=x&&px<x+w&&py>=y&&py<y+h;}};
constexpr TabRect tabs[3]={{4,23,94,40},{103,23,94,40},{202,23,114,40}};
struct Detail {int x=40,y=220;bool down=false,edge=false;bool wasPressed()const{return edge;}bool isPressed()const{return down;}};
struct FakeTouch {Detail detail;Detail getDetail()const{return detail;}};
struct Device {FakeTouch Touch;} M5;
struct Maintenance {bool on=false;bool active()const{return on;}bool updating()const{return false;}bool restarting()const{return false;}void stop(){on=false;}void start(){on=true;}} maintenance;
struct Radio {
  bool available=true,accept=true;int calls=0;char sent[48]{};
  bool canSend(uint32_t)const{return available;}
  bool sendLine(const char* p,uint32_t){++calls;std::strcpy(sent,p);return accept;}
  void setChannelSearchEnabled(bool){}
} wireless;
void ready(uint32_t now){state.self=3;state.karts[3].seen=true;state.karts[3].received=now;state.karts[3].vesc=true;state.metaSeen=true;state.metaMs=now;state.modeReady=true;state.token=123;}
void press(){M5.Touch.detail.down=true;M5.Touch.detail.edge=true;}
void held(){M5.Touch.detail.edge=false;}
void release(){M5.Touch.detail.down=false;M5.Touch.detail.edge=false;}
'''
        harness+=function(source,'static void requestWirelessMode(')+'\n'+function(source,'void touch(')
        harness+=r'''
int main(){
  ready(100);press();touch(100);held();ready(749);touch(749);
  assert(!holdFired&&wireless.calls==0);
  wireless.available=false;ready(750);touch(750);
  assert(holdFired&&!state.pending&&requestId==10&&wireless.calls==0);
  assert(localModeNotice&&std::strstr(localModeNotice,"Radio busy"));
  wireless.available=true;ready(900);touch(900);ready(2000);touch(2000);
  assert(wireless.calls==0&&!state.pending); // becoming ready cannot replay the held gesture
  release();touch(2001);ready(2100);press();touch(2100);held();ready(2750);touch(2750);
  assert(wireless.calls==1&&state.pending==11&&state.token==0&&!localModeNotice);
  m5link::Request parsed;char line[48];std::strcpy(line,wireless.sent);line[std::strlen(line)-1]=0;
  assert(m5link::decode(line,parsed)&&parsed.mode==0&&parsed.id==11&&parsed.token==123);
  ready(2800);touch(2800);assert(wireless.calls==1); // no repeat while held
  state.pending=0;release();touch(3000);ready(3100);press();touch(3100);held();
  wireless.accept=false;ready(3750);touch(3750);
  assert(wireless.calls==2&&!state.pending&&state.token==0&&state.requested==-1&&!state.pendingUnknown);
  assert(localModeNotice&&std::strstr(localModeNotice,"Not sent"));
  wireless.accept=true;ready(4000);touch(4000);assert(wireless.calls==2);
  release();touch(4100);ready(4200);press();touch(4200);held();ready(4850);state.modeReady=false;touch(4850);
  assert(wireless.calls==2&&!state.pending&&std::strstr(localModeNotice,"unavailable"));
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'touch.cpp').write_text(harness)
            subprocess.run([shutil.which('c++'),'-std=c++17','-Wall','-Wextra','-Werror',
                '-fsanitize=address,undefined','-g','-I'+str(include),
                '-I'+str(ROOT/'firmware/m5-core2'),'-I'+str(ROOT/'firmware/libraries/M5DisplayLink'),
                str(path/'touch.cpp'),'-o',str(path/'touch')],check=True)
            subprocess.run([str(path/'touch')],check=True,timeout=10)


if __name__=='__main__':unittest.main()
