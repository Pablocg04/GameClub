// Link PinMAME directly: Horizon homebrew cannot load a desktop shared object.
#include "plugins/MsgPluginManager.h"

extern "C" void PinMAMEPluginLoad(uint32_t, const MsgPluginAPI *);
extern "C" void PinMAMEPluginUnload();
extern "C" void B2SPluginLoad(uint32_t, const MsgPluginAPI *);
extern "C" void B2SPluginUnload();
extern "C" void FlexDMDPluginLoad(uint32_t, const MsgPluginAPI *);
extern "C" void FlexDMDPluginUnload();
extern "C" void ScoreViewPluginLoad(uint32_t, const MsgPluginAPI *);
extern "C" void ScoreViewPluginUnload();

void GameClubSetupPinMAME(MsgPI::MsgPluginManager &manager) {
    manager.RegisterPlugin("PinMAME", "PinMAME", "PinMAME", "", "", "",
                           &PinMAMEPluginLoad, &PinMAMEPluginUnload);
    manager.RegisterPlugin("B2S", "B2S", "B2S", "", "", "", &B2SPluginLoad, &B2SPluginUnload);
    manager.RegisterPlugin("FlexDMD", "FlexDMD", "FlexDMD", "", "", "", &FlexDMDPluginLoad, &FlexDMDPluginUnload);
    manager.RegisterPlugin("ScoreView", "ScoreView", "ScoreView", "", "", "", &ScoreViewPluginLoad, &ScoreViewPluginUnload);
}
