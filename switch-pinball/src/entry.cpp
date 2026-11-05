// Native Horizon/libnx entry point. VPX supplies its own SDL main loop.
#include <switch.h>
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <cstdio>
#include <filesystem>
#include <vector>
#include <string>
#include <pinmame/libpinmame.h>
#include <unistd.h>

extern int g_argc;
extern const char **g_argv;
extern "C" int WinMain(void *, void *, char *, int);
void GameClubSetupInput();
static std::filesystem::path gameclubState;

namespace PinMAME {
void GameClubPinMAMEApplyPaths() {
    for (const auto &item : {std::pair{PINMAME_FILE_TYPE_NVRAM, "nvram"},
                             std::pair{PINMAME_FILE_TYPE_CONFIG, "cfg"},
                             std::pair{PINMAME_FILE_TYPE_HIGHSCORE, "hi"}})
        PinmameSetPath(item.first, (gameclubState / item.second).string().c_str());
}
}

int main(int argc, char **argv) {
    romfsInit();
    socketInitializeDefault();
    SDL_SetMainReady();
    if (chdir("sdmc:/") != 0)
        return 1;
    {
        FILE *boot = std::fopen("/switch/gameclub/pinball-start.log", "w");
        if (boot) {
            std::fprintf(boot, "GameClub: entrada del motor nativo, argc=%d\n", argc);
            std::fclose(boot);
        }
    }
    std::vector<std::string> normalized;
    for (int i = 0; i < argc; ++i) {
        std::string value = argv[i];
        if (value.rfind("sdmc:/", 0) == 0) value.erase(0, 5);
        normalized.push_back(std::move(value));
    }
    std::vector<const char *> arguments;
    std::filesystem::path state = "/switch/gameclub/pinball/preferences";
    for (int i = 0; i < argc; ++i) {
        if (normalized[i] == "--gameclub-state" && i + 1 < argc)
            state = normalized[++i];
        else
            arguments.push_back(normalized[i].c_str());
    }
    std::error_code error;
    std::filesystem::create_directories(state, error);
    if (error)
        return 1;
    gameclubState = state;
    const auto log = (state / "switch-player.log").string();
    std::freopen(log.c_str(), "w", stdout);
    std::freopen(log.c_str(), "a", stderr);
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    std::setvbuf(stderr, nullptr, _IONBF, 0);
    std::puts("GameClub: VPX/PinMAME nativo para Horizon/libnx");
    for (const auto &item : {std::pair{PINMAME_FILE_TYPE_NVRAM, "nvram"},
                             std::pair{PINMAME_FILE_TYPE_CONFIG, "cfg"},
                             std::pair{PINMAME_FILE_TYPE_HIGHSCORE, "hi"}}) {
        auto path = state / item.second;
        std::filesystem::create_directories(path, error);
        if (error)
            return 1;
        PinmameSetPath(item.first, path.string().c_str());
    }
    g_argc = static_cast<int>(arguments.size());
    arguments.push_back(nullptr);
    g_argv = arguments.data();
    for (int i = 0; i < g_argc; ++i)
        std::printf("argv[%d]: %s\n", i, g_argv[i]);
    if (!SDL_Init(SDL_INIT_EVENTS)) {
        std::printf("GameClub: fallo al iniciar SDL: %s\n", SDL_GetError());
        return 1;
    }
    GameClubSetupInput();
    std::puts("GameClub: entrando en Visual Pinball");
    int status = WinMain(nullptr, nullptr, nullptr, 0);
    std::printf("GameClub: salida del motor, código %d\n", status);
    fsdevCommitDevice("sdmc");
    socketExit();
    romfsExit();
    return status;
}
