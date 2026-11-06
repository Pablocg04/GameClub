#pragma once
#include "pause_menu.hpp"
#include "imgui/imgui.h"
#include <cstdio>

namespace gameclub {
inline void drawPauseMenu(const PauseMenu &menu, float fps) {
    auto *draw = ImGui::GetForegroundDrawList();
    const auto size = ImGui::GetIO().DisplaySize;
    const float scale = size.y / 720.f;
    const auto point = [=](float x, float y) { return ImVec2(x * scale, y * scale); };
    const auto text = [&](float x, float y, float height, ImU32 color, const char *label) {
        draw->AddText(nullptr, height * scale, point(x, y), color, label);
    };
    char status[80];
    std::snprintf(status, sizeof(status), "B: MENU   %.0f FPS", fps);
    draw->AddRectFilled(point(10, 10), point(267, 48), IM_COL32(0, 0, 0, 230));
    text(20, 16, 22, IM_COL32(240, 220, 255, 255), status);
    if (!menu.isOpen()) return;
    draw->AddRectFilled(ImVec2(0, 0), size, IM_COL32(0, 0, 0, 180));
    const float x = (size.x / scale - 560) * .5f;
    draw->AddRectFilled(point(x-8, 182), point(x+568, 538), IM_COL32(0, 0, 0, 255));
    draw->AddRectFilled(point(x, 190), point(x+560, 530), IM_COL32(68, 27, 111, 255));
    text(x+32, 217, 32, IM_COL32(255, 219, 99, 255), "GAMECLUB / PAUSA");
    const char *items[] = {"Continuar", "Salir"};
    for (int i = 0; i < 2; ++i) {
        const float y = 284.f + i * 84.f;
        const bool selected = menu.selection() == i;
        draw->AddRectFilled(point(x+24, y), point(x+536, y+68), IM_COL32(0, 0, 0, 255));
        draw->AddRectFilled(point(x+30, y+6), point(x+530, y+62), selected ? IM_COL32(178, 95, 246, 255) : IM_COL32(40, 17, 65, 255));
        text(x+48, y+16, 28, IM_COL32(255, 255, 255, 255), items[i]);
    }
    text(x+32, 474, 22, IM_COL32(235, 221, 255, 255), "Cruceta: elegir   A: aceptar   B: volver");
}

}
