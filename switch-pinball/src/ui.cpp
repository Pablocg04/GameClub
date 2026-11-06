#include "core/stdafx.h"
#include "switch_ui.hpp"
#include "pause_menu.hpp"
#include "menu_draw.hpp"

namespace {
gameclub::PauseMenu menu;
}

bool GameClubHandleMenuEvent(Player *player, const SDL_Event &event) {
    if (event.type != SDL_EVENT_KEY_DOWN && event.type != SDL_EVENT_KEY_UP) return false;
    const auto scan = event.key.scancode;
    auto key = scan == SDL_SCANCODE_F12 ? gameclub::MenuKey::Toggle :
               scan == SDL_SCANCODE_UP ? gameclub::MenuKey::Up :
               scan == SDL_SCANCODE_DOWN ? gameclub::MenuKey::Down :
               scan == SDL_SCANCODE_RETURN ? gameclub::MenuKey::Confirm : gameclub::MenuKey::Other;
    const bool consumed = scan == SDL_SCANCODE_F12 || (menu.isOpen() && event.key.down);
    const auto action = menu.key(key, event.key.down, event.key.repeat, player->IsPlaying());
    switch (action) {
    case gameclub::MenuAction::Pause: player->SetPlayState(false); break;
    case gameclub::MenuAction::Resume: player->SetPlayState(true); break;
    case gameclub::MenuAction::Exit:
        PLOGI << "GameClub: Salir -> volver a la biblioteca";
        player->SetCloseState(Player::CS_CLOSE_APP);
        break;
    default: break;
    }
    return consumed;
}

void GameClubRenderUI(Player *player) { gameclub::drawPauseMenu(menu, player->m_fps); }
