#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <esp_mac.h>
#include "PairingRecord.h"
#include "M5EspNowLink.h"

namespace m5now {
// One versioned CRC-protected NVS blob: no partial peer/key association after a power loss.
// Provision only over the local USB port. Key material is never printed or accepted by radio.
class Settings {
 public:
  Pairing pair{};
  bool configured=false,rebootRequired=false;
  bool load(){
    Preferences p;uint8_t bytes[PAIR_BYTES];configured=false;
    if(!p.begin("m5espnow",true))return false;
    size_t n=p.getBytesLength("pair");
    if(n==sizeof bytes&&p.getBytes("pair",bytes,sizeof bytes)==sizeof bytes)configured=decodePair(bytes,sizeof bytes,pair);
    p.end();return configured;
  }
  bool save(const Pairing& v){
    uint8_t bytes[PAIR_BYTES];if(!encodePair(v,bytes,sizeof bytes))return false;
    Preferences p;if(!p.begin("m5espnow",false))return false;
    bool ok=p.putBytes("pair",bytes,sizeof bytes)==sizeof bytes;p.end();rebootRequired|=ok;return ok;
  }
  void status(Link& link,Print& out){
    uint8_t mac[6];esp_read_mac(mac,ESP_MAC_WIFI_STA);
    out.printf("{\"t\":\"espnow\",\"configured\":%s,\"reboot_required\":%s,\"mac\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"peer\":\"%02x:%02x:%02x:%02x:%02x:%02x\",\"ready\":%s,\"linked\":%s,\"channel\":%u,\"rssi\":%d",
      configured?"true":"false",rebootRequired?"true":"false",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5],
      pair.peer[0],pair.peer[1],pair.peer[2],pair.peer[3],pair.peer[4],pair.peer[5],
      link.ready()?"true":"false",link.connected(millis())?"true":"false",link.channel(),link.rssi());
    out.printf(",\"rx_channel\":%u,\"peer_channel\":%u,\"channel_aligned\":%s",
      link.receivedChannel(),link.peerChannel(),link.channelAligned(millis())?"true":"false");
    const auto& s=link.stats();
    out.printf(",\"tx_lines\":%lu,\"tx_packets\":%lu,\"tx_failed\":%lu,\"tx_dropped\":%lu,\"rx_lines\":%lu,\"rx_packets\":%lu,\"rx_dropped\":%lu,\"rx_invalid\":%lu,\"channel_hops\":%lu}\n",
      (unsigned long)s.txLines,(unsigned long)s.txPackets,(unsigned long)s.txFailed,(unsigned long)s.txDropped,
      (unsigned long)s.rxLines,(unsigned long)s.rxPackets,(unsigned long)s.rxDropped,(unsigned long)s.rxInvalid,(unsigned long)s.channelHops);
  }
  bool command(const char* line,Link& link,Print& out){
    if(strncmp(line,"espnow",6)||(line[6]&&line[6]!=' '))return false;
    if(!strcmp(line,"espnow status")){status(link,out);return true;}
    if(!strncmp(line,"espnow pair ",12)){
      char mac[18]{},lmk[33]{},pmk[33]{},extra{};Pairing v;
      bool ok=sscanf(line+12,"%17s %32s %32s %c",mac,lmk,pmk,&extra)==3
        &&parseMac(mac,v.peer)&&parseHex(lmk,v.lmk,16)&&parseHex(pmk,v.pmk,16)&&validPair(v);
      uint8_t own[6];esp_read_mac(own,ESP_MAC_WIFI_STA);ok=ok&&memcmp(own,v.peer,6)!=0;
      ok=ok&&save(v);memset(lmk,0,sizeof lmk);memset(pmk,0,sizeof pmk);memset(&v,0,sizeof v);
      out.println(ok?"{\"t\":\"espnow_config\",\"stored\":true,\"reboot_required\":true}":"{\"t\":\"espnow_config\",\"stored\":false}");return true;
    }
    if(!strcmp(line,"espnow clear")){
      Preferences p;bool ok=p.begin("m5espnow",false);if(ok){ok=!p.isKey("pair")||p.remove("pair");p.end();}rebootRequired|=ok;
      out.println(ok?"{\"t\":\"espnow_config\",\"cleared\":true,\"reboot_required\":true}":"{\"t\":\"espnow_config\",\"cleared\":false}");return true;
    }
    out.println("{\"t\":\"espnow_config\",\"error\":\"use USB espnow status, pair MAC LMK PMK, or clear\"}");return true;
  }
};
} // namespace m5now
