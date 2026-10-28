// GameClub adapter to the unmodified, pinned VPinballLib C API (GPLv3+).
#include <SDL3/SDL.h>
#include <jni.h>
#include <dlfcn.h>
#include <android/log.h>
#include <string>
#include <stdexcept>
#include <algorithm>

namespace {
JavaVM* vm=nullptr;
jobject listener=nullptr;
jmethodID eventMethod=nullptr;
void* engine=nullptr;
template<typename T>T symbol(const char* name);
struct Presentation { int mechanical, electronic, scale; bool score; std::string error; };
void configurePresentation(void* data) {
  auto& settings=*static_cast<Presentation*>(data);
  try {
    auto saveInt=symbol<void(*)(const char*,const char*,int)>("VPinballSaveValueInt");
    auto saveFloat=symbol<void(*)(const char*,const char*,float)>("VPinballSaveValueFloat");
    // PinMAME publishes a BACKGLASS stream; playfield is the mechanical channel.
    saveInt("Player","SoundVolume",settings.mechanical);
    saveInt("Player","MusicVolume",settings.electronic);
    // Cabinet visibility avoids the desktop DMD drawn by many table scripts.
    // Legacy mode fits the geometry to the actual viewport, unlike imported POVs.
    saveInt("Player","BGSet",1);
    saveInt("Player","CabinetAutofitMode",0);
    saveInt("Player","NumberOfTimesToShowTouchMessage",0);
    saveInt("TableOverride","ViewCabMode",0);
    for(const char* key:{"ViewCabPlayerX","ViewCabPlayerY","ViewCabPlayerZ","ViewCabRotation","ViewCabLayback"})
      saveFloat("TableOverride",key,0.f);
    saveFloat("TableOverride","ViewCabLookAt",20.f);
    saveFloat("TableOverride","ViewCabFOV",50.f);
    for(const char* key:{"ViewCabScaleX","ViewCabScaleY","ViewCabScaleZ"})
      saveFloat("TableOverride",key,settings.scale/100.f);
    saveInt("ScoreView","ScoreViewOutput",settings.score?2:0);
  } catch(const std::exception& error) { settings.error=error.what(); }
}
using EventCallback=void(*)(int,const char*);
template<typename T>T symbol(const char* name) {
  auto result=reinterpret_cast<T>(dlsym(engine,name));
  if(!result)throw std::runtime_error(std::string("Falta la API VPX: ")+name);
  return result;
}
void failure(JNIEnv* env,const char* text) {
  __android_log_print(ANDROID_LOG_ERROR,"GameClubPinball","%s",text);
  auto type=env->FindClass("java/lang/IllegalStateException");
  if(type){env->ThrowNew(type,text);env->DeleteLocalRef(type);}
}
void event(int value,const char* json) {
  if(!vm||!listener||!eventMethod)return;
  JNIEnv* env=nullptr;
  const bool attach=vm->GetEnv(reinterpret_cast<void**>(&env),JNI_VERSION_1_6)!=JNI_OK;
  if(attach&&vm->AttachCurrentThread(&env,nullptr)!=JNI_OK)return;
  auto payload=json?env->NewStringUTF(json):nullptr;
  env->CallVoidMethod(listener,eventMethod,value,payload);
  if(payload)env->DeleteLocalRef(payload);
  if(env->ExceptionCheck()){env->ExceptionDescribe();env->ExceptionClear();}
  if(attach)vm->DetachCurrentThread();
}
std::string text(JNIEnv* env,jstring value) {
  if(!value)return {};
  auto chars=env->GetStringUTFChars(value,nullptr);
  if(!chars)throw std::runtime_error("No se pudo leer una ruta de la mesa");
  std::string result(chars);env->ReleaseStringUTFChars(value,chars);return result;
}
void configureInput(void*) {
  try {
    auto saveString=symbol<void(*)(const char*,const char*,const char*)>("VPinballSaveValueString");
    auto saveBool=symbol<void(*)(const char*,const char*,int)>("VPinballSaveValueBool");
    // Android delivers our touch/pad controls as ordinary SDL keyboard keys.
    const std::pair<const char*,const char*> mappings[]={
      {"LeftFlipper","Key;225"},{"RightFlipper","Key;229"},
      {"LeftStagedFlipper","Key;225"},{"RightStagedFlipper","Key;229"},
      {"Start","Key;30"},{"Credit1","Key;34"},{"LaunchBall","Key;40"},
      {"LeftNudge","Key;29"},{"RightNudge","Key;56"},{"CenterNudge","Key;44"}
    };
    for(const auto& mapping:mappings)saveString("Input",(std::string("Mapping.")+mapping.first).c_str(),mapping.second);
    SDL_InitSubSystem(SDL_INIT_GAMEPAD);
    int count=0;auto ids=SDL_GetJoysticks(&count);
    for(int i=0;i<count;++i) {
      auto guid=SDL_GetJoystickGUIDForID(ids[i]);char name[33]{};SDL_GUIDToString(guid,name,sizeof(name));
      int index=1;
      for(int j=0;j<i;++j){auto other=SDL_GetJoystickGUIDForID(ids[j]);if(SDL_memcmp(&guid,&other,sizeof(guid))==0)++index;}
      saveBool("Input",(std::string("Device.SDLJoy_")+name+"_"+std::to_string(index)+".NoAutoLayout").c_str(),1);
    }
    SDL_free(ids);
  } catch(const std::exception& error){__android_log_print(ANDROID_LOG_ERROR,"GameClubPinball","%s",error.what());}
}
}

extern "C" JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* current,void*) {vm=current;return JNI_VERSION_1_6;}

extern "C" JNIEXPORT jboolean JNICALL Java_com_gameclub_gameclub_PinballActivity_nativeReady(JNIEnv*,jobject) {
  return (SDL_WasInit(SDL_INIT_VIDEO)&SDL_INIT_VIDEO)!=0;
}
extern "C" JNIEXPORT void JNICALL Java_com_gameclub_gameclub_PinballActivity_nativeInitialize(JNIEnv* env,jobject activity) {
  try {
    engine=dlopen("libvpinball.so",RTLD_NOW|RTLD_LOCAL);
    if(!engine)throw std::runtime_error(dlerror());
    if(listener)throw std::runtime_error("VPX ya se ha inicializado");
    listener=env->NewGlobalRef(activity);
    auto type=env->GetObjectClass(activity);
    eventMethod=env->GetMethodID(type,"onNativeEvent","(ILjava/lang/String;)V");env->DeleteLocalRef(type);
    if(!eventMethod)throw std::runtime_error("Falta el receptor de eventos VPX");
    symbol<void(*)(EventCallback)>("VPinballInit")(event);
  } catch(const std::exception& error){failure(env,error.what());}
}
extern "C" JNIEXPORT jint JNICALL Java_com_gameclub_gameclub_PinballActivity_nativeLoad(JNIEnv* env,jobject,jstring path,jint mechanical,jint electronic,jint scale,jboolean score) {
  try {
    if(!engine)throw std::runtime_error("VPX no esta inicializado");
    SDL_RunOnMainThread(configureInput,nullptr,true);
    Presentation settings{std::clamp(int(mechanical),0,100),std::clamp(int(electronic),0,100),std::clamp(int(scale),70,100),bool(score)};
    if(!SDL_RunOnMainThread(configurePresentation,&settings,true))throw std::runtime_error("No se pudieron aplicar los ajustes VPX");
    if(!settings.error.empty())throw std::runtime_error(settings.error);
    return symbol<int(*)(const char*)>("VPinballLoadTable")(text(env,path).c_str());
  } catch(const std::exception& error){failure(env,error.what());return 1;}
}
extern "C" JNIEXPORT jint JNICALL Java_com_gameclub_gameclub_PinballActivity_nativePlay(JNIEnv* env,jobject) {
  try{return symbol<int(*)()>("VPinballPlay")();}
  catch(const std::exception& error){failure(env,error.what());return 1;}
}
extern "C" JNIEXPORT void JNICALL Java_com_gameclub_gameclub_PinballActivity_nativeStop(JNIEnv* env,jobject) {
  try{if(engine)symbol<int(*)()>("VPinballStop")();}
  catch(const std::exception& error){failure(env,error.what());}
}
extern "C" JNIEXPORT jstring JNICALL Java_com_gameclub_gameclub_PinballActivity_nativeVersion(JNIEnv* env,jobject) {
  try{return env->NewStringUTF(symbol<const char*(*)()>("VPinballGetVersionStringFull")());}
  catch(const std::exception& error){failure(env,error.what());return nullptr;}
}
