#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <deque>
#include <vector>
#include <algorithm>
#define ESP_OK 0
#define WIFI_MODE_STA 1
#define WIFI_STA WIFI_MODE_STA
#define WIFI_IF_STA 0
#define WL_CONNECTED 3
#define WIFI_SCAN_RUNNING -1
#define portMUX_INITIALIZER_UNLOCKED 0
#define portENTER_CRITICAL(p) ((void)(p))
#define portEXIT_CRITICAL(p) ((void)(p))
using portMUX_TYPE=int;
using wifi_second_chan_t=int;
constexpr int WIFI_SECOND_CHAN_NONE=0,pdTRUE=1;
struct wifi_pkt_rx_ctrl_t { int8_t rssi;uint8_t channel; };
struct esp_now_recv_info_t { const uint8_t* src_addr;const uint8_t* des_addr;wifi_pkt_rx_ctrl_t* rx_ctrl; };
struct esp_now_send_info_t { const uint8_t* des_addr; };
enum esp_now_send_status_t { ESP_NOW_SEND_SUCCESS,ESP_NOW_SEND_FAIL };
struct esp_now_peer_info_t { uint8_t peer_addr[6],lmk[16];uint8_t channel;int ifidx;bool encrypt; };
using ReceiveCallback=void(*)(const esp_now_recv_info_t*,const uint8_t*,int);
using SendCallback=void(*)(const esp_now_send_info_t*,esp_now_send_status_t);
namespace fake {
inline uint32_t now=100,random=1000;
inline uint8_t channel=6,own[6]={2,1,2,3,4,5},peer[6]={2,5,4,3,2,1};
inline int connected=0,scan=0,setCalls=0;
inline bool setFail=false,pending=false;
inline ReceiveCallback receive=nullptr;inline SendCallback sent=nullptr;
inline std::vector<std::vector<uint8_t>> sentPackets;
inline void reset(){now=100;channel=6;connected=scan=setCalls=0;setFail=pending=false;sentPackets.clear();}
inline void complete(bool ok=true){pending=false;esp_now_send_info_t info{peer};if(sent)sent(&info,ok?ESP_NOW_SEND_SUCCESS:ESP_NOW_SEND_FAIL);}
}
inline uint32_t millis(){return fake::now;}
inline uint32_t esp_random(){return ++fake::random;}
struct FakeWiFi {
  int getMode(){return WIFI_MODE_STA;}bool mode(int){return true;}
  void setAutoReconnect(bool){}void setSleep(bool){}void disconnect(bool,bool){fake::connected=0;}
  int status(){return fake::connected;}int scanComplete(){return fake::scan;}
};inline FakeWiFi WiFi;
inline int esp_wifi_get_mac(int,uint8_t* out){std::memcpy(out,fake::own,6);return ESP_OK;}
inline int esp_wifi_get_channel(uint8_t* out,wifi_second_chan_t* secondary){*out=fake::channel;*secondary=0;return ESP_OK;}
inline int esp_wifi_set_channel(uint8_t c,wifi_second_chan_t){++fake::setCalls;if(fake::setFail)return -1;fake::channel=c;return ESP_OK;}
inline int esp_now_init(){return ESP_OK;}inline int esp_now_deinit(){return ESP_OK;}
inline int esp_now_set_pmk(const uint8_t*){return ESP_OK;}inline int esp_now_add_peer(esp_now_peer_info_t*){return ESP_OK;}
inline int esp_now_register_recv_cb(ReceiveCallback f){fake::receive=f;return ESP_OK;}
inline int esp_now_register_send_cb(SendCallback f){fake::sent=f;return ESP_OK;}
inline void esp_now_unregister_recv_cb(){fake::receive=nullptr;}
inline void esp_now_unregister_send_cb(){fake::sent=nullptr;}
inline int esp_now_send(const uint8_t*,const uint8_t* p,size_t n){fake::pending=true;fake::sentPackets.emplace_back(p,p+n);return ESP_OK;}
struct FakeQueue {size_t depth,size;std::deque<std::vector<uint8_t>> items;};using QueueHandle_t=FakeQueue*;
inline QueueHandle_t xQueueCreate(size_t depth,size_t size){return new FakeQueue{depth,size,{}};}
inline void vQueueDelete(QueueHandle_t q){delete q;}
inline int xQueueSend(QueueHandle_t q,const void* data,int){if(q->items.size()==q->depth)return 0;const auto* p=static_cast<const uint8_t*>(data);q->items.emplace_back(p,p+q->size);return pdTRUE;}
inline int xQueueReceive(QueueHandle_t q,void* out,int){if(q->items.empty())return 0;std::memcpy(out,q->items.front().data(),q->size);q->items.pop_front();return pdTRUE;}
// Deterministic MAC substitute tests adapter auth/rejection ordering, NOT cryptographic strength.
constexpr int MBEDTLS_MD_SHA256=1;
inline const void* mbedtls_md_info_from_type(int){return nullptr;}
inline int mbedtls_md_hmac(const void*,const uint8_t* key,size_t kn,const uint8_t* p,size_t n,uint8_t* out){
  uint32_t hash=2166136261u;for(size_t i=0;i<kn;++i)hash=(hash^key[i])*16777619u;
  for(size_t i=0;i<n;++i)hash=(hash^p[i])*16777619u;
  for(size_t i=0;i<32;++i){hash=hash*1664525u+1013904223u;out[i]=uint8_t(hash>>24);}return 0;
}
