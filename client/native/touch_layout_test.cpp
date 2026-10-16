#include "touch_layout.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>

void require(bool condition,const char* message) {
  if(!condition){std::fprintf(stderr,"%s\n",message);std::exit(1);}
}
int main() {
  struct Screen{float w,h,density;};
  Screen screens[]={{1080,2400,3},{2400,1080,3},{1080,1920,3},{1920,1080,3},
    {720,1280,2},{1280,720,2},{1600,2560,2},{2560,1600,2},{360,400,1},{1280,720,1}};
  for(const auto& screen:screens)for(float scale:{.8f,1.f,1.35f}) {
    auto layout=gameclub::makeTouchLayout(screen.w,screen.h,screen.density,scale,true);
    require(layout.video.h>0&&layout.video.h<=screen.h,"Vídeo fuera de pantalla");
    for(const auto& button:layout.buttons) {
      const auto& r=button.rect;
      require(r.x>=-.1f&&r.y>=-.1f&&r.w>0&&r.h>0&&r.x+r.w<=screen.w+.1f&&r.y+r.h<=screen.h+.1f,"Control fuera de pantalla");
      require(r.contains(r.x+r.w/2,r.y+r.h/2),"Centro del control inaccesible");
      if(layout.portrait)require(r.y+.1f>=layout.video.h,"Control superpuesto al vídeo vertical");
    }
    for(int a:{0,1,8,9})for(int b:{0,1,8,9})if(a<b) {
      gameclub::PadRect ar{},br{};
      for(const auto& button:layout.buttons){if(button.index==a)ar=button.rect;if(button.index==b)br=button.rect;}
      float dx=ar.x+ar.w/2-br.x-br.w/2,dy=ar.y+ar.h/2-br.y-br.h/2;
      require(std::sqrt(dx*dx+dy*dy)>layout.diameter,"Botones circulares solapados");
    }
  }
  auto portrait=gameclub::makeTouchLayout(1080,2400,3,1,true);
  require(portrait.diameter/3>=60,"Botones demasiado pequeños en móvil de alta densidad");
  auto landscape=gameclub::makeTouchLayout(2400,1080,3,1,true);
  require(landscape.diameter/3>=68,"Botones demasiado pequeños en horizontal");
  auto tv=gameclub::makeTouchLayout(1280,720,1,1,false);
  require(tv.video.h==720&&!tv.portrait,"La TV pierde superficie de vídeo");
  std::puts("30 diseños táctiles: tamaño dp, límites, separación y área de vídeo correctos.");
}
