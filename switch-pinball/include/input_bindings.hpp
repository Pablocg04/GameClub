#pragma once
#include <SDL3/SDL.h>
#include <array>

namespace gameclub {
struct NativeKey { SDL_Scancode scan; SDL_Keycode code; };
// devkitPro SDL raw libnx pad ordering. F12 opens VPX's menu; Escape exits the table.
inline constexpr std::array<NativeKey, 16> buttonKeys{{
    {SDL_SCANCODE_RETURN, SDLK_RETURN}, {SDL_SCANCODE_F12, SDLK_F12},
    {SDL_SCANCODE_5, SDLK_5}, {SDL_SCANCODE_1, SDLK_1},
    {SDL_SCANCODE_7, SDLK_7}, {SDL_SCANCODE_8, SDLK_8},
    {SDL_SCANCODE_LSHIFT, SDLK_LSHIFT}, {SDL_SCANCODE_RSHIFT, SDLK_RSHIFT},
    {SDL_SCANCODE_LSHIFT, SDLK_LSHIFT}, {SDL_SCANCODE_RSHIFT, SDLK_RSHIFT},
    {SDL_SCANCODE_1, SDLK_1}, {SDL_SCANCODE_5, SDLK_5},
    {SDL_SCANCODE_LEFT, SDLK_LEFT}, {SDL_SCANCODE_UP, SDLK_UP},
    {SDL_SCANCODE_RIGHT, SDLK_RIGHT}, {SDL_SCANCODE_DOWN, SDLK_DOWN}
}};
}
