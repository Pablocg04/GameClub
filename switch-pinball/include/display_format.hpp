#pragma once
#include <SDL3/SDL_pixels.h>
#include <optional>

namespace gameclub {
// The display's channel ordering does not restrict desktop GL capabilities.
// libnx reports RGBA8888, including when using the desktop OpenGL backend.
template<class Color> constexpr std::optional<Color> displayFormat(SDL_PixelFormat format) {
    switch (format) {
    case SDL_PIXELFORMAT_RGB565:
    case SDL_PIXELFORMAT_BGR565: return Color::RGB5;
    case SDL_PIXELFORMAT_XRGB8888:
    case SDL_PIXELFORMAT_XBGR8888:
    case SDL_PIXELFORMAT_RGBX8888:
    case SDL_PIXELFORMAT_BGRX8888: return Color::RGB8;
    case SDL_PIXELFORMAT_ARGB8888:
    case SDL_PIXELFORMAT_RGBA8888:
    case SDL_PIXELFORMAT_ABGR8888:
    case SDL_PIXELFORMAT_BGRA8888: return Color::RGBA8;
    case SDL_PIXELFORMAT_ARGB2101010:
    case SDL_PIXELFORMAT_ABGR2101010: return Color::RGBA10;
    default: return std::nullopt;
    }
}
}
