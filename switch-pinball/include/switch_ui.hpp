#pragma once
#include <SDL3/SDL.h>
class Player;
bool GameClubHandleMenuEvent(Player *, const SDL_Event &);
void GameClubRenderUI(Player *);
