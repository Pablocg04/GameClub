"""Sistemas disponibles en la biblioteca; cada uno usa su propia carpeta."""

def system(id, name, extensions, metadata_id, emulator):
    return dict(id=id, name=name, extensions=extensions.split(),
                metadata_id=metadata_id, emulator=emulator)


SYSTEMS = [
    system("atari2600", "Atari 2600", ".a26 .bin .rom .zip", 26, "Stella · nativo en GameClub"),
    system("gb", "Game Boy", ".gb .zip .7z", 9, "RetroArch"),
    system("gba", "Game Boy Advance", ".gba .zip .7z", 12, "mGBA / RetroArch"),
    system("gbc", "Game Boy Color", ".gbc .gb .zip .7z", 10, "RetroArch"),
    system("gc", "GameCube", ".iso .gcm .rvz .ciso .gcz", 13, "Dolphin"),
    system("mame", "Arcade · MAME", ".zip .7z .chd", 75, "MAME / RetroArch"),
    system("n3ds", "Nintendo 3DS", ".3ds .cci .cxi .cia", 17, "Azahar"),
    system("n64", "Nintendo 64", ".z64 .n64 .v64 .zip .7z", 14, "Mupen64Plus / RetroArch"),
    system("nes", "Nintendo Entertainment System · NES", ".nes .unf .unif .zip", 3, "Nestopia UE · nativo en GameClub"),
    system("nds", "Nintendo DS", ".nds .dsi .zip .7z", 15, "melonDS"),
    system("ps2", "PlayStation 2", ".iso .chd .cso .bin .gz .m3u", 58, "PCSX2 / NetherSX2"),
    system("psp", "PSP", ".iso .cso .chd .pbp", 61, "PPSSPP"),
    system("psvita", "PlayStation Vita", ".vpk .zip", 62, "Vita3K"),
    system("psx", "PlayStation", ".cue .bin .chd .pbp .iso .m3u", 57, "DuckStation"),
    system("vpinball", "Visual Pinball · PinMAME", ".zip .vpxz .vpx", 10001, "Visual Pinball X + PinMAME"),
    system("snes", "Super Nintendo", ".sfc .smc .zip .7z", 4, "Snes9x / RetroArch"),
    system("switch", "Nintendo Switch", ".nsp .xci .nsz .xcz", 225, "Emulador compatible con tu dispositivo"),
    system("wii", "Nintendo Wii", ".iso .wbfs .rvz .gcz .ciso", 16, "Dolphin"),
    system("wiiu", "Nintendo Wii U", ".wud .wux .wua .rpx", 18, "Cemu"),
]
