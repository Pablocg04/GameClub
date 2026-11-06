#include <SDL3/SDL.h>
#include "input_bindings.hpp"
#include <cstdio>
#include <array>
#include <map>
#include <mutex>

namespace {
constexpr auto &keys = gameclub::buttonKeys;
std::map<SDL_JoystickID, uint32_t> pads;
std::array<bool, SDL_SCANCODE_COUNT> previous{};
std::mutex mutex;

bool SDLCALL filter(void *, SDL_Event *event) {
    const bool button = event->type == SDL_EVENT_JOYSTICK_BUTTON_DOWN || event->type == SDL_EVENT_JOYSTICK_BUTTON_UP;
    const bool removed = event->type == SDL_EVENT_JOYSTICK_REMOVED;
    if (!button && !removed)
        return true;
    if (button && event->jbutton.button >= keys.size())
        return false;
    std::array<bool, SDL_SCANCODE_COUNT> held{};
    std::array<bool, SDL_SCANCODE_COUNT> changed{};
    {
        std::lock_guard lock(mutex);
        if (removed)
            pads.erase(event->jdevice.which);
        else {
            auto &state = pads[event->jbutton.which];
            const uint32_t bit = uint32_t(1) << event->jbutton.button;
            if (event->jbutton.down) state |= bit; else state &= ~bit;
        }
        for (const auto &[_, state] : pads)
            for (size_t i = 0; i < keys.size(); ++i)
                if (state & (uint32_t(1) << i)) held[keys[i].scan] = true;
        for (size_t i = 0; i < held.size(); ++i) changed[i] = held[i] != previous[i];
        previous = held;
    }
    for (const auto &key : keys) {
        if (!changed[key.scan]) continue;
        changed[key.scan] = false;
        SDL_Event generated{};
        generated.type = held[key.scan] ? SDL_EVENT_KEY_DOWN : SDL_EVENT_KEY_UP;
        generated.key.timestamp = SDL_GetTicksNS();
        generated.key.windowID = SDL_GetKeyboardFocus() ? SDL_GetWindowID(SDL_GetKeyboardFocus()) : 0;
        generated.key.scancode = key.scan;
        generated.key.key = key.code;
        generated.key.down = held[key.scan];
        if (held[key.scan] && (key.scan == SDL_SCANCODE_1 || key.scan == SDL_SCANCODE_5 || key.scan == SDL_SCANCODE_F12))
            std::printf("GameClub: control %s\n", key.scan == SDL_SCANCODE_1 ? "START" : key.scan == SDL_SCANCODE_5 ? "COIN" : "MENU");
        SDL_PushEvent(&generated);
    }
    return removed;
}
}
void GameClubSetupInput() { SDL_SetEventFilter(filter, nullptr); }
