#pragma once

namespace gameclub {
enum class MenuKey { Toggle, Up, Down, Confirm, Other };
enum class MenuAction { None, Pause, Resume, Exit };
// Main-thread state. Key releases still reach VPX, avoiding stuck flippers.
class PauseMenu {
    bool opened = false, wasPlaying = false;
    int selected = 0;
public:
    bool isOpen() const { return opened; }
    int selection() const { return selected; }
    MenuAction key(MenuKey key, bool down, bool repeat, bool playing) {
        if (!down || repeat) return MenuAction::None;
        if (key == MenuKey::Toggle) {
            if (opened) { opened = false; return wasPlaying ? MenuAction::Resume : MenuAction::None; }
            opened = true; selected = 0; wasPlaying = playing;
            return playing ? MenuAction::Pause : MenuAction::None;
        }
        if (!opened) return MenuAction::None;
        if (key == MenuKey::Up || key == MenuKey::Down) selected = 1 - selected;
        if (key == MenuKey::Confirm) {
            opened = false;
            return selected == 1 ? MenuAction::Exit : (wasPlaying ? MenuAction::Resume : MenuAction::None);
        }
        return MenuAction::None;
    }
};
}
