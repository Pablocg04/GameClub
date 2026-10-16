#pragma once
#include <algorithm>
#include <vector>

namespace gameclub {
struct PadRect {
  float x, y, w, h;
  bool contains(float px, float py) const {
    return px >= x && px <= x+w && py >= y && py <= y+h;
  }
};
struct TouchButton { PadRect rect; const char* label; int index; bool round; };
struct TouchLayout {
  PadRect video, dpad;
  std::vector<TouchButton> buttons;
  float density, diameter;
  bool portrait;
};

// Coordenadas físicas, con tamaños de uso táctil expresados en dp (no píxeles fijos).
inline TouchLayout makeTouchLayout(float w, float h, float density, float scale, bool touch) {
  density = std::clamp(density, .75f, 8.f);
  scale = std::clamp(scale, .8f, 1.35f);
  const float margin = std::min(12.f*density, w*.035f);
  const float smallH = std::min(44.f*density, h*.12f);
  const float smallW = std::min(76.f*density, w*.23f);
  const float shoulderH = std::min(44.f*density, h*.12f);
  const bool portrait=touch && h>w;
  const float maxHeight=portrait?std::max(1.f,(h*.7f-smallH-shoulderH-4*margin)/2.46f):h*.22f;
  const float d = std::min({72.f*density*scale, w*.19f, maxHeight});
  const float rowY = h-margin-smallH;
  const float cy = rowY-margin-d*1.23f;
  const float lx = margin+d*1.1f, rx = w-margin-d*1.23f;
  const float shoulderY = std::max(margin, cy-d*1.23f-margin-shoulderH);
  TouchLayout result{{0,0,w,h}, {lx-d*1.1f,cy-d*1.1f,d*2.2f,d*2.2f}, {}, density,d,portrait};
  if(result.portrait) result.video.h=std::max(h*.3f,shoulderY-margin);
  auto cell = [&](int column,int row,int index) {
    const auto& p=result.dpad;
    result.buttons.push_back({{p.x+column*p.w/3,p.y+row*p.h/3,p.w/3,p.h/3},"",index,false});
  };
  cell(1,0,4);cell(1,2,5);cell(0,1,6);cell(2,1,7);
  cell(0,0,16);cell(2,0,17);cell(0,2,18);cell(2,2,19);
  auto circle = [&](float x,float y,const char* label,int index) {
    result.buttons.push_back({{x-d/2,y-d/2,d,d},label,index,true});
  };
  circle(rx+d*.73f,cy,"A",8);circle(rx,cy+d*.73f,"B",0);
  circle(rx-d*.73f,cy,"X",9);circle(rx,cy-d*.73f,"Y",1);
  const float shoulderW=std::min(96.f*density,w*.3f);
  result.buttons.push_back({{lx-shoulderW/2,shoulderY,shoulderW,shoulderH},"L",10,false});
  result.buttons.push_back({{rx-shoulderW/2,shoulderY,shoulderW,shoulderH},"R",11,false});
  const float menu=std::min(48.f*density,w*.14f);
  result.buttons.push_back({{w/2-menu/2-margin-smallW,rowY,smallW,smallH},"SELECT",2,false});
  result.buttons.push_back({{w/2+menu/2+margin,rowY,smallW,smallH},"START",3,false});
  result.buttons.push_back({{w/2-menu/2,rowY,menu,smallH},"MENU",-1,false});
  return result;
}
}
