#include <SDL3/SDL.h>
#include <array>
#include <map>
#include <mutex>

namespace {
struct Key { SDL_Scancode scan; SDL_Keycode code; };
// Raw libnx pad ordering is defined by devkitPro's SDL Switch driver.
constexpr std::array<Key, 16> keys{{
    {SDL_SCANCODE_RETURN, SDLK_RETURN}, {SDL_SCANCODE_ESCAPE, SDLK_ESCAPE},
    {SDL_SCANCODE_5, SDLK_5}, {SDL_SCANCODE_1, SDLK_1},
    {SDL_SCANCODE_7, SDLK_7}, {SDL_SCANCODE_8, SDLK_8},
    {SDL_SCANCODE_LSHIFT, SDLK_LSHIFT}, {SDL_SCANCODE_RSHIFT, SDLK_RSHIFT},
    {SDL_SCANCODE_LSHIFT, SDLK_LSHIFT}, {SDL_SCANCODE_RSHIFT, SDLK_RSHIFT},
    {SDL_SCANCODE_ESCAPE, SDLK_ESCAPE}, {SDL_SCANCODE_5, SDLK_5},
    {SDL_SCANCODE_LEFT, SDLK_LEFT}, {SDL_SCANCODE_UP, SDLK_UP},
    {SDL_SCANCODE_RIGHT, SDLK_RIGHT}, {SDL_SCANCODE_DOWN, SDLK_DOWN}
}};
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
        SDL_PushEvent(&generated);
    }
    return removed;
}
}
void GameClubSetupInput() { SDL_SetEventFilter(filter, nullptr); }
