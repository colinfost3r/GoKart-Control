#include "DisplayMaintenance.h"
#include <cassert>
#include <cstdio>
#include <string>

using namespace m5dash::maintenance;

std::string config(const char* ssid="test network", const char* wifi="wifi-test-only",
                   const char* ota="test-ota-secret", const char* host="gokart-display-3") {
  JsonDocument d;
  d["ssid"]=ssid; d["wifi_password"]=wifi; d["ota_password"]=ota; d["hostname"]=host;
  std::string result; serializeJson(d,result); return result;
}

int main() {
  Config c;
  assert(parseConfig(config().c_str(),c));
  assert(std::strcmp(c.ssid,"test network")==0);
  assert(std::strcmp(c.host,"gokart-display-3")==0);
  const Config saved=c;
  for (const char* bad : {"", "{}", "null", "[]", "not JSON",
      "{\"ssid\":1,\"wifi_password\":\"x\",\"ota_password\":\"123456789012\",\"hostname\":\"x\"}"}) {
    assert(!parseConfig(bad,c)); assert(std::memcmp(&saved,&c,sizeof c)==0);
  }
  assert(!parseConfig(config("", "", "123456789012").c_str(),c));
  assert(!parseConfig(config("x", "", "12345678901").c_str(),c));
  assert(parseConfig(config("x", "", "123456789012").c_str(),c));
  for(const char* bad : {"", "-x", "x-", "gokart.local", "bad host", "bad_host", "bad\"host"})
    assert(!parseConfig(config("x","","123456789012",bad).c_str(),c));
  assert(hostnameValid("gokart-display-3"));
  assert(!hostnameValid(std::string(32,'x').c_str()));
  assert(parseConfig(config(std::string(32,'s').c_str(),std::string(64,'w').c_str(),
                           std::string(64,'p').c_str(),std::string(31,'h').c_str()).c_str(),c));
  assert(!parseConfig(config(std::string(33,'s').c_str()).c_str(),c));
  assert(!parseConfig(config("x",std::string(65,'w').c_str()).c_str(),c));
  assert(!parseConfig(config("x","",std::string(65,'p').c_str()).c_str(),c));
  assert(!parseConfig(config("new\nline").c_str(),c));
  assert(!parseConfig((config()+std::string(301,' ')).c_str(),c));
  std::string embedded=config(); embedded.replace(embedded.find("test network"),12,"test\\u0000network");
  assert(!parseConfig(embedded.c_str(),c));
  JsonDocument extra; deserializeJson(extra,config()); extra["extra"]="ignored?";
  std::string unknown; serializeJson(extra,unknown); assert(!parseConfig(unknown.c_str(),c));
  assert(remaining(100,100)==WINDOW_MS);
  assert(remaining(100,100+WINDOW_MS-1)==1);
  assert(remaining(100,100+WINDOW_MS)==0);
  assert(remaining(100,100+WINDOW_MS+1)==0);
  const uint32_t nearWrap=0xfffffff0U;
  assert(remaining(nearWrap,nearWrap+200U)==WINDOW_MS-200U);
  assert(remaining(nearWrap,nearWrap+WINDOW_MS)==0);
  std::puts("maintenance config validation and bounded window checks passed");
}
