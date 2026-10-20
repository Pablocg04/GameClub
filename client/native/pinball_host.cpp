// VPX remains an unmodified child process. This host owns focus, pad input and the pause menu.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <SDL3/SDL.h>
#include "pinball_host.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>

namespace gameclub {
namespace {
constexpr Uint32 menuEvent = SDL_EVENT_USER + 15;
constexpr WORD leftFlip = 0x2a, rightFlip = 0x36, coin = 0x06, start = 0x02, launch = 0x1c;
constexpr WORD nudgeLeft = 0x2c, nudgeRight = 0x35, nudgeCenter = 0x39;
DWORD enginePid = 0;
bool interceptedMenuKey = false;

DWORD foregroundPid() {
  DWORD pid=0;GetWindowThreadProcessId(GetForegroundWindow(),&pid);return pid;
}
LRESULT CALLBACK keyboardHook(int code, WPARAM message, LPARAM data) {
  if(code==HC_ACTION) {
    const auto* key=reinterpret_cast<KBDLLHOOKSTRUCT*>(data);
    if(key->vkCode==VK_ESCAPE || key->vkCode==VK_F1 || key->vkCode=='P') {
      const bool down=message==WM_KEYDOWN || message==WM_SYSKEYDOWN;
      if(enginePid && foregroundPid()==enginePid) {
        if(down && !interceptedMenuKey){SDL_Event event{};event.type=menuEvent;SDL_PushEvent(&event);}
        interceptedMenuKey=down;return 1;
      }
      if(!down && interceptedMenuKey){interceptedMenuKey=false;return 1;}
    }
  }
  return CallNextHookEx(nullptr,code,message,data);
}

struct WindowSearch {DWORD pid; HWND handle=nullptr;};
BOOL CALLBACK findPlayfield(HWND handle, LPARAM data) {
  auto& search=*reinterpret_cast<WindowSearch*>(data);DWORD pid=0;
  GetWindowThreadProcessId(handle,&pid);
  wchar_t title[256]{};GetWindowTextW(handle,title,256);
  if(pid==search.pid && IsWindowVisible(handle) && std::wstring(title)==L"Visual Pinball Player") {
    search.handle=handle;return FALSE;
  }
  return TRUE;
}
HWND playfield() {WindowSearch search{enginePid};EnumWindows(findPlayfield,reinterpret_cast<LPARAM>(&search));return search.handle;}
void activate(HWND window) {
  if(!window)return;
  // Do not call SetFocus/SetActiveWindow on the VPX thread: those synchronous
  // cross-thread calls can stall startup. Share only the foreground permission
  // long enough to activate our own menu or its owned player window.
  if(!IsWindowVisible(window))ShowWindowAsync(window,SW_SHOWNOACTIVATE);
  const DWORD foregroundThread=GetWindowThreadProcessId(GetForegroundWindow(),nullptr);
  const DWORD current=GetCurrentThreadId();
  const bool attached=GetForegroundWindow()!=window && foregroundThread && foregroundThread!=current && AttachThreadInput(current,foregroundThread,TRUE);
  SetForegroundWindow(window);
  if(attached)AttachThreadInput(current,foregroundThread,FALSE);
}
void sendKey(WORD scan, bool down) {
  INPUT input{};input.type=INPUT_KEYBOARD;input.ki.wScan=scan;
  input.ki.wVk=static_cast<WORD>(MapVirtualKeyW(scan,MAPVK_VSC_TO_VK_EX));
  input.ki.dwFlags=down?0:KEYEVENTF_KEYUP;
  SendInput(1,&input,sizeof(input));
}

struct Pad {
  SDL_Gamepad* gamepad=nullptr;
  SDL_Joystick* joystick=nullptr;
  bool back=false,start=false,north=false;
  bool button(SDL_GamepadButton which) const {
    if(gamepad)return SDL_GetGamepadButton(gamepad,which);
    int raw=-1;
    switch(which) {
      case SDL_GAMEPAD_BUTTON_SOUTH:raw=0;break;case SDL_GAMEPAD_BUTTON_EAST:raw=1;break;
      case SDL_GAMEPAD_BUTTON_WEST:raw=2;break;case SDL_GAMEPAD_BUTTON_NORTH:raw=3;break;
      case SDL_GAMEPAD_BUTTON_LEFT_SHOULDER:raw=4;break;case SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER:raw=5;break;
      case SDL_GAMEPAD_BUTTON_BACK:raw=6;break;case SDL_GAMEPAD_BUTTON_START:raw=7;break;
      default:break;
    }
    if(raw>=0 && raw<SDL_GetNumJoystickButtons(joystick))return SDL_GetJoystickButton(joystick,raw);
    const auto hat=SDL_GetNumJoystickHats(joystick)?SDL_GetJoystickHat(joystick,0):0;
    switch(which) {
      case SDL_GAMEPAD_BUTTON_DPAD_UP:return hat&SDL_HAT_UP;case SDL_GAMEPAD_BUTTON_DPAD_DOWN:return hat&SDL_HAT_DOWN;
      case SDL_GAMEPAD_BUTTON_DPAD_LEFT:return hat&SDL_HAT_LEFT;case SDL_GAMEPAD_BUTTON_DPAD_RIGHT:return hat&SDL_HAT_RIGHT;
      default:return false;
    }
  }
  Sint16 axis(SDL_GamepadAxis which) const {return gamepad?SDL_GetGamepadAxis(gamepad,which):0;}
  void close(){if(gamepad)SDL_CloseGamepad(gamepad);else if(joystick)SDL_CloseJoystick(joystick);}
};

class Host {
 public:
  SDL_Window* window=nullptr;
  SDL_Renderer* renderer=nullptr;
  HWND ownWindow=nullptr;
  SDL_Process* child=nullptr;
  HANDLE job=nullptr;
  std::filesystem::path engine, table, preferences;
  std::ofstream diagnostics;
  std::map<SDL_JoystickID,Pad> pads;
  std::set<WORD> held;
  std::map<WORD,Uint64> pulses;
  bool menu=false, ready=false, stopping=false, restarting=false, initialize=false, intro=true, blocked=true, testOnlyPad=false, warming=false;
  bool prevUp=false,prevDown=false,prevAccept=false,prevCancel=false;
  int selected=0, result=0;
  int initializationPasses=2;
  bool saveInitializationMarker=false;
  bool finishInitializationAfterRestart=false;
  Uint64 startedAt=0, stoppedAt=0, focusUntil=0, lastTick=0, initializationTime=0, bootTime=0, warmupMs=0;
  Uint64 lastCoinTime=0, pendingStartAt=0;
  Uint64 nextCoinAt=0;
  int queuedCoins=0;
  uintmax_t logOffset=0;
  Uint64 lastDraw=0;
  SDL_JoystickID virtualId=0;
  std::string pendingTestInput;

  void record(const std::string& value) {
    diagnostics<<SDL_GetTicks()<<' '<<value<<std::endl;
    std::printf("GAMECLUB_PINBALL_STATE %s\n",value.c_str());std::fflush(stdout);
  }
  void release() {
    for(auto scan:held)sendKey(scan,false);
    held.clear();pulses.clear();pendingStartAt=0;queuedCoins=0;
  }
  void focusGame() {
    AllowSetForegroundWindow(enginePid);
    activate(playfield());
    if(foregroundPid()!=enginePid)record("focus-pending "+std::to_string(foregroundPid()));
    focusUntil=SDL_GetTicks()+2500;
  }
  void openMenu() {
    if(!ready || stopping)return;
    release();menu=true;intro=false;blocked=true;selected=0;
    SDL_ShowWindow(window);SDL_RaiseWindow(window);activate(ownWindow);
    SDL_ShowCursor();record("menu");
  }
  void resume() {
    release();menu=false;blocked=true;
    focusGame();SDL_HideWindow(window);
    record(warming?"warming":"running");
  }
  void stop(bool restart) {
    if(stopping)return;
    release();restarting=restart;stopping=true;stoppedAt=SDL_GetTicks();
    if(HWND handle=playfield()) {
      // Use VPX's own ExitGame action; WM_CLOSE is not handled consistently by
      // every standalone SDL build. Posted keys bypass our global menu hook.
      PostMessageW(handle,WM_KEYDOWN,VK_ESCAPE,1|(1<<16));
      PostMessageW(handle,WM_KEYUP,VK_ESCAPE,1|(1<<16)|0xc0000000);
    }
    else SDL_KillProcess(child,false);
    record(restart?"restarting":"saving");
  }
  void choose() {if(selected==0)resume();else stop(selected==1);}
  void addPad(SDL_JoystickID id) {
    if(pads.count(id))return;
    Pad pad;
    if(SDL_IsGamepad(id)){pad.gamepad=SDL_OpenGamepad(id);if(pad.gamepad)pad.joystick=SDL_GetGamepadJoystick(pad.gamepad);}
    else pad.joystick=SDL_OpenJoystick(id);
    if(pad.joystick){pads.emplace(id,pad);record(std::string("pad ")+SDL_GetJoystickName(pad.joystick));}
  }
  bool launchEngine() {
    std::error_code error;
    logOffset=std::filesystem::file_size(preferences/"vpinball.log",error);
    if(error)logOffset=0;
    ready=false;menu=false;stopping=false;restarting=false;blocked=true;initializationTime=0;bootTime=0;warming=false;
    auto ini=(preferences/"VPinballX.ini").u8string(), pref=preferences.u8string()+"\\";
    auto binary=engine.u8string(), primary=table.u8string(), work=engine.parent_path().u8string();
    const char* arguments[]={binary.c_str(),"-Ini",ini.c_str(),"-PrefPath",pref.c_str(),"-Play",primary.c_str(),nullptr};
    auto props=SDL_CreateProperties();
    auto environment=SDL_CreateEnvironment(true);
    // Only the child ignores physical pads: the host supplies one consistent mapping,
    // preventing VPX's first-device mapping prompt and duplicate controller actions.
    for(const char* hint:{"SDL_JOYSTICK_HIDAPI","SDL_JOYSTICK_DIRECTINPUT","SDL_JOYSTICK_RAWINPUT","SDL_JOYSTICK_WGI","SDL_XINPUT_ENABLED"})
      SDL_SetEnvironmentVariable(environment,hint,"0",true);
    SDL_SetPointerProperty(props,SDL_PROP_PROCESS_CREATE_ARGS_POINTER,const_cast<char**>(arguments));
    SDL_SetPointerProperty(props,SDL_PROP_PROCESS_CREATE_ENVIRONMENT_POINTER,environment);
    SDL_SetStringProperty(props,SDL_PROP_PROCESS_CREATE_WORKING_DIRECTORY_STRING,work.c_str());
    SDL_SetNumberProperty(props,SDL_PROP_PROCESS_CREATE_STDIN_NUMBER,SDL_PROCESS_STDIO_NULL);
    SDL_SetNumberProperty(props,SDL_PROP_PROCESS_CREATE_STDOUT_NUMBER,SDL_PROCESS_STDIO_INHERITED);
    SDL_SetNumberProperty(props,SDL_PROP_PROCESS_CREATE_STDERR_NUMBER,SDL_PROCESS_STDIO_INHERITED);
    child=SDL_CreateProcessWithProperties(props);
    SDL_DestroyEnvironment(environment);SDL_DestroyProperties(props);
    if(!child){record(std::string("error ")+SDL_GetError());return false;}
    enginePid=static_cast<DWORD>(SDL_GetNumberProperty(SDL_GetProcessProperties(child),SDL_PROP_PROCESS_PID_NUMBER,0));
    if(HANDLE handle=OpenProcess(PROCESS_SET_QUOTA|PROCESS_TERMINATE,FALSE,enginePid)) {
      if(job)AssignProcessToJobObject(job,handle);
      CloseHandle(handle);
    }
    AllowSetForegroundWindow(enginePid);
    std::printf("GAMECLUB_PINBALL_ENGINE %lu\n",static_cast<unsigned long>(enginePid));std::fflush(stdout);
    startedAt=lastTick=SDL_GetTicks();record(initialize?"initializing":"loading");
    return true;
  }
  void readLog() {
    std::ifstream file(preferences/"vpinball.log",std::ios::binary);
    if(!file)return;
    file.seekg(0,std::ios::end);auto size=static_cast<uintmax_t>(file.tellg());
    if(size<logOffset)logOffset=0;
    file.seekg(logOffset);
    std::string fresh{std::istreambuf_iterator<char>(file),{}};logOffset+=fresh.size();
    if(!ready && fresh.find("Startup done")!=std::string::npos) {
      ready=true;focusGame();record("ready");
      if(!initialize && warmupMs){warming=true;record("warming");}
      else if(!initialize && intro)openMenu();
      else if(!initialize)resume();
    }
  }
  void pulse(WORD key) {
    const auto now=SDL_GetTicks();
    if(key==start)pendingStartAt=std::max(now,lastCoinTime+1000);
    else if(key==coin)queuedCoins=std::min(queuedCoins+1,20);
    else pulses[key]=now+150;
  }
  void input() {
    const bool active=foregroundPid()==enginePid, own=GetForegroundWindow()==ownWindow;
    bool up=false,down=false,accept=false,cancel=false,combo=false,neutral=true;
    std::set<WORD> desired;
    for(auto& item:pads) {
      if(testOnlyPad && item.first!=virtualId)continue;
      auto& pad=item.second;
      auto button=[&pad](SDL_GamepadButton id){return pad.button(id);};
      const bool back=button(SDL_GAMEPAD_BUTTON_BACK), begin=button(SDL_GAMEPAD_BUTTON_START);
      combo|=(back&&begin)||button(SDL_GAMEPAD_BUTTON_GUIDE);
      bool any=false;
      for(int i=0;i<SDL_GAMEPAD_BUTTON_COUNT;++i)any|=button(static_cast<SDL_GamepadButton>(i));
      any|=pad.axis(SDL_GAMEPAD_AXIS_LEFT_TRIGGER)>12000 || pad.axis(SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)>12000;
      any|=std::abs(static_cast<int>(pad.axis(SDL_GAMEPAD_AXIS_LEFTX)))>18000 || std::abs(static_cast<int>(pad.axis(SDL_GAMEPAD_AXIS_LEFTY)))>18000;
      neutral&=!any;
      up|=button(SDL_GAMEPAD_BUTTON_DPAD_UP)||pad.axis(SDL_GAMEPAD_AXIS_LEFTY)<-18000;
      down|=button(SDL_GAMEPAD_BUTTON_DPAD_DOWN)||pad.axis(SDL_GAMEPAD_AXIS_LEFTY)>18000;
      accept|=button(SDL_GAMEPAD_BUTTON_SOUTH)||begin;
      cancel|=button(SDL_GAMEPAD_BUTTON_EAST);
      if(ready && !warming && !blocked && !menu && active && !initialize && !stopping) {
        // Start/Select act on release, so their chord never also inserts a coin or starts a game.
        if(pad.back&&!back&&!begin)pulse(coin);
        if(pad.start&&!begin&&!back)pulse(start);
        if(button(SDL_GAMEPAD_BUTTON_NORTH)&&!pad.north)pulse(coin);
        if(button(SDL_GAMEPAD_BUTTON_SOUTH))desired.insert(launch);
        if(button(SDL_GAMEPAD_BUTTON_LEFT_SHOULDER)||pad.axis(SDL_GAMEPAD_AXIS_LEFT_TRIGGER)>12000||button(SDL_GAMEPAD_BUTTON_WEST))desired.insert(leftFlip);
        if(button(SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER)||pad.axis(SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)>12000||button(SDL_GAMEPAD_BUTTON_EAST))desired.insert(rightFlip);
        if(button(SDL_GAMEPAD_BUTTON_DPAD_LEFT)||pad.axis(SDL_GAMEPAD_AXIS_LEFTX)<-18000)desired.insert(nudgeLeft);
        if(button(SDL_GAMEPAD_BUTTON_DPAD_RIGHT)||pad.axis(SDL_GAMEPAD_AXIS_LEFTX)>18000)desired.insert(nudgeRight);
        if(button(SDL_GAMEPAD_BUTTON_DPAD_UP))desired.insert(nudgeCenter);
      }
      pad.back=back;pad.start=begin;pad.north=button(SDL_GAMEPAD_BUTTON_NORTH);
    }
    if(blocked && neutral)blocked=false;
    if(!menu && active && combo && !blocked){openMenu();return;}
    if(menu && own && !blocked && !stopping) {
      if(up&&!prevUp)selected=(selected+2)%3;
      if(down&&!prevDown)selected=(selected+1)%3;
      if(accept&&!prevAccept)choose();else if(cancel&&!prevCancel)resume();
    }
    prevUp=up;prevDown=down;prevAccept=accept;prevCancel=cancel;
    if(!ready || !active || menu || blocked || initialize || warming || stopping){release();return;}
    const auto now=SDL_GetTicks();
    if(queuedCoins && now>=nextCoinAt) {
      pulses[coin]=now+150;--queuedCoins;nextCoinAt=now+1100;
      if(pendingStartAt)pendingStartAt=std::max(pendingStartAt,now+1100);
    }
    if(pendingStartAt && !queuedCoins && now>=pendingStartAt){pulses[start]=now+500;pendingStartAt=0;}
    for(auto it=pulses.begin();it!=pulses.end();) {
      if(it->second<=SDL_GetTicks())it=pulses.erase(it);
      else {desired.insert(it->first);++it;}
    }
    for(WORD scan:held)if(!desired.count(scan)){sendKey(scan,false);record("key-up "+std::to_string(scan));}
    for(WORD scan:desired)if(!held.count(scan)){sendKey(scan,true);if(scan==coin)lastCoinTime=SDL_GetTicks();record("key-down "+std::to_string(scan));}
    held=desired;
  }
  void draw() {
    const auto now=SDL_GetTicks();
    if(now-lastDraw<33)return;
    lastDraw=now;
    if(!menu && ready)return;
    SDL_SetRenderDrawColor(renderer,16,17,28,255);SDL_RenderClear(renderer);
    auto text=[this](float x,float y,const char* value,float scale=2.f) {
      SDL_SetRenderScale(renderer,scale,scale);SDL_SetRenderDrawColor(renderer,245,245,255,255);
      SDL_RenderDebugText(renderer,x/scale,y/scale,value);SDL_SetRenderScale(renderer,1,1);
    };
    text(45,35,menu?"GAMECLUB - MENU PINBALL":"PREPARANDO VISUAL PINBALL",3.f);
    text(45,85,menu?"Juego en pausa. Cruceta: elegir / A: aceptar / B: continuar":"Cargando mesa, ROM y motor. Espera unos segundos.",1.65f);
    const char* labels[]={"Continuar","Reiniciar mesa","Guardar y volver a la biblioteca"};
    if(menu)for(int i=0;i<3;++i) {
      SDL_FRect rect{40.f,130.f+i*70.f,920.f,56.f};
      SDL_SetRenderDrawColor(renderer,i==selected?100:37,i==selected?78:39,i==selected?210:61,255);
      SDL_RenderFillRect(renderer,&rect);text(65,rect.y+18,labels[i]);
    }
    text(45,365,"CONTROLES",2.4f);
    text(45,410,"Mando: Select / Y = moneda    Start = iniciar partida",1.8f);
    text(45,440,"A = lanzar bola    LB/LT = flipper izq.    RB/RT = flipper der.",1.8f);
    text(45,470,"Start + Select / Guide = abrir este menu",1.8f);
    text(45,515,"Teclado: 5 = moneda    1 = partida    Intro = lanzar bola",1.8f);
    text(45,545,"Mayus izq./der. = flippers    Esc / F1 / P = menu",1.8f);
    text(45,585,"Espacio da un golpe a la mesa; NO lanza la bola.",1.8f);
    text(45,625,pads.empty()?"Conecta un mando USB/Bluetooth o usa el teclado.":"Mando conectado. Tambien puedes elegir con raton.",1.65f);
    SDL_RenderPresent(renderer);
  }
  void testInput() {
    if(!virtualId)return;
    DWORD count=0;auto pipe=GetStdHandle(STD_INPUT_HANDLE);
    if(!PeekNamedPipe(pipe,nullptr,0,nullptr,&count,nullptr)||!count)return;
    char bytes[512];DWORD read=0;
    if(!ReadFile(pipe,bytes,std::min<DWORD>(count,sizeof(bytes)),&read,nullptr))return;
    pendingTestInput.append(bytes,read);
    size_t end;
    while((end=pendingTestInput.find('\n'))!=std::string::npos) {
      std::istringstream line(pendingTestInput.substr(0,end));pendingTestInput.erase(0,end+1);
      std::string command;int index=0,value=0;line>>command>>index>>value;
      auto joystick=SDL_GetJoystickFromID(virtualId);
      if(command=="button"&&joystick&&index>=0&&index<SDL_GAMEPAD_BUTTON_COUNT)SDL_SetJoystickVirtualButton(joystick,index,value!=0);
      if(command=="axis"&&joystick&&index>=0&&index<SDL_GAMEPAD_AXIS_COUNT)SDL_SetJoystickVirtualAxis(joystick,index,static_cast<Sint16>(std::clamp(value,-32768,32767)));
      if(command=="disconnect"){SDL_DetachVirtualJoystick(virtualId);virtualId=0;}
    }
  }
  int run(bool testPad) {
    testOnlyPad=testPad;
    diagnostics.open(preferences/"controls.log",std::ios::app);
    SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS,"1");
    if(!SDL_Init(SDL_INIT_VIDEO|SDL_INIT_GAMEPAD)){record(SDL_GetError());return 3;}
    window=SDL_CreateWindow("GameClub - Menu pinball",1000,680,SDL_WINDOW_RESIZABLE);
    renderer=SDL_CreateRenderer(window,nullptr);
    if(!window||!renderer){record(SDL_GetError());SDL_Quit();return 3;}
    SDL_SetRenderLogicalPresentation(renderer,1000,680,SDL_LOGICAL_PRESENTATION_LETTERBOX);
    ownWindow=static_cast<HWND>(SDL_GetPointerProperty(SDL_GetWindowProperties(window),SDL_PROP_WINDOW_WIN32_HWND_POINTER,nullptr));
    activate(ownWindow);draw();
    job=CreateJobObjectW(nullptr,nullptr);
    if(job){JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits));}
    int count=0;auto ids=SDL_GetJoysticks(&count);for(int i=0;i<count;++i)addPad(ids[i]);SDL_free(ids);
    if(testPad) {
      SDL_VirtualJoystickDesc desc{};SDL_INIT_INTERFACE(&desc);desc.type=SDL_JOYSTICK_TYPE_GAMEPAD;
      desc.naxes=SDL_GAMEPAD_AXIS_COUNT;desc.nbuttons=SDL_GAMEPAD_BUTTON_COUNT;
      desc.axis_mask=(1u<<SDL_GAMEPAD_AXIS_COUNT)-1;desc.button_mask=(1u<<SDL_GAMEPAD_BUTTON_COUNT)-1;
      desc.name="GameClub Pinball Integration Pad";virtualId=SDL_AttachVirtualJoystick(&desc);addPad(virtualId);
    }
    HHOOK hook=SetWindowsHookExW(WH_KEYBOARD_LL,keyboardHook,GetModuleHandleW(nullptr),0);
    bool alive=launchEngine();
    while(alive) {
      SDL_Event event;
      while(SDL_PollEvent(&event)) {
        if(event.type==SDL_EVENT_JOYSTICK_ADDED)addPad(event.jdevice.which);
        if(event.type==SDL_EVENT_JOYSTICK_REMOVED) {
          auto it=pads.find(event.jdevice.which);if(it!=pads.end()){it->second.close();pads.erase(it);}release();blocked=true;
        }
        if(event.type==menuEvent)openMenu();
        if(event.type==SDL_EVENT_QUIT) {if(menu)stop(false);else openMenu();}
        if(menu && !stopping && event.type==SDL_EVENT_KEY_DOWN && !event.key.repeat) {
          switch(event.key.key) {
            case SDLK_UP:case SDLK_LEFT:selected=(selected+2)%3;break;
            case SDLK_DOWN:case SDLK_RIGHT:selected=(selected+1)%3;break;
            case SDLK_RETURN:choose();break;case SDLK_ESCAPE:resume();break;default:break;
          }
        }
        if(menu && !stopping && event.type==SDL_EVENT_MOUSE_BUTTON_UP && event.button.button==SDL_BUTTON_LEFT) {
          SDL_ConvertEventToRenderCoordinates(renderer,&event);
          const auto y=event.button.y;
          if(event.button.x>=40&&event.button.x<=960&&y>=130&&y<326) {
            selected=static_cast<int>((y-130)/70);if(y<130+selected*70+56)choose();
          }
        }
      }
      testInput();
      int exitCode=0;
      if(SDL_WaitProcess(child,false,&exitCode)) {
        SDL_DestroyProcess(child);child=nullptr;enginePid=0;
        if(restarting && exitCode==0){
          alive=launchEngine();continue;
        }
        if(result==0)result=exitCode;break;
      }
      readLog();
      const auto now=SDL_GetTicks();
      if(ready && !menu && now<focusUntil && foregroundPid()!=enginePid)activate(playfield());
      if(ready && initialize && !stopping && foregroundPid()==enginePid) {
        initializationTime+=now-lastTick;
        if(initializationTime>=10000){
          // WPC's first NVRAM initialization needs the PinMAME reset key, not
          // repeatedly unloading the table before its trough sensors settle.
          if(HWND handle=playfield()) {
            PostMessageW(handle,WM_KEYDOWN,VK_F3,1|(0x3d<<16));
            PostMessageW(handle,WM_KEYUP,VK_F3,1|(0x3d<<16)|0xc0000000);
          }
          initializationTime=0;
          if(--initializationPasses==0){initialize=false;saveInitializationMarker=true;warming=true;bootTime=0;}
          record("first-boot-next-pass");
        }
      }
      if(ready && warming && !menu && !stopping && foregroundPid()==enginePid) {
        bootTime+=now-lastTick;
        if(bootTime>=warmupMs){
          warming=false;
          if(saveInitializationMarker){
            saveInitializationMarker=false;finishInitializationAfterRestart=true;
            // Reload also reapplies the table's static coin-door/interlock
            // switches, which a PinMAME-only reset clears.
            stop(true);
          } else {
            if(finishInitializationAfterRestart){std::ofstream(preferences/".initialized-afm-v2")<<"complete\n";finishInitializationAfterRestart=false;record("first-boot-complete");}
            if(intro)openMenu();else resume();
          }
        }
      }
      lastTick=now;
      if(!ready && !stopping && now-startedAt>90000){record("error VPX no termino de iniciar");result=5;stop(false);}
      if(stopping && now-stoppedAt>15000){record("error VPX no cerro normalmente");SDL_KillProcess(child,true);result=6;break;}
      input();draw();SDL_Delay(8);
    }
    release();enginePid=0;
    if(hook)UnhookWindowsHookEx(hook);
    if(child){int code=0;SDL_WaitProcess(child,true,&code);SDL_DestroyProcess(child);}
    for(auto& item:pads)item.second.close();
    if(virtualId)SDL_DetachVirtualJoystick(virtualId);
    if(job)CloseHandle(job);
    SDL_DestroyRenderer(renderer);SDL_DestroyWindow(window);SDL_Quit();
    record("closed");return alive?result:4;
  }
};
}

int runPinballHost(int argc, char** argv) {
  if(argc<5)return 2;
  Host host;host.engine=std::filesystem::u8path(argv[2]);host.table=std::filesystem::u8path(argv[3]);host.preferences=std::filesystem::u8path(argv[4]);
  if(!std::filesystem::is_regular_file(host.engine)||!std::filesystem::is_regular_file(host.table))return 2;
  std::filesystem::create_directories(host.preferences);
  bool testPad=false;
  for(int i=5;i<argc;++i){std::string arg=argv[i];if(arg=="--initialize")host.initialize=true;if(arg=="--test-pad")testPad=true;
    if(arg.rfind("--warmup=",0)==0)host.warmupMs=std::clamp(std::atoi(arg.c_str()+9),0,30000);}
  return host.run(testPad);
}
}
