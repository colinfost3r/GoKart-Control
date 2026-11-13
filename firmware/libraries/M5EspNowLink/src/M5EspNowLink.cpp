#include "M5EspNowLink.h"
#include <esp_wifi.h>
#include <esp_system.h>
#include <mbedtls/md.h>

namespace m5now {
std::atomic<Link*> Link::instance_{nullptr};
std::atomic<Link::ExtraReceiver> Link::extraReceiver_{nullptr};
static bool validUnicast(const uint8_t* mac) {
  if(!mac || (mac[0]&1))return false;
  uint8_t any=0;for(unsigned i=0;i<6;++i)any|=mac[i];return any;
}
static bool nonzero(const uint8_t* key) {
  if(!key)return false;uint8_t any=0;for(unsigned i=0;i<16;++i)any|=key[i];return any;
}
bool Link::begin(Role role,const uint8_t peer[6],const uint8_t lmk[16],const uint8_t pmk[16]) {
  if(ready_ || instance_ || !validUnicast(peer) || !nonzero(lmk) || !nonzero(pmk) ||
     (role!=Role::Heltec && role!=Role::Display))return false;
  role_=role;assembler_.setRole(role);std::memcpy(peer_,peer,6);
  // A separate labeled HMAC key authenticates the complete application fragment even if a
  // driver were to deliver an unencrypted frame bearing a spoofed paired source address.
  static const uint8_t label[]="GoKart M5 ESP-NOW frame auth v1";
  if(mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),lmk,16,label,sizeof(label)-1,authKey_))return false;
  if(!(WiFi.getMode()&WIFI_MODE_STA) && !WiFi.mode(WIFI_STA))return false;
  if(role_==Role::Display) {
    WiFi.setAutoReconnect(false);
    // Clear an existing association without erasing saved credentials; the display follows
    // only its paired Heltec and never attempts to join an old access point.
    WiFi.disconnect(false,false);
  }
  WiFi.setSleep(false);
  if(esp_wifi_get_mac(WIFI_IF_STA,own_)!=ESP_OK || !std::memcmp(peer_,own_,6))return false;
  packets_=xQueueCreate(RX_PACKET_DEPTH,sizeof(Packet));done_=xQueueCreate(1,sizeof(bool));
  if(!packets_ || !done_) {end();return false;}
  if(esp_now_init()!=ESP_OK) {end();return false;}
  instance_=this;
  if(esp_now_set_pmk(pmk)!=ESP_OK) {end();return false;}
  esp_now_peer_info_t p{};std::memcpy(p.peer_addr,peer_,6);std::memcpy(p.lmk,lmk,16);
  p.channel=0;p.ifidx=WIFI_IF_STA;p.encrypt=true;
  if(esp_now_add_peer(&p)!=ESP_OK || esp_now_register_recv_cb(receive)!=ESP_OK ||
     esp_now_register_send_cb(sent)!=ESP_OK) {end();return false;}
  uint8_t current=1;wifi_second_chan_t secondary;
  if(esp_wifi_get_channel(&current,&secondary)==ESP_OK && current>=1 && current<=14)channel_=current;
  if(role_==Role::Display && WiFi.status()!=WL_CONNECTED) {
    channel_=1;esp_wifi_set_channel(channel_,WIFI_SECOND_CHAN_NONE);
  }
  boot_=esp_random();if(!boot_)boot_=1;id_=0;
  alignment_.begin(role_,boot_,esp_random());alignment_.driver(channel_,esp_random());
  hopMs_=heartbeatMs_=millis();ready_=true;return true;
}
void Link::setChannelSearchEnabled(bool enabled) {
  if(channelSearchEnabled_==enabled)return;
  channelSearchEnabled_=enabled;hopMs_=millis();++radioEpoch_;
  alignment_.enable(enabled);assembler_.clear();
  if(role_==Role::Display)abandonTx();
}
void Link::refreshChannel() {
  uint8_t current=0;wifi_second_chan_t secondary;
  if(esp_wifi_get_channel(&current,&secondary)!=ESP_OK)current=0;
  if(current!=channel_) {
    channel_=current;++radioEpoch_;alignment_.driver(current,esp_random());assembler_.clear();
    abandonTx(); // old channel advertisements/grants are stale too; telemetry resumes fresh
  }
}
void Link::end() {
  ready_=false;
  if(instance_==this) {
    esp_now_unregister_recv_cb();esp_now_unregister_send_cb();esp_now_deinit();instance_=nullptr;
  }
  if(packets_) {vQueueDelete(packets_);packets_=nullptr;}
  if(done_) {vQueueDelete(done_);done_=nullptr;}
  txCount_=rxCount_=0;txHead_=txTail_=rxHead_=rxTail_=0;active_=inFlight_=abandoned_=haveRx_=false;
  assembler_.clear();alignment_.invalidate();++radioEpoch_;std::memset(authKey_,0,sizeof authKey_);
}
void Link::receive(const esp_now_recv_info_t* info,const uint8_t* data,int length) {
  auto extra=extraReceiver_.load();if(extra&&extra(info,data,length))return;
  Link* self=instance_;
  if(!self || !self->ready_ || !info || !info->src_addr || !info->des_addr || !data ||
     length<int(HEADER_SIZE+TAG_SIZE) || length>int(PACKET_MAX) ||
     std::memcmp(info->src_addr,self->peer_,6) || std::memcmp(info->des_addr,self->own_,6))return;
  Packet p{};p.arrived=millis();p.epoch=self->radioEpoch_.load();p.length=uint16_t(length);
  if(info->rx_ctrl) {p.rssi=info->rx_ctrl->rssi;p.channel=info->rx_ctrl->channel;}
  std::memcpy(p.data,data,size_t(length));
  if(xQueueSend(self->packets_,&p,0)!=pdTRUE) {
    portENTER_CRITICAL(&self->mux_);++self->callbackDrops_;portEXIT_CRITICAL(&self->mux_);
  }
}
void Link::sent(const esp_now_send_info_t* info,esp_now_send_status_t status) {
  Link* self=instance_;
  if(!self || !self->ready_ || !info || !info->des_addr || std::memcmp(info->des_addr,self->peer_,6))return;
  const bool ok=status==ESP_NOW_SEND_SUCCESS;
  xQueueSend(self->done_,&ok,0); // only one packet is ever outstanding
}
bool Link::tag(const uint8_t* p,size_t n,uint8_t out[TAG_SIZE]) const {
  uint8_t digest[32];
  if(mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),authKey_,sizeof authKey_,p,n,digest))return false;
  std::memcpy(out,digest,TAG_SIZE);return true;
}
bool Link::authenticate(const uint8_t* p,size_t n) const {
  if(n<HEADER_SIZE+TAG_SIZE || n>PACKET_MAX)return false;
  uint8_t expected[TAG_SIZE];if(!tag(p,n-TAG_SIZE,expected))return false;
  uint8_t different=0;for(size_t i=0;i<TAG_SIZE;++i)different|=expected[i]^p[n-TAG_SIZE+i];
  return different==0;
}
uint32_t Link::nextId() {
  if(++id_==0) {boot_=esp_random();if(!boot_)boot_=1;id_=1;}
  return id_;
}
bool Link::enqueue(const char* text,size_t n,Kind kind,uint32_t now) {
  if(txCount_==TX_DEPTH) {++stats_.txDropped;return false;}
  Line& line=tx_[txHead_];line.born=now;line.id=nextId();line.length=uint16_t(n);line.kind=kind;
  if(n)std::memcpy(line.text,text,n);line.text[n]=0;
  txHead_=(txHead_+1)%TX_DEPTH;++txCount_;return true;
}
bool Link::sendLine(const char* line,uint32_t now) {
  if(!ready_ || !line)return false;
  size_t n=strnlen(line,MAX_LINE+3);
  if(n && line[n-1]=='\n')--n;
  if(n && line[n-1]=='\r')--n;
  if(!n || n>MAX_LINE) {++stats_.txDropped;return false;}
  for(size_t i=0;i<n;++i)if(uint8_t(line[i])<32 || line[i]==127) {++stats_.txDropped;return false;}
  // The display request is never queued behind telemetry or a recovery event. No command retry.
  if(channelRecordPrefix(line) || (role_==Role::Display && (n>CHUNK_SIZE || !canSend(now)))) {
    ++stats_.txDropped;return false;
  }
  if(!enqueue(line,n,Kind::Line,now))return false;
  serviceTx(now);return true;
}
void Link::abandonTx() {
  stats_.txDropped+=txCount_;txCount_=0;txTail_=txHead_;
  if(active_) {++stats_.txDropped;active_=false;}
  // Never start another packet until the preceding callback arrives; a late result must not
  // accidentally advance a new line. A stalled Wi-Fi callback cannot cause command replay.
  if(inFlight_)abandoned_=true;
}
void Link::serviceTx(uint32_t now) {
  if(!ready_)return;
  refreshChannel();
  bool ok;
  if(xQueueReceive(done_,&ok,0)==pdTRUE) {
    inFlight_=false;
    if(abandoned_)abandoned_=false;
    else if(active_) {
      if(!ok) {++stats_.txFailed;active_=false;}
      else if(++part_>=parts(current_.length)) {
        if(current_.kind==Kind::Line)++stats_.txLines;
        active_=false;
      }
    }
  }
  if(active_ && uint32_t(now-current_.born)>MAX_AGE_MS)abandonTx();
  if(inFlight_)return;
  while(!active_ && txCount_) {
    current_=tx_[txTail_];txTail_=(txTail_+1)%TX_DEPTH;--txCount_;
    if(uint32_t(now-current_.born)>MAX_AGE_MS || (role_==Role::Display && !connected(now))) {
      ++stats_.txDropped;continue;
    }
    active_=true;part_=0;
  }
  if(!active_)return;
  // A channel/maintenance change after enqueue must not release a queued mode request.
  if(role_==Role::Display && current_.kind==Kind::Line && !channelRecordPrefix(current_.text) &&
     (!channelSearchEnabled_ || !alignment_.aligned(now))) {abandonTx();return;}
  uint8_t p[PACKET_MAX];size_t n=encode(p,role_,current_.kind,boot_,current_.id,current_.text,current_.length,part_);
  if(!n || !tag(p,n,p+n)) {++stats_.txFailed;active_=false;return;}
  inFlight_=true;
  if(esp_now_send(peer_,p,n+TAG_SIZE)!=ESP_OK) {inFlight_=false;++stats_.txFailed;active_=false;return;}
  ++stats_.txPackets;
}
void Link::poll(uint32_t now) {
  if(!ready_)return;
  refreshChannel();
  portENTER_CRITICAL(&mux_);stats_.rxDropped+=callbackDrops_;callbackDrops_=0;portEXIT_CRITICAL(&mux_);
  Packet p;unsigned budget=RX_PACKET_DEPTH;
  // Leave remaining packets queued until the caller drains completed lines. Dropping an
  // older self/metadata line here would bias an eight-kart burst toward its last peers.
  while(budget-- && rxCount_<RX_LINE_DEPTH && xQueueReceive(packets_,&p,0)==pdTRUE) {
    ++stats_.rxPackets;
    // Wi-Fi callbacks can enqueue after poll's caller sampled time. Refresh after dequeue
    // so a newer arrival never looks billions of milliseconds old through unsigned wrap.
    now=millis();
    if(uint32_t(now-p.arrived)>MAX_AGE_MS) {++stats_.rxDropped;continue;}
    if(!authenticate(p.data,p.length)) {++stats_.rxInvalid;continue;}
    auto result=assembler_.consume(p.data,p.length-TAG_SIZE,p.arrived);
    if(result==Result::Invalid) {++stats_.rxInvalid;continue;}
    if(result==Result::Line || result==Result::Heartbeat) {
      haveRx_=true;lastRxMs_=assembler_.receivedMs();rssi_=p.rssi;
      rxChannel_=p.channel;
      if(alignment_.peerBoot(assembler_.peerBoot(),esp_random()))abandonTx();
      hopMs_=now;
      if(result==Result::Line) {
        if(channelRecordPrefix(assembler_.line())) {
          ChannelRecord record;
          if(!decodeChannelRecord(assembler_.line(),record))++stats_.rxInvalid;
          else if(!alignment_.accept(record,p.channel,assembler_.receivedMs(),p.epoch==radioEpoch_.load()))++stats_.rxDropped;
          continue;
        }
        if(role_==Role::Heltec && (p.epoch!=radioEpoch_.load() || p.channel!=channel_ || !alignment_.aligned(now))) {
          ++stats_.rxDropped;continue;
        }
        ++stats_.rxLines;
        Completed& line=completed_[rxHead_];line.arrived=assembler_.receivedMs();line.epoch=p.epoch;line.peerBoot=assembler_.peerBoot();
        std::memcpy(line.text,assembler_.line(),std::strlen(assembler_.line())+1);
        rxHead_=(rxHead_+1)%RX_LINE_DEPTH;++rxCount_;
      }
    }
  }
  now=millis(); // parsing/authentication also consume time; expiry and hopping use current time
  if(assembler_.expire(now))++stats_.rxDropped;
  if(role_==Role::Display) {
    const uint8_t target=alignment_.retuneTarget(now);
    const bool mayRetune=channelSearchEnabled_ && !inFlight_ && !active_ && !txCount_ &&
      WiFi.status()!=WL_CONNECTED && WiFi.scanComplete()!=WIFI_SCAN_RUNNING;
    if(target && mayRetune) {
      // First invalidate queued callback proof; require a NEW authenticated announcement
      // received on the intended channel before acknowledgement/control readiness.
      ++radioEpoch_;alignment_.invalidate();assembler_.clear();
      if(esp_wifi_set_channel(target,WIFI_SECOND_CHAN_NONE)==ESP_OK) {refreshChannel();++stats_.channelHops;}
      hopMs_=now;
    } else if(!connected(now)) {
      abandonTx();
      if(mayRetune && uint32_t(now-hopMs_)>=650) {
        const uint8_t next=channel_>=11?1:uint8_t(channel_+1);
        if(esp_wifi_set_channel(next,WIFI_SECOND_CHAN_NONE)==ESP_OK) {
          refreshChannel();++stats_.channelHops;
        }
        hopMs_=now;
      }
    } else if(uint32_t(now-heartbeatMs_)>=500 && !inFlight_ && !active_ && !txCount_) {
      enqueue(nullptr,0,Kind::Heartbeat,now);heartbeatMs_=now;
    }
  }
  // Only insert one-packet maintenance frames into an idle transmitter, never ahead of
  // an active line. Older firmware ignores these ordinary v1 lines; controls require both
  // updated peers. A Heltec grant names the current display boot, not merely a channel.
  if(uint32_t(now-channelReportMs_)>=500 && !inFlight_ && !active_ && !txCount_) {
    ChannelRecord record;char text[CHANNEL_RECORD_SIZE+1];
    if(alignment_.record(now,record) && encodeChannelRecord(record,text)) {
      enqueue(text,CHANNEL_RECORD_SIZE,Kind::Line,now);channelReportMs_=now;
    }
  }
  serviceTx(now);
}
const char* Link::readLine(uint32_t now) {
  refreshChannel(); // AP-owned channel can change after poll but before command dispatch
  while(rxCount_) {
    const Completed& line=completed_[rxTail_];rxTail_=(rxTail_+1)%RX_LINE_DEPTH;--rxCount_;
    if(uint32_t(now-line.arrived)>MAX_AGE_MS) {++stats_.rxDropped;continue;}
    if(role_==Role::Heltec && (line.epoch!=radioEpoch_.load() || line.peerBoot!=assembler_.peerBoot() || !alignment_.aligned(now))) {
      ++stats_.rxDropped;continue;
    }
    std::memcpy(read_,line.text,std::strlen(line.text)+1);readMs_=line.arrived;return read_;
  }
  return nullptr;
}
}
