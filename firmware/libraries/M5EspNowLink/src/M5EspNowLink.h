#pragma once
#include "M5EspNowFrame.h"
#include "M5ChannelAlignment.h"
#include <atomic>
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

namespace m5now {
struct Stats {
  uint32_t txLines=0,txPackets=0,txFailed=0,txDropped=0;
  uint32_t rxLines=0,rxPackets=0,rxDropped=0,rxInvalid=0,channelHops=0;
};
class Link {
public:
  // Wi-Fi STA must share the Heltec's AP channel. Display discovers it without joining Wi-Fi.
  // Keys are caller-owned provisioning data. No open discovery, broadcast or default keys.
  bool begin(Role role,const uint8_t peer[6],const uint8_t lmk[16],const uint8_t pmk[16]);
  void end();
  void poll(uint32_t now);
  // Display maintenance owns the Wi-Fi channel while joining/using its AP. Pausing search
  // does not disconnect Wi-Fi, reinitialize ESP-NOW, or clear the authenticated peer session.
  void setChannelSearchEnabled(bool enabled);
  bool sendLine(const char* line,uint32_t now);
  const char* readLine(uint32_t now); // NUL-terminated; valid until the next readLine call
  uint32_t receivedMs() const { return readMs_; }
  bool ready() const { return ready_; }
  bool canSend(uint32_t now) const { return ready_ && connected(now) &&
    (role_!=Role::Display || (channelSearchEnabled_ && alignment_.aligned(now))) &&
    !inFlight_ && !active_ && !txCount_; }
  bool connected(uint32_t now) const { return haveRx_ && uint32_t(now-lastRxMs_)<LINK_MS; }
  uint8_t channel() const { return channel_; }
  uint8_t receivedChannel() const { return rxChannel_; }
  uint8_t peerChannel() const { return alignment_.peerChannel(); }
  bool channelAligned(uint32_t now) const { return alignment_.aligned(now); }
  int8_t rssi() const { return rssi_; }
  const Stats& stats() const { return stats_; }
private:
  static constexpr unsigned TX_DEPTH=12,RX_PACKET_DEPTH=32,RX_LINE_DEPTH=4;
  struct Packet { uint32_t arrived,epoch;uint16_t length;int8_t rssi;uint8_t channel;uint8_t data[PACKET_MAX]; };
  struct Line { uint32_t born,id;uint16_t length;Kind kind;char text[MAX_LINE+1]; };
  struct Completed { uint32_t arrived,epoch,peerBoot;char text[MAX_LINE+1]; };
  static std::atomic<Link*> instance_;
  static void receive(const esp_now_recv_info_t* info,const uint8_t* data,int length);
  static void sent(const esp_now_send_info_t* info,esp_now_send_status_t status);
  bool authenticate(const uint8_t* p,size_t n) const;
  bool tag(const uint8_t* p,size_t n,uint8_t out[TAG_SIZE]) const;
  bool enqueue(const char* text,size_t n,Kind kind,uint32_t now);
  void serviceTx(uint32_t now);
  void abandonTx();
  void refreshChannel();
  uint32_t nextId();
  uint8_t peer_[6]{},own_[6]{},authKey_[32]{};
  Role role_=Role::Display;
  std::atomic<bool> ready_{false};
  bool haveRx_=false,inFlight_=false,abandoned_=false,active_=false;
  bool channelSearchEnabled_=true;
  uint8_t channel_=1,rxChannel_=0,part_=0;int8_t rssi_=0;
  uint32_t boot_=0,id_=0,lastRxMs_=0,hopMs_=0,heartbeatMs_=0,readMs_=0,channelReportMs_=0;
  std::atomic<uint32_t> radioEpoch_{1};
  QueueHandle_t packets_=nullptr,done_=nullptr;
  // Queue overflow accounting crosses Wi-Fi/application tasks via this critical section.
  portMUX_TYPE mux_=portMUX_INITIALIZER_UNLOCKED;
  uint32_t callbackDrops_=0;
  Line tx_[TX_DEPTH]{},current_{};unsigned txHead_=0,txTail_=0,txCount_=0;
  Completed completed_[RX_LINE_DEPTH]{};unsigned rxHead_=0,rxTail_=0,rxCount_=0;
  char read_[MAX_LINE+1]{};
  Assembler assembler_;
  ChannelAlignment alignment_;
  Stats stats_{};
};
}
