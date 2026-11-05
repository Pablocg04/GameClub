#include "display_format.hpp"
#include <iostream>
#include <stdexcept>
enum class Color { RGB5, RGB8, RGBA8, RGBA10 };
int main() {
    int checks = 0;
    auto check = [&](bool ok) { if (!ok) throw std::runtime_error("Display format regression"); ++checks; };
    try {
        using gameclub::displayFormat;
        check(displayFormat<Color>(static_cast<SDL_PixelFormat>(373694468)) == Color::RGBA8);
        check(displayFormat<Color>(SDL_PIXELFORMAT_BGRA8888) == Color::RGBA8);
        check(displayFormat<Color>(SDL_PIXELFORMAT_ABGR8888) == Color::RGBA8);
        check(displayFormat<Color>(SDL_PIXELFORMAT_ARGB8888) == Color::RGBA8);
        check(displayFormat<Color>(SDL_PIXELFORMAT_RGBX8888) == Color::RGB8);
        check(displayFormat<Color>(SDL_PIXELFORMAT_XRGB8888) == Color::RGB8);
        check(displayFormat<Color>(SDL_PIXELFORMAT_ARGB2101010) == Color::RGBA10);
        check(displayFormat<Color>(SDL_PIXELFORMAT_RGB565) == Color::RGB5);
        check(!displayFormat<Color>(SDL_PIXELFORMAT_NV12));
        std::cout << checks << " comprobaciones de formato Switch superadas.\n";
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
