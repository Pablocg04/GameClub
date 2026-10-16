#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include "libretro.h"
#include "touch_layout.h"
#include "pad_input.h"
#include <algorithm>
#include <array>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <map>
#include <string>
#include <vector>
#ifdef __ANDROID__
#include <jni.h>
#endif

namespace {
SDL_Window* window = nullptr;
SDL_Renderer* renderer = nullptr;
SDL_Texture* texture = nullptr;
SDL_AudioStream* audio = nullptr;
SDL_SharedObject* library = nullptr;
unsigned width = 0, height = 0, rotation = 0;
retro_pixel_format pixelFormat = RETRO_PIXEL_FORMAT_0RGB1555;
std::vector<uint32_t> pixels;
std::array<std::array<bool, 16>, 4> buttons{};
std::array<std::array<bool, 16>, 4> tappedButtons{};
std::array<gameclub::PadAxes,4> axes{};
struct AxesPacket {int port;std::array<float,8> values;};
std::array<bool, RETROK_LAST> keyboard{};
std::map<SDL_JoystickID, SDL_Gamepad*> pads;
std::map<SDL_FingerID, int> fingers;
std::map<std::string, std::string> variables;
retro_keyboard_event_t keyboardCallback = nullptr;
std::string systemPath, savePath, reportPath, errorMessage;
bool menu = false, quit = false, touchEnabled = false, cards = false, focused = true, atari2600 = false;
int selected = 0, mouseX = 0, mouseY = 0;
uint64_t frames = 0;
uint64_t inputCount = 0;
uint64_t consumedInputs = 0;
uint64_t directionalInputs = 0, axisPackets = 0;
uint64_t audioSignals = 0;
uint64_t audioBatches = 0;
Uint64 nextInputCapture = 0;
bool diagnostics = false, screenshotSaved = false;
float aspect = 4.f / 3.f;
float touchDensity=1, touchScale=1;
gameclub::TouchLayout touchLayout{};
int layoutWidth=0, layoutHeight=0;
Uint64 captureAfter=0;
std::array<bool,16> touchHeld{};

#define CORE_FUNCTION(name) decltype(&retro_##name) core_##name = nullptr
CORE_FUNCTION(init); CORE_FUNCTION(deinit); CORE_FUNCTION(load_game); CORE_FUNCTION(unload_game);
CORE_FUNCTION(run); CORE_FUNCTION(get_system_info); CORE_FUNCTION(get_system_av_info);
CORE_FUNCTION(set_environment); CORE_FUNCTION(set_video_refresh); CORE_FUNCTION(set_audio_sample);
CORE_FUNCTION(set_audio_sample_batch); CORE_FUNCTION(set_input_poll); CORE_FUNCTION(set_input_state);
CORE_FUNCTION(set_controller_port_device); CORE_FUNCTION(get_memory_data); CORE_FUNCTION(get_memory_size);

void report(const std::string& state, const std::string& message = "") {
  std::ofstream(std::filesystem::u8path(reportPath), std::ios::trunc) << state << '\n' << message;
  SDL_Log("GameClub native: %s %s", state.c_str(), message.c_str());
}
void logCore(enum retro_log_level level, const char* format, ...) {
  if(level < RETRO_LOG_ERROR && frames>0) return;
  char text[4096]; va_list args; va_start(args, format);
  vsnprintf(text, sizeof(text), format, args); va_end(args);
  SDL_Log("core: %s", text);
  if (level >= RETRO_LOG_ERROR) errorMessage = text;
}
void setVariable(const char* key, const char* value) {
  if (!key || !value) return;
  std::string name=key;
  if(name.find("skip_disclaimer")!=std::string::npos || name.find("skip_warnings")!=std::string::npos || name.find("skip_gameinfo")!=std::string::npos) value="enabled";
  if(name.find("boot_to_osd")!=std::string::npos || name.find("boot_from_cli")!=std::string::npos) value="disabled";
  if(name.find("mouse_enable")!=std::string::npos)value="enabled";
  variables[name]=value;
}
bool environment(unsigned command, void* data) {
  switch (command) {
    case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
      pixelFormat = *static_cast<retro_pixel_format*>(data);
      return pixelFormat <= RETRO_PIXEL_FORMAT_RGB565;
    case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY: *static_cast<const char**>(data) = systemPath.c_str(); return true;
    case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY: *static_cast<const char**>(data) = savePath.c_str(); return true;
    case RETRO_ENVIRONMENT_GET_LOG_INTERFACE: static_cast<retro_log_callback*>(data)->log = logCore; return true;
    case RETRO_ENVIRONMENT_GET_CAN_DUPE: *static_cast<bool*>(data) = true; return true;
    case RETRO_ENVIRONMENT_GET_INPUT_BITMASKS: return true;
    case RETRO_ENVIRONMENT_GET_INPUT_DEVICE_CAPABILITIES: *static_cast<uint64_t*>(data)=(1ull<<RETRO_DEVICE_JOYPAD)|(1ull<<RETRO_DEVICE_ANALOG)|(1ull<<RETRO_DEVICE_MOUSE)|(1ull<<RETRO_DEVICE_KEYBOARD); return true;
    case RETRO_ENVIRONMENT_GET_INPUT_MAX_USERS: *static_cast<unsigned*>(data) = 4; return true;
    case RETRO_ENVIRONMENT_GET_LANGUAGE: *static_cast<unsigned*>(data) = RETRO_LANGUAGE_SPANISH; return true;
    case RETRO_ENVIRONMENT_GET_TARGET_REFRESH_RATE: *static_cast<float*>(data) = 60.f; return true;
    case RETRO_ENVIRONMENT_GET_AUDIO_VIDEO_ENABLE: *static_cast<int*>(data) = 3; return true;
    case RETRO_ENVIRONMENT_GET_CORE_OPTIONS_VERSION: *static_cast<unsigned*>(data) = 2; return true;
    case RETRO_ENVIRONMENT_GET_MESSAGE_INTERFACE_VERSION: *static_cast<unsigned*>(data) = 1; return true;
    case RETRO_ENVIRONMENT_SET_MESSAGE: SDL_Log("core message: %s",static_cast<retro_message*>(data)->msg); return true;
    case RETRO_ENVIRONMENT_SET_MESSAGE_EXT: SDL_Log("core message: %s",static_cast<retro_message_ext*>(data)->msg); return true;
    case RETRO_ENVIRONMENT_SET_ROTATION: rotation = *static_cast<unsigned*>(data); return true;
    case RETRO_ENVIRONMENT_SET_GEOMETRY: aspect = static_cast<retro_game_geometry*>(data)->aspect_ratio; return true;
    case RETRO_ENVIRONMENT_SET_KEYBOARD_CALLBACK: keyboardCallback = static_cast<retro_keyboard_callback*>(data)->callback; return true;
    case RETRO_ENVIRONMENT_SET_VARIABLES: {
      auto item = static_cast<const retro_variable*>(data);
      for (; item && item->key; ++item) {
        std::string text = item->value ? item->value : "";
        auto pos = text.find(';');
        if (pos != std::string::npos) { text = text.substr(pos + 1); text.erase(0, text.find_first_not_of(' ')); }
        setVariable(item->key, text.substr(0, text.find('|')).c_str());
      }
      return true;
    }
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS: {
      auto item = static_cast<const retro_core_option_definition*>(data);
      for (; item && item->key; ++item) setVariable(item->key, item->default_value ? item->default_value : item->values[0].value);
      return true;
    }
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2: {
      auto item = static_cast<retro_core_options_v2*>(data)->definitions;
      for (; item && item->key; ++item) setVariable(item->key, item->default_value ? item->default_value : item->values[0].value);
      return true;
    }
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS_INTL: return environment(RETRO_ENVIRONMENT_SET_CORE_OPTIONS, const_cast<retro_core_option_definition*>(static_cast<retro_core_options_intl*>(data)->us));
    case RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2_INTL: return environment(RETRO_ENVIRONMENT_SET_CORE_OPTIONS_V2, static_cast<retro_core_options_v2_intl*>(data)->us);
    case RETRO_ENVIRONMENT_GET_VARIABLE: {
      auto item = static_cast<retro_variable*>(data);
      auto found = variables.find(item->key);
      item->value = found == variables.end() ? nullptr : found->second.c_str();
      return item->value != nullptr;
    }
    case RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE: *static_cast<bool*>(data) = false; return true;
    case RETRO_ENVIRONMENT_SHUTDOWN: quit = true; return true;
    case RETRO_ENVIRONMENT_SET_INPUT_DESCRIPTORS:
    case RETRO_ENVIRONMENT_SET_CONTROLLER_INFO:
    case RETRO_ENVIRONMENT_SET_SUPPORT_NO_GAME:
    case RETRO_ENVIRONMENT_SET_PERFORMANCE_LEVEL: return true;
    default: return false;
  }
}
void video(const void* data, unsigned w, unsigned h, size_t pitch) {
  if (!data || data == RETRO_HW_FRAME_BUFFER_VALID || w == 0 || h == 0 || w > 8192 || h > 8192) return;
  if (!texture || w != width || h != height) {
    SDL_DestroyTexture(texture); width = w; height = h;
    texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, w, h);
    // XRGB8888 no define alpha: nunca tratar su byte alto como transparencia.
    SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_NONE);
    SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_NEAREST);
    pixels.resize(static_cast<size_t>(w) * h);
  }
  if (pixelFormat == RETRO_PIXEL_FORMAT_XRGB8888) SDL_UpdateTexture(texture, nullptr, data, static_cast<int>(pitch));
  else {
    for (unsigned y = 0; y < h; ++y) {
      auto row = reinterpret_cast<const uint16_t*>(static_cast<const uint8_t*>(data) + y * pitch);
      for (unsigned x = 0; x < w; ++x) {
        unsigned p = row[x], r, g, b;
        if (pixelFormat == RETRO_PIXEL_FORMAT_RGB565) { r = (p >> 11) & 31; g = (p >> 5) & 63; b = p & 31; g = (g << 2) | (g >> 4); }
        else { r = (p >> 10) & 31; g = (p >> 5) & 31; b = p & 31; g = (g << 3) | (g >> 2); }
        r = (r << 3) | (r >> 2); b = (b << 3) | (b >> 2);
        pixels[y * w + x] = 0xff000000u | (r << 16) | (g << 8) | b;
      }
    }
    SDL_UpdateTexture(texture, nullptr, pixels.data(), w * 4);
  }
  ++frames;
}
size_t audioBatch(const int16_t* data, size_t count) {
  if(diagnostics&&count)++audioBatches;
  if(diagnostics&&data&&count&&std::any_of(data,data+count*2,[](int16_t sample){return sample!=0;}))++audioSignals;
  if (audio && !menu && focused && SDL_GetAudioStreamQueued(audio) < 192000)
    SDL_PutAudioStreamData(audio, data, static_cast<int>(count * 4));
  return count;
}
void audioSample(int16_t left, int16_t right) { int16_t sample[]{left, right}; audioBatch(sample, 1); }
void inputPoll() {}
bool buttonHeld(unsigned port,unsigned id,bool taps=true) {
  return port<4&&id<16&&(buttons[port][id]||((axes[port].mask()>>id)&1)||(port==0&&touchHeld[id])||(taps&&tappedButtons[port][id]));
}
int16_t inputStateValue(unsigned port, unsigned device, unsigned index, unsigned id) {
  if (port >= 4 || menu || !focused) return 0;
  device &= RETRO_DEVICE_MASK;
  if (device == RETRO_DEVICE_JOYPAD) {
    if (id == RETRO_DEVICE_ID_JOYPAD_MASK) { unsigned mask = 0; for (int i = 0; i < 16; ++i) if (buttonHeld(port,i)) mask |= 1u << i; if(atari2600&&buttonHeld(port,RETRO_DEVICE_ID_JOYPAD_A))mask|=1u<<RETRO_DEVICE_ID_JOYPAD_B; return static_cast<int16_t>(mask); }
    return buttonHeld(port,id)||(atari2600&&id==RETRO_DEVICE_ID_JOYPAD_B&&buttonHeld(port,RETRO_DEVICE_ID_JOYPAD_A));
  }
  if (device == RETRO_DEVICE_ANALOG && index < 2 && id < 2) return axes[port].analog(index*2+id);
  if (device == RETRO_DEVICE_KEYBOARD) return id < keyboard.size() && keyboard[id];
  if (device == RETRO_DEVICE_MOUSE) {
    if (id == RETRO_DEVICE_ID_MOUSE_X) { int digital=static_cast<int>(buttonHeld(port,7))-static_cast<int>(buttonHeld(port,6));int v=(port==0?mouseX:0)+axes[port].relative(0,digital);if(port==0)mouseX=0;return static_cast<int16_t>(v); }
    if (id == RETRO_DEVICE_ID_MOUSE_Y) { int digital=static_cast<int>(buttonHeld(port,5))-static_cast<int>(buttonHeld(port,4));int v=(port==0?mouseY:0)+axes[port].relative(1,digital);if(port==0)mouseY=0;return static_cast<int16_t>(v); }
    if (id == RETRO_DEVICE_ID_MOUSE_LEFT) return buttonHeld(port,8);
  }
  return 0;
}
int16_t inputState(unsigned port,unsigned device,unsigned index,unsigned id) {
  int16_t value=inputStateValue(port,device,index,id);
  if(value)++consumedInputs;
  unsigned kind=device&RETRO_DEVICE_MASK;
  if(value&&((kind==RETRO_DEVICE_JOYPAD&&((id>=4&&id<=7)||(id==RETRO_DEVICE_ID_JOYPAD_MASK&&(value&0xf0))))||kind==RETRO_DEVICE_ANALOG||(kind==RETRO_DEVICE_MOUSE&&id<2)))++directionalInputs;
  return value;
}
void releaseInputs() {
  for (unsigned key = 0; key < keyboard.size(); ++key) if (keyboard[key] && keyboardCallback) keyboardCallback(false, key, 0, 0);
  buttons = {}; tappedButtons={}; axes = {}; keyboard = {}; fingers.clear(); touchHeld={};mouseX = mouseY = 0;
}
void updateCardKey(int index) {
  if(!cards)return;
  const unsigned keys[]{RETROK_x,RETROK_v,RETROK_5,RETROK_1,RETROK_UP,RETROK_DOWN,RETROK_LEFT,RETROK_RIGHT,RETROK_z,RETROK_c,RETROK_b,RETROK_2,RETROK_n,RETROK_m,RETROK_q,RETROK_p};
  unsigned key=keys[index];bool down=buttonHeld(0,index,false);
  if(keyboard[key]==down)return;
  keyboard[key]=down;
  if(keyboardCallback){keyboardCallback(down,key,down&&key<128?key:0,0);if(down)++consumedInputs;}
}
void openMenu() { menu = true; selected = 0; releaseInputs(); if (audio) SDL_ClearAudioStream(audio); report("menu"); }
void press(int index, bool down, unsigned port = 0, bool touch=false) {
  if (index < 0 || index >= 16 || port >= 4) return;
  if(diagnostics && down)SDL_Log("controller button=%d menu=%d selected=%d",index,menu,selected);
  if (menu) {
    if (down && (index == 4 || index == 6)) selected = 0;
    if (down && (index == 5 || index == 7)) selected = 1;
    if (down && index == 0) { menu = false; releaseInputs(); }
    if (down && index == 8) { if (selected == 1) quit = true; else { menu = false; releaseInputs(); } }
    return;
  }
  if(touch)touchHeld[index]=down;else buttons[port][index]=down;
  if(down)tappedButtons[port][index]=true;
  if(down) ++inputCount;
  if (down && buttonHeld(port,2,false) && buttonHeld(port,3,false)) { openMenu(); return; }
  if(port==0)updateCardKey(index);
}
void applyAxes(unsigned port,const std::array<float,8>& values) {
  if(port>=4)return;
  auto previous=axes[port].mask();axes[port].set(values);auto mask=axes[port].mask();++axisPackets;
  for(int i=0;i<16;++i) {
    bool down=(mask&(1<<i))!=0;
    if(down&&!(previous&(1<<i))){if(menu)press(i,true,port);else {tappedButtons[port][i]=true;++inputCount;}}
    if(port==0)updateCardKey(i);
  }
}
void resetPort(int port) {
  if(port<0){releaseInputs();return;}
  if(port>=4)return;
  buttons[port]={};tappedButtons[port]={};axes[port]={};
  if(port==0){touchHeld={};fingers.clear();for(int i=0;i<16;++i)updateCardKey(i);}
}
int padIndex(SDL_GamepadButton button) {
  switch (button) {
    case SDL_GAMEPAD_BUTTON_SOUTH: return 8; case SDL_GAMEPAD_BUTTON_EAST: return 0;
    case SDL_GAMEPAD_BUTTON_WEST: return 9; case SDL_GAMEPAD_BUTTON_NORTH: return 1;
    case SDL_GAMEPAD_BUTTON_BACK: return 2; case SDL_GAMEPAD_BUTTON_START: return 3;
    case SDL_GAMEPAD_BUTTON_DPAD_UP: return 4; case SDL_GAMEPAD_BUTTON_DPAD_DOWN: return 5;
    case SDL_GAMEPAD_BUTTON_DPAD_LEFT: return 6; case SDL_GAMEPAD_BUTTON_DPAD_RIGHT: return 7;
    case SDL_GAMEPAD_BUTTON_LEFT_SHOULDER: return 10; case SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER: return 11;
    case SDL_GAMEPAD_BUTTON_LEFT_STICK: return 14; case SDL_GAMEPAD_BUTTON_RIGHT_STICK: return 15;
    default: return -1;
  }
}
void text(float x, float y, const char* label, float scale = 2) {
  SDL_SetRenderScale(renderer, scale, scale);
  SDL_RenderDebugText(renderer, x / scale, y / scale, label);
  SDL_SetRenderScale(renderer, 1, 1);
}
SDL_FRect rectSDL(const gameclub::PadRect& rect) {return {rect.x,rect.y,rect.w,rect.h};}
void updateTouchInputs() {
  std::array<bool,16> held{};
  for(const auto& finger:fingers) {
    int index=finger.second;
    if(index>=16&&index<=19){held[index<18?4:5]=true;held[index%2==0?6:7]=true;}
    else if(index>=0&&index<16)held[index]=true;
  }
  for(int i=0;i<16;++i)if(held[i]!=touchHeld[i]){press(i,held[i],0,true);if(menu)break;}
}
void circle(const SDL_FRect& rect, bool pad=false, bool active=false) {
  float x=rect.x+rect.w/2,y=rect.y+rect.h/2,r=rect.w*.46f;
  SDL_Vertex vertices[108]; SDL_FPoint line[37];
  for(int i=0;i<36;++i) {
    float a=i*6.2831853f/36,b=(i+1)*6.2831853f/36;
    SDL_FColor color{active?.62f:.38f,active?.62f:.38f,active?.65f:.4f,pad?.65f:.72f};
    vertices[3*i]={{x,y},color,{0,0}};
    vertices[3*i+1]={{x+std::cos(a)*r,y+std::sin(a)*r},color,{0,0}};
    vertices[3*i+2]={{x+std::cos(b)*r,y+std::sin(b)*r},color,{0,0}};
    line[i]={x+std::cos(a)*r,y+std::sin(a)*r};
  }
  line[36]=line[0];SDL_RenderGeometry(renderer,nullptr,vertices,108,nullptr,0);
  SDL_SetRenderDrawColor(renderer,210,210,215,160);SDL_RenderLines(renderer,line,37);
}
void layout(int w, int h) {
  if(w==layoutWidth&&h==layoutHeight)return;
  layoutWidth=w;layoutHeight=h;
  screenshotSaved=false;
  captureAfter=SDL_GetTicks()+600;
  // SDL debe actualizar también su transformación lógica al rotar la superficie Android.
  SDL_SetRenderLogicalPresentation(renderer,w,h,SDL_LOGICAL_PRESENTATION_STRETCH);
  SDL_SetRenderViewport(renderer,nullptr);
  SDL_SetRenderScale(renderer,1,1);
  releaseInputs();
  touchLayout=gameclub::makeTouchLayout(static_cast<float>(w),static_cast<float>(h),touchDensity,touchScale,touchEnabled);
  if(diagnostics) {
    std::ofstream out(std::filesystem::u8path(reportPath+".layout"));
    out<<"{\"width\":"<<w<<",\"height\":"<<h<<",\"density\":"<<touchDensity<<",\"portrait\":"<<(touchLayout.portrait?"true":"false")<<",\"diameter\":"<<touchLayout.diameter<<",\"videoHeight\":"<<touchLayout.video.h<<",\"buttons\":[";
    bool first=true;
    for(const auto& b:touchLayout.buttons){if(!first)out<<',';first=false;out<<"{\"index\":"<<b.index<<",\"x\":"<<b.rect.x+b.rect.w/2<<",\"y\":"<<b.rect.y+b.rect.h/2<<",\"w\":"<<b.rect.w<<",\"h\":"<<b.rect.h<<'}';}
    out<<"]}";
  }
}
void textUI(float x,float y,const char* label,float dp,float maxWidth) {
  float scale=std::max(.75f,std::min(dp*touchDensity/8,maxWidth/(std::max<size_t>(1,std::strlen(label))*8)));
  text(x,y,label,scale);
}
void drawPad() {
  SDL_FRect pad=rectSDL(touchLayout.dpad);circle(pad,true);
  float cx=pad.x+pad.w/2,cy=pad.y+pad.h/2,arm=pad.w*.2f;
  SDL_FRect horizontal{cx-pad.w*.37f,cy-arm/2,pad.w*.74f,arm},vertical{cx-arm/2,cy-pad.h*.37f,arm,pad.h*.74f};
  SDL_SetRenderDrawColor(renderer,185,185,190,210);SDL_RenderFillRect(renderer,&horizontal);SDL_RenderFillRect(renderer,&vertical);
  for(int i=0;i<4;++i){
    float angle=i*1.5707963f,dx=std::sin(angle),dy=-std::cos(angle),px=cx+dx*pad.w*.3f,py=cy+dy*pad.h*.3f,s=pad.w*.045f;
    SDL_FColor color{1,1,1,.95f};
    SDL_Vertex vertices[3]={{{px+dx*s,py+dy*s},color,{0,0}},{{px-dx*s-dy*s,py-dy*s+dx*s},color,{0,0}},{{px-dx*s+dy*s,py-dy*s-dx*s},color,{0,0}}};
    SDL_RenderGeometry(renderer,nullptr,vertices,3,nullptr,0);
  }
}
void draw() {
  int w, h; SDL_GetRenderOutputSize(renderer, &w, &h); layout(w, h);
  SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255); SDL_RenderClear(renderer);
  if (texture) {
    float ratio = aspect > 0 ? aspect : ((rotation & 1) ? static_cast<float>(height) / width : static_cast<float>(width) / height);
    const auto& area=touchLayout.video;
    float vw = std::min(area.w, area.h * ratio), vh = vw / ratio;
    SDL_FRect rect{area.x+(area.w-vw)/2, area.y+(area.h-vh)/2, vw, vh};
    if (rotation & 1) rect = {area.x+(area.w-vh)/2, area.y+(area.h-vw)/2, vh, vw};
    SDL_RenderTextureRotated(renderer, texture, nullptr, &rect, -90.0 * rotation, nullptr, SDL_FLIP_NONE);
  }
  SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND);
  if(touchEnabled&&!menu)drawPad();
  if (touchEnabled && !menu) for (const auto& button : touchLayout.buttons) {
    if(!button.label[0])continue;
    auto rect=rectSDL(button.rect);
    bool active=button.index>=0&&button.index<16&&buttonHeld(0,button.index,false);
    if(button.round)circle(rect,false,active);
    else {
      SDL_SetRenderDrawColor(renderer,active?160:95,active?160:95,active?165:100,180);SDL_RenderFillRect(renderer,&rect);
      SDL_SetRenderDrawColor(renderer,210,210,215,160);SDL_RenderRect(renderer,&rect);
    }
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 230);
    float font=(button.round?24.f:14.f)*touchDensity;
    font=std::min(font,rect.w*.85f/std::max<size_t>(1,std::strlen(button.label)));
    text(rect.x+(rect.w-std::strlen(button.label)*font)/2,rect.y+(rect.h-font)/2,button.label,font/8);
  }
  if (menu) {
    SDL_SetRenderDrawColor(renderer, 16, 17, 28, 240); SDL_RenderFillRect(renderer, nullptr);
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    textUI(w*.15f,h*.22f,"MENU DEL JUEGO",24,w*.7f);
    for (int i = 0; i < 2; ++i) {
      SDL_FRect rect{w*.12f, h*(.4f + i*.2f), w*.76f, h*.14f};
      SDL_SetRenderDrawColor(renderer, i == selected ? 100 : 37, i == selected ? 78 : 39, i == selected ? 210 : 61, 255);
      SDL_RenderFillRect(renderer, &rect); SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
      textUI(rect.x+rect.w*.05f,rect.y+rect.h*.35f,i==0?"Continuar":"Guardar y salir",20,rect.w*.9f);
    }
    textUI(w*.15f,h*.84f,"Cruceta: elegir / A: aceptar",14,w*.7f);
    textUI(w*.15f,h*.9f,"B/Atras: continuar",14,w*.7f);
  }
  if(diagnostics && !screenshotSaved && !menu && frames>600 && SDL_GetTicks()>=captureAfter) {
    SDL_Surface* image=SDL_RenderReadPixels(renderer,nullptr);
    if(image){screenshotSaved=SDL_SaveBMP(image,(reportPath+".bmp").c_str());SDL_DestroySurface(image);}
  }
  if(diagnostics&&!menu&&inputCount>=8&&frames>900&&SDL_GetTicks()>=nextInputCapture){SDL_Surface* image=SDL_RenderReadPixels(renderer,nullptr);if(image){SDL_SaveBMP(image,(reportPath+".after.bmp").c_str());SDL_DestroySurface(image);}nextInputCapture=SDL_GetTicks()+1000;}
  SDL_RenderPresent(renderer);
}
void point(float x, float y, SDL_FingerID finger, bool down) {
  int w,h; SDL_GetRenderOutputSize(renderer,&w,&h);
  if (!down) { fingers.erase(finger);updateTouchInputs();return; }
  if (menu) { if(y > h*.4f && y < h*.74f) { selected=y < h*.58f ? 0:1; press(8,true); } return; }
  if (!touchEnabled) return;
  int hit=-2;
  for (const auto& button:touchLayout.buttons) if(button.rect.contains(x,y)) {
    if(button.round){float dx=x-(button.rect.x+button.rect.w/2),dy=y-(button.rect.y+button.rect.h/2);if(dx*dx+dy*dy>button.rect.w*button.rect.w/4)continue;}
    hit=button.index;break;
  }
  auto old=fingers.find(finger);
  if(old!=fingers.end() && old->second==hit) return;
  if(old!=fingers.end())fingers.erase(old);
  if(hit == -1) {openMenu();return;}
  if(hit>=0)fingers[finger]=hit;
  updateTouchInputs();
}
void events() {
  SDL_Event event;
  while (SDL_PollEvent(&event)) {
    switch(event.type) {
      case SDL_EVENT_QUIT: if (menu) quit=true; else openMenu(); break;
      case SDL_EVENT_WINDOW_FOCUS_LOST: focused=false; releaseInputs(); if(audio)SDL_ClearAudioStream(audio); break;
      case SDL_EVENT_WINDOW_FOCUS_GAINED: focused=true; break;
      case SDL_EVENT_GAMEPAD_ADDED: { auto pad=SDL_OpenGamepad(event.gdevice.which); if(pad)pads[event.gdevice.which]=pad; break; }
      case SDL_EVENT_GAMEPAD_REMOVED: { auto pad=pads.find(event.gdevice.which);if(pad!=pads.end()){SDL_CloseGamepad(pad->second);pads.erase(pad);}releaseInputs();break; }
      case SDL_EVENT_GAMEPAD_BUTTON_DOWN:
      case SDL_EVENT_GAMEPAD_BUTTON_UP: {
        unsigned port=0; for(auto& item:pads){if(item.first==event.gbutton.which)break; ++port;}
        if(event.gbutton.button==SDL_GAMEPAD_BUTTON_GUIDE && event.gbutton.down)openMenu();
        else press(padIndex(static_cast<SDL_GamepadButton>(event.gbutton.button)),event.gbutton.down,port);
        break;
      }
      case SDL_EVENT_GAMEPAD_AXIS_MOTION: {
        unsigned port=0;for(auto& item:pads){if(item.first==event.gaxis.which)break;++port;} if(port>=4)break;
        int axis=event.gaxis.axis;if(axis>=6)break;
        auto values=axes[port].values;values[axis<4?axis:axis+2]=event.gaxis.value/32767.f;applyAxes(port,values);
        break;
      }
      case SDL_EVENT_KEY_DOWN:
      case SDL_EVENT_KEY_UP: {
        bool down=event.key.down; if(event.key.repeat)break;
        SDL_Keycode key=event.key.key;
        if((key==SDLK_ESCAPE||key==SDLK_AC_BACK)&&down){if(menu){menu=false;releaseInputs();}else openMenu();break;}
        int index=-1;
        switch(key){case SDLK_UP:index=4;break;case SDLK_DOWN:index=5;break;case SDLK_LEFT:index=6;break;case SDLK_RIGHT:index=7;break;case SDLK_RETURN:index=menu?8:3;break;case SDLK_5:index=2;break;case SDLK_1:index=3;break;case SDLK_Z:index=8;break;case SDLK_X:index=0;break;case SDLK_C:index=9;break;case SDLK_V:index=1;break;case SDLK_B:index=10;break;}
        if(index>=0)press(index,down);
        unsigned retroKey=key<128?key:RETROK_UNKNOWN;
        if(key==SDLK_TAB)retroKey=RETROK_TAB;
        if(retroKey>0&&retroKey<keyboard.size()) {keyboard[retroKey]=down;if(keyboardCallback)keyboardCallback(down,retroKey,down&&key<128?key:0,0);}
        break;
      }
      case SDL_EVENT_FINGER_DOWN: case SDL_EVENT_FINGER_MOTION: case SDL_EVENT_FINGER_UP: case SDL_EVENT_FINGER_CANCELED: {
        int w,h;SDL_GetRenderOutputSize(renderer,&w,&h);point(event.tfinger.x*w,event.tfinger.y*h,event.tfinger.fingerID,event.type!=SDL_EVENT_FINGER_UP&&event.type!=SDL_EVENT_FINGER_CANCELED);break;
      }
      case SDL_EVENT_MOUSE_BUTTON_DOWN:case SDL_EVENT_MOUSE_BUTTON_UP:
        if(event.button.which!=SDL_TOUCH_MOUSEID)point(event.button.x,event.button.y,-1,event.button.down);break;
      case SDL_EVENT_MOUSE_MOTION: if(event.motion.which!=SDL_TOUCH_MOUSEID){mouseX+=static_cast<int>(event.motion.xrel);mouseY+=static_cast<int>(event.motion.yrel);}break;
      default:
        if(event.type==SDL_EVENT_USER && event.user.code>=0 && event.user.code<64)press(event.user.code%16,reinterpret_cast<intptr_t>(event.user.data1)!=0,event.user.code/16);
        if(event.type==SDL_EVENT_USER && event.user.code==100){if(diagnostics)SDL_Log("menu command active=%d",menu);if(menu){menu=false;releaseInputs();}else openMenu();}
        if(event.type==SDL_EVENT_USER && event.user.code==200){auto packet=static_cast<AxesPacket*>(event.user.data1);applyAxes(packet->port,packet->values);delete packet;}
        if(event.type==SDL_EVENT_USER && event.user.code==201)resetPort(static_cast<int>(reinterpret_cast<intptr_t>(event.user.data1)));
        break;
    }
  }
}
void saveRAM(bool load) {
  auto length=core_get_memory_size(RETRO_MEMORY_SAVE_RAM);auto data=core_get_memory_data(RETRO_MEMORY_SAVE_RAM);
  if(!length||!data||length>128*1024*1024)return;
  auto path=std::filesystem::u8path(savePath)/"battery.srm";
  if(load){std::ifstream file(path,std::ios::binary);if(file)file.read(static_cast<char*>(data),length);}
  else {std::ofstream file(path,std::ios::binary|std::ios::trunc);file.write(static_cast<char*>(data),length);}
}
}

#ifdef __ANDROID__
extern "C" JNIEXPORT void JNICALL Java_com_gameclub_gameclub_NativeGameActivity_nativeButton(JNIEnv*,jobject,jint index,jboolean down,jint port){
  SDL_Event event{};event.type=SDL_EVENT_USER;event.user.code=index+16*std::clamp(static_cast<int>(port),0,3);event.user.data1=reinterpret_cast<void*>(static_cast<intptr_t>(down));SDL_PushEvent(&event);
}
extern "C" JNIEXPORT void JNICALL Java_com_gameclub_gameclub_NativeGameActivity_nativeMenu(JNIEnv*,jobject){SDL_Event event{};event.type=SDL_EVENT_USER;event.user.code=100;SDL_PushEvent(&event);}
extern "C" JNIEXPORT void JNICALL Java_com_gameclub_gameclub_NativeGameActivity_nativeAxes(JNIEnv* env,jobject,jfloatArray input,jint port){
  if(env->GetArrayLength(input)!=8||port<0||port>=4)return;
  auto packet=new AxesPacket{};packet->port=port;env->GetFloatArrayRegion(input,0,8,packet->values.data());
  SDL_Event event{};event.type=SDL_EVENT_USER;event.user.code=200;event.user.data1=packet;if(!SDL_PushEvent(&event))delete packet;
}
extern "C" JNIEXPORT void JNICALL Java_com_gameclub_gameclub_NativeGameActivity_nativeReset(JNIEnv*,jobject,jint port){SDL_Event event{};event.type=SDL_EVENT_USER;event.user.code=201;event.user.data1=reinterpret_cast<void*>(static_cast<intptr_t>(port));SDL_PushEvent(&event);}
#endif

int main(int argc,char** argv) {
  if(argc<6)return 2;
  std::string corePath=argv[1],gamePath=argv[2];savePath=argv[3];reportPath=argv[4];
  touchEnabled=std::string(argv[5])=="touch";cards=argc>6&&std::string(argv[6])=="cards";
  atari2600=argc>6&&std::string(argv[6])=="atari2600";
  std::string orientation="landscape";
  for(int i=7;i<argc;++i){std::string arg=argv[i];
    if(arg=="verify")diagnostics=true;
    if(arg.rfind("--touch-density=",0)==0)touchDensity=std::clamp(std::strtof(arg.c_str()+16,nullptr),.75f,8.f);
    if(arg.rfind("--touch-scale=",0)==0)touchScale=std::clamp(std::strtof(arg.c_str()+14,nullptr),.8f,1.35f);
    if(arg.rfind("--orientation=",0)==0)orientation=arg.substr(14);
  }
  systemPath=std::filesystem::u8path(gamePath).parent_path().u8string();
  std::filesystem::current_path(std::filesystem::u8path(systemPath));
  std::filesystem::create_directories(std::filesystem::u8path(savePath));
  report("loading");
  SDL_SetHint(SDL_HINT_ORIENTATIONS,orientation=="portrait"?"Portrait PortraitUpsideDown":orientation=="auto"?"Portrait PortraitUpsideDown LandscapeLeft LandscapeRight":"LandscapeLeft LandscapeRight");
  SDL_SetHint(SDL_HINT_ANDROID_TRAP_BACK_BUTTON,"1");
  if(!SDL_Init(SDL_INIT_VIDEO|SDL_INIT_AUDIO|SDL_INIT_GAMEPAD)) {report("error",SDL_GetError());return 3;}
  SDL_DisableScreenSaver();
  window=SDL_CreateWindow("GameClub - Emulacion nativa",orientation=="portrait"?720:1280,orientation=="portrait"?1280:720,SDL_WINDOW_FULLSCREEN|SDL_WINDOW_RESIZABLE);
  renderer=SDL_CreateRenderer(window,nullptr);
  if(!window||!renderer){report("error",SDL_GetError());SDL_Quit();return 3;}
  SDL_SetRenderVSync(renderer,0);SDL_HideCursor();
  library=SDL_LoadObject(corePath.c_str());
  if(!library){report("error",SDL_GetError());SDL_Quit();return 4;}
#define LOAD(name) core_##name=reinterpret_cast<decltype(core_##name)>(SDL_LoadFunction(library,"retro_" #name));if(!core_##name){report("error","Motor libretro incompleto: " #name);return 4;}
  LOAD(init);LOAD(deinit);LOAD(load_game);LOAD(unload_game);LOAD(run);LOAD(get_system_info);LOAD(get_system_av_info);
  LOAD(set_environment);LOAD(set_video_refresh);LOAD(set_audio_sample);LOAD(set_audio_sample_batch);LOAD(set_input_poll);LOAD(set_input_state);
  LOAD(set_controller_port_device);LOAD(get_memory_data);LOAD(get_memory_size);
  core_set_environment(environment);core_set_video_refresh(video);core_set_audio_sample(audioSample);core_set_audio_sample_batch(audioBatch);core_set_input_poll(inputPoll);core_set_input_state(inputState);
  core_init();
  if(variables.count("nestopia_blargg_ntsc_filter"))variables["nestopia_blargg_ntsc_filter"]="disabled";
  for(auto& item:variables){
    if(item.first.find("skip_gameinfo")!=std::string::npos)item.second="enabled";
    if(item.first.find("boot_to_osd")!=std::string::npos||item.first.find("boot_from_cli")!=std::string::npos)item.second="disabled";
  }
  retro_system_info info{};core_get_system_info(&info);
  if(diagnostics)std::ofstream(std::filesystem::u8path(reportPath+".engine"))<<info.library_name<<" "<<info.library_version;
  std::vector<char> content;
  if(!info.need_fullpath){std::ifstream file(std::filesystem::u8path(gamePath),std::ios::binary);content.assign(std::istreambuf_iterator<char>(file),{});}
  retro_game_info game{gamePath.c_str(),content.empty()?nullptr:content.data(),content.size(),nullptr};
  report("loading","retro_load_game");
  if(!core_load_game(&game)){report("error",errorMessage.empty()?"El motor rechazo el juego. Comprueba el formato y los archivos necesarios.":errorMessage);core_deinit();SDL_Quit();return 5;}
  report("loading","retro_set_controller_port_device");
  for(unsigned port=0;port<4;++port)core_set_controller_port_device(port,RETRO_DEVICE_JOYPAD);
  report("loading","retro_get_system_av_info");
  retro_system_av_info av{};core_get_system_av_info(&av);aspect=av.geometry.aspect_ratio;
  if(diagnostics){std::ofstream options(std::filesystem::u8path(reportPath+".options"));for(const auto& item:variables)options<<item.first<<"="<<item.second<<"\n";options<<"sample_rate="<<av.timing.sample_rate<<"\nfps="<<av.timing.fps<<"\n";}
  SDL_AudioSpec spec{SDL_AUDIO_S16,2,static_cast<int>(av.timing.sample_rate>0?av.timing.sample_rate:48000)};
  audio=SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK,&spec,nullptr,nullptr);if(audio)SDL_ResumeAudioStreamDevice(audio);
  saveRAM(true);
  double fps=av.timing.fps>1?av.timing.fps:60;uint64_t step=static_cast<uint64_t>(1000000000.0/fps),next=SDL_GetTicksNS(),last=next,begin=next,oldFrames=0,lastSave=next;
  while(!quit){
    events();
    if(!menu&&focused){core_run();tappedButtons={};}
    draw();
    auto now=SDL_GetTicksNS();
    if(!texture&&now-begin>30000000000ull){errorMessage="El motor no produjo video. "+errorMessage;break;}
    if(now-last>2000000000ull&&!menu){double speed=(frames-oldFrames)*1e9/(now-last);report("running",std::to_string(speed)+"\nframes="+std::to_string(frames)+"\ninputs="+std::to_string(inputCount)+"\nconsumed="+std::to_string(consumedInputs)+"\ndirections="+std::to_string(directionalInputs)+"\naxis_packets="+std::to_string(axisPackets)+"\naudio_signals="+std::to_string(audioSignals)+"\naudio_batches="+std::to_string(audioBatches));oldFrames=frames;last=now;}
    if(now-lastSave>30000000000ull){saveRAM(false);lastSave=now;}
    next+=step;if(next>now)SDL_DelayPrecise(next-now);else if(now-next>step*3)next=now;
  }
  releaseInputs();saveRAM(false);core_unload_game();core_deinit();
  report(texture?"closed":"error",errorMessage);
  for(auto& pad:pads)SDL_CloseGamepad(pad.second);
  SDL_DestroyAudioStream(audio);SDL_DestroyTexture(texture);SDL_DestroyRenderer(renderer);SDL_DestroyWindow(window);SDL_UnloadObject(library);SDL_Quit();
  return texture?0:6;
}
