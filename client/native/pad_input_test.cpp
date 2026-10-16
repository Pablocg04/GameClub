#include "pad_input.h"
#include <cstdio>
#include <cstdlib>
#include <limits>
void check(bool value,const char* message){if(!value){std::fprintf(stderr,"%s\n",message);std::exit(1);}}
int main(){
  gameclub::PadAxes pad;
  check(pad.mask()==0&&pad.analog(0)==0,"Entrada neutral incorrecta");
  auto input=pad.values;input[4]=-1;input[5]=-1;pad.set(input);
  check((pad.mask()&(1<<6))&&(pad.mask()&(1<<4)),"Cruceta HAT diagonal perdida");
  check(pad.relative(0,-1)<0,"Cruceta no mueve el trackball/paddle");
  input[0]=.8f;input[1]=.7f;pad.set(input);
  check((pad.mask()&(1<<7))&&(pad.mask()&(1<<5)),"Stick no genera direcciones digitales");
  check(pad.analog(0)>25000&&pad.relative(0,0)>0,"Stick no llega a la entrada analógica/ratón");
  input[4]=input[5]=0;pad.set(input);
  check((pad.mask()&(1<<7))!=0,"Soltar HAT anuló el stick");
  input={};input[2]=-.8f;input[3]=.6f;input[6]=1;pad.set(input);
  check(pad.relative(0,0)<0&&pad.relative(1,0)>0,"Stick derecho no controla el trackball");
  check((pad.mask()&(1<<12))!=0,"Gatillo perdido");
  input={};input[0]=.1f;pad.set(input);check(pad.analog(0)==0&&pad.mask()==0,"Zona muerta incorrecta");
  input[0]=std::numeric_limits<float>::quiet_NaN();pad.set(input);check(pad.analog(0)==0,"Eje inválido no filtrado");
  pad={};check(pad.mask()==0&&pad.relative(0,0)==0,"Reset mantiene entradas retenidas");
  std::puts("HAT, sticks, gatillos, analógico, trackball y reset correctos.");
}
