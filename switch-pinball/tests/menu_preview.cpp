// Render the same ImGui draw commands as the console, using SDL's host renderer.
#include <SDL.h>
#include <SDL_image.h>
#include <memory>
class Sampler {
public:
    SDL_Texture *texture;
    explicit Sampler(SDL_Texture *value) : texture(value) {}
};
#include "menu_draw.hpp"
#include "fonts/DroidSans.h"
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <vector>
#include <string>

int main(int argc, char **argv) {
    try {
        if (argc != 2) throw std::runtime_error("Expected output folder");
        const std::filesystem::path folder = argv[1];
        std::filesystem::create_directories(folder);
        SDL_SetMainReady();
        if (SDL_Init(SDL_INIT_VIDEO)) throw std::runtime_error(SDL_GetError());
        auto *window = SDL_CreateWindow("GameClub menu check", 0, 0, 1280, 720, SDL_WINDOW_HIDDEN);
        auto *renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
        if (!renderer) throw std::runtime_error(SDL_GetError());
        ImGui::CreateContext();
        auto &io = ImGui::GetIO();
        io.IniFilename = nullptr;
        io.DisplaySize = ImVec2(1280, 720);
        io.DeltaTime = 1.f / 60;
        io.BackendFlags |= ImGuiBackendFlags_RendererHasTextures;
        io.Fonts->AddFontFromMemoryCompressedTTF(droidsans_compressed_data, droidsans_compressed_size, 22.f);
        std::vector<SDL_Texture *> textures;
        gameclub::PauseMenu menu;
        using K = gameclub::MenuKey;
        for (int state = 0; state < 3; ++state) {
            if (state == 1) menu.key(K::Toggle, true, false, true);
            if (state == 2) menu.key(K::Down, true, false, false);
            ImGui::NewFrame();
            gameclub::drawPauseMenu(menu, 42.f);
            ImGui::Render();
            auto *data = ImGui::GetDrawData();
            for (auto *tex : *data->Textures) {
                if (tex->Status != ImTextureStatus_WantCreate && tex->Status != ImTextureStatus_WantUpdates) continue;
                SDL_Texture *texture;
                if (tex->Status == ImTextureStatus_WantCreate) {
                    texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888, SDL_TEXTUREACCESS_STATIC, tex->Width, tex->Height);
                    if (!texture) throw std::runtime_error(SDL_GetError());
                    SDL_SetTextureBlendMode(texture, SDL_BLENDMODE_BLEND);
                    textures.push_back(texture);
                    tex->SetTexID(std::make_shared<Sampler>(texture));
                } else texture = tex->TexID->texture;
                if (tex->Format != ImTextureFormat_RGBA32) throw std::runtime_error("Unexpected font format");
                SDL_UpdateTexture(texture, nullptr, tex->GetPixels(), tex->GetPitch());
                tex->SetStatus(ImTextureStatus_OK);
            }
            SDL_SetRenderDrawColor(renderer, 25, 41, 47, 255); SDL_RenderClear(renderer);
            for (auto *list : data->CmdLists) for (const auto &cmd : list->CmdBuffer) {
                if (cmd.UserCallback) throw std::runtime_error("Unexpected draw callback");
                SDL_Rect clip{int(cmd.ClipRect.x), int(cmd.ClipRect.y), int(cmd.ClipRect.z-cmd.ClipRect.x), int(cmd.ClipRect.w-cmd.ClipRect.y)};
                SDL_RenderSetClipRect(renderer, &clip);
                const auto *v = list->VtxBuffer.Data + cmd.VtxOffset;
                const auto *idx = list->IdxBuffer.Data + cmd.IdxOffset;
                if (SDL_RenderGeometryRaw(renderer, cmd.GetTexID() ? cmd.GetTexID()->texture : nullptr,
                    &v->pos.x, sizeof(ImDrawVert), reinterpret_cast<const SDL_Color *>(&v->col), sizeof(ImDrawVert),
                    &v->uv.x, sizeof(ImDrawVert), list->VtxBuffer.Size-int(cmd.VtxOffset), idx, int(cmd.ElemCount), sizeof(ImDrawIdx)))
                    throw std::runtime_error(SDL_GetError());
            }
            auto *surface = SDL_CreateRGBSurfaceWithFormat(0, 1280, 720, 32, SDL_PIXELFORMAT_ABGR8888);
            SDL_RenderSetClipRect(renderer, nullptr);
            if (SDL_RenderReadPixels(renderer, nullptr, surface->format->format, surface->pixels, surface->pitch))
                throw std::runtime_error(SDL_GetError());
            const auto path = folder / (std::string("pinball-menu-")+std::to_string(state)+".png");
            if (IMG_SavePNG(surface, path.string().c_str())) throw std::runtime_error(IMG_GetError());
            SDL_FreeSurface(surface);
        }
        for (auto *tex : io.Fonts->TexList) { tex->SetTexID(ImTextureID_Invalid); tex->SetStatus(ImTextureStatus_Destroyed); }
        ImGui::DestroyContext();
        for (auto *texture : textures) SDL_DestroyTexture(texture);
        SDL_DestroyRenderer(renderer); SDL_DestroyWindow(window); SDL_Quit();
        std::cout << "Tres vistas del menu nativo comprobadas.\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
