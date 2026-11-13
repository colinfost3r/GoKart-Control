#include "VescLink.h"
#include <cstdlib>
#include <deque>
#include <iostream>
#include <string>
#include <vector>

static uint32_t clockMs = 100;
uint32_t millis() { return clockMs; }

static void check(bool ok, const char* why) {
  if (!ok) { std::cerr << why << '\n'; std::exit(1); }
}

class MemoryStream : public Stream {
public:
  std::deque<uint8_t> rx;
  std::vector<uint8_t> tx;
  int available() override { return static_cast<int>(rx.size()); }
  int read() override {
    if (rx.empty()) return -1;
    int value = rx.front(); rx.pop_front(); return value;
  }
  size_t write(const uint8_t* data, size_t size) override {
    tx.insert(tx.end(), data, data + size); return size;
  }
  void packet(const std::vector<uint8_t>& payload) {
    if (payload.size() < 256) { rx.push_back(2); rx.push_back(payload.size()); }
    else { rx.push_back(3); rx.push_back(payload.size() >> 8); rx.push_back(payload.size() & 255); }
    rx.insert(rx.end(), payload.begin(), payload.end());
    const uint16_t crc = VescLink::crc16(payload.data(), payload.size());
    rx.push_back(crc >> 8); rx.push_back(crc & 255); rx.push_back(3);
  }
};

static std::vector<uint8_t> firmware(const std::string& hardware = "75_300_R2", uint8_t firstUuidByte = 0x37) {
  std::vector<uint8_t> p = {VESC_COMM_FW_VERSION, 6, 2};
  p.insert(p.end(), hardware.begin(), hardware.end()); p.push_back(0);
  const uint8_t uuid[] = {firstUuidByte,0,0x4e,0,9,0x51,0x34,0x30,0x37,0x35,0x37,0x39};
  p.insert(p.end(), std::begin(uuid), std::end(uuid));
  return p;
}

static void receive(MemoryStream& stream, VescLink& link, const std::vector<uint8_t>& payload) {
  stream.packet(payload);
  check(link.poll(), "complete framed packet was not handled");
  check(stream.tx.empty(), "receiving/reconciling a controller must not send any command");
}

static void validThenLoss() {
  MemoryStream stream; VescLink link(&stream);
  check(link.fwSeenMs == 0 && link.uuidHex[0] == 0, "new client has identity proof");
  receive(stream, link, firmware());
  check(link.fwSeenMs == clockMs, "complete UUID did not establish freshness");
  check(std::strcmp(link.uuidHex, "37004e000951343037353739") == 0, "incorrect UUID decoding");
  link.markLinkLost();
  check(link.fwSeenMs == 0 && link.uuidHex[0] == 0, "link loss retained identity proof");
  check(link.fwMajor == 6 && link.fwMinor == 2 && std::strcmp(link.hwName, "75_300_R2") == 0,
        "link loss unnecessarily removed descriptive diagnostics");
  check(stream.tx.empty(), "link loss sent a controller command");
}

static void everyTruncation() {
  const auto complete = firmware();
  for (size_t n = 1; n < complete.size(); ++n) {
    MemoryStream stream; VescLink link(&stream);
    receive(stream, link, complete);
    ++clockMs;
    receive(stream, link, std::vector<uint8_t>(complete.begin(), complete.begin() + n));
    check(link.fwSeenMs == 0 && link.uuidHex[0] == 0, "truncated reply refreshed or retained old UUID proof");
  }
}

static void hardwareNameBounds() {
  MemoryStream stream; VescLink link(&stream);
  receive(stream, link, firmware());
  std::vector<uint8_t> noTerminator = {VESC_COMM_FW_VERSION, 6, 2};
  noTerminator.insert(noTerminator.end(), 80, 'A');
  receive(stream, link, noTerminator);
  check(link.fwSeenMs == 0 && link.uuidHex[0] == 0, "unterminated name retained identity");
  ++clockMs;
  receive(stream, link, firmware(std::string(80, 'B')));
  check(link.fwSeenMs == clockMs && std::strlen(link.hwName) == sizeof(link.hwName) - 1,
        "long terminated name did not preserve bounded diagnostics and fresh identity");
  check(std::strcmp(link.uuidHex, "37004e000951343037353739") == 0, "UUID offset used truncated display name");
}

static void configBeforeIdentity() {
  MemoryStream stream; VescLink link(&stream);
  receive(stream, link, firmware());
  link.markLinkLost(); ++clockMs;
  std::vector<uint8_t> config(482, 0);
  config[0] = VESC_COMM_GET_MCCONF;
  config[1] = 0x2e; config[2] = 0x43; config[3] = 0xa1; config[4] = 0x61;
  receive(stream, link, config);
  std::vector<uint8_t> values(74, 0); values[0] = VESC_COMM_GET_VALUES;
  receive(stream, link, values);
  check(link.limits().receivedMs == clockMs && link.linkUp(), "fresh config/telemetry were not parsed");
  check(link.fwSeenMs == 0 && link.uuidHex[0] == 0, "config/telemetry revived previous controller identity");
  link.markLinkLost();
  check(link.limits().receivedMs == 0 && !link.linkUp(), "link loss retained config/telemetry freshness");
}

static void controllerReplacement() {
  MemoryStream stream; VescLink link(&stream);
  receive(stream, link, firmware());
  link.markLinkLost(); ++clockMs;
  receive(stream, link, {VESC_COMM_FW_VERSION, 6, 3, 'N', 'E', 'W', 0});
  check(link.fwMajor == 6 && link.fwMinor == 3 && std::strcmp(link.hwName, "NEW") == 0,
        "UUID-less reply lost useful descriptive diagnostics");
  check(link.fwSeenMs == 0 && link.uuidHex[0] == 0, "UUID-less replacement controller borrowed old identity");
  ++clockMs;
  receive(stream, link, firmware("OTHER", 0x42));
  check(link.fwSeenMs == clockMs && std::strcmp(link.uuidHex, "42004e000951343037353739") == 0,
        "fresh replacement UUID did not replace old identity");
}

int main(int argc, char** argv) {
  check(argc == 2, "choose a regression case");
  const std::string test = argv[1];
  if (test == "loss") validThenLoss();
  else if (test == "truncation") everyTruncation();
  else if (test == "name") hardwareNameBounds();
  else if (test == "ordering") configBeforeIdentity();
  else if (test == "replacement") controllerReplacement();
  else check(false, "unknown test case");
}
