#pragma once
// Minimal host adapter: exercise the production parser without device libraries.
#include <cstddef>
#include <cstdint>
#include <cstring>

uint32_t millis();

class Stream {
public:
  virtual ~Stream() = default;
  virtual int available() = 0;
  virtual int read() = 0;
  virtual size_t write(const uint8_t* data, size_t size) = 0;
};
