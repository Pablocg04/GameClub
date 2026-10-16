#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace gameclub {
struct PadAxes {
  // sticks izquierdo/derecho, HAT y gatillos. Todos comparten el mismo puerto.
  std::array<float,8> values{};
  void set(const std::array<float,8>& input) {
    for(unsigned i=0;i<8;++i)values[i]=std::isfinite(input[i])?std::clamp(input[i],i<6?-1.f:0.f,1.f):0.f;
  }
  uint16_t mask() const {
    uint16_t result=0;
    if(values[1]<-.45f||values[5]<-.5f)result|=1<<4;
    if(values[1]>.45f||values[5]>.5f)result|=1<<5;
    if(values[0]<-.45f||values[4]<-.5f)result|=1<<6;
    if(values[0]>.45f||values[4]>.5f)result|=1<<7;
    if(values[6]>.5f)result|=1<<12;
    if(values[7]>.5f)result|=1<<13;
    return result;
  }
  int16_t analog(unsigned axis) const {
    float value=axis<4?values[axis]:0;
    return std::abs(value)>.15f?static_cast<int16_t>(value*32767):0;
  }
  int relative(unsigned axis,int digital) const {
    int left=analog(axis),right=analog(axis+2);
    return left?left/2200:right?right/2200:digital*8;
  }
};
}
