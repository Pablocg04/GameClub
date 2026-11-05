#pragma once
#include "json.hpp"
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace gc {
namespace fs = std::filesystem;
using Json = nlohmann::json;
struct Game {
    std::string id, title, system, filename, revision, cover;
    uint64_t size = 0;
    bool favorite = false;
};
struct Config {
    std::string server = "http://192.168.0.47:8001", token;
    std::string cores = "sdmc:/retroarch/cores";
};
inline std::string lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return char(std::tolower(c)); });
    for (size_t i = 0; i + 1 < s.size(); ++i) {
        if (static_cast<unsigned char>(s[i]) == 0xC3) {
            auto c = static_cast<unsigned char>(s[i + 1]);
            if (c >= 0x80 && c <= 0x9E && c != 0x97)
                s[i + 1] = char(c + 0x20);
        }
    }
    return s;
}
inline bool safeId(const std::string &s) {
    return !s.empty() && s.size() <= 64 &&
           std::all_of(s.begin(), s.end(), [](unsigned char c) { return std::isalnum(c) || c == '-' || c == '_'; });
}
inline bool safeRelative(const std::string &s) {
    if (s.empty() || s.size() > 240 || s.front() == '/' || s.back() == '/')
        return false;
    for (unsigned char c : s)
        if (c < 32 || std::string("\\:\"<>|?*").find(char(c)) != std::string::npos)
            return false;
    std::istringstream input(s);
    std::string part;
    while (std::getline(input, part, '/'))
        if (part.empty() || part == "." || part == "..")
            return false;
    return true;
}
inline bool validServer(const std::string &s) {
    auto scheme = s.find("://");
    if (scheme == std::string::npos || (s.substr(0, scheme) != "http" && s.substr(0, scheme) != "https"))
        return false;
    auto authority = s.substr(scheme + 3);
    if (authority.empty() || authority.front() == '/' || authority.find('@') != std::string::npos)
        return false;
    for (unsigned char c : s)
        if (c <= 32 || c == '\\' || c == '"' || c == '#' || c == '?')
            return false;
    return true;
}
inline std::string normalizedServer(std::string s) {
    while (!s.empty() && s.back() == '/')
        s.pop_back();
    if (!validServer(s))
        throw std::runtime_error("Servidor no válido. Usa http://IP:8001");
    return s;
}
inline std::string libraryKey(const std::string &server) {
    uint64_t h = 14695981039346656037ull;
    for (unsigned char c : normalizedServer(server)) {
        h ^= c;
        h *= 1099511628211ull;
    }
    std::ostringstream out;
    out << std::hex << h;
    return out.str();
}
inline bool persists(const std::string &system) {
    return system != "nes" && system != "atari2600" && system != "mame" && system != "vpinball";
}
inline std::vector<std::string> coreNames(const std::string &s) {
    if (s == "nes")
        return {"nestopia_libretro_libnx.nro", "fceumm_libretro_libnx.nro", "quicknes_libretro_libnx.nro"};
    if (s == "atari2600")
        return {"stella2014_libretro_libnx.nro", "stella_libretro_libnx.nro"};
    if (s == "gb" || s == "gbc")
        return {"gambatte_libretro_libnx.nro", "mgba_libretro_libnx.nro"};
    if (s == "gba")
        return {"mgba_libretro_libnx.nro", "gpsp_libretro_libnx.nro"};
    if (s == "snes")
        return {"snes9x_libretro_libnx.nro", "snes9x2010_libretro_libnx.nro"};
    if (s == "mame")
        return {"mame2003_plus_libretro_libnx.nro", "mame2003_libretro_libnx.nro", "fbneo_libretro_libnx.nro"};
    if (s == "nds")
        return {"melonds_libretro_libnx.nro", "desmume_libretro_libnx.nro"};
    if (s == "n64")
        return {"mupen64plus_next_libretro_libnx.nro"};
    if (s == "psx")
        return {"pcsx_rearmed_libretro_libnx.nro"};
    if (s == "psp")
        return {"ppsspp_libretro_libnx.nro"};
    return {};
}
inline fs::path findCore(const Config &config, const std::string &system) {
    for (auto &name : coreNames(system)) {
        auto candidate = fs::path(config.cores) / name;
        if (fs::is_regular_file(candidate))
            return candidate;
        // Algunas distribuciones omiten el sufijo de plataforma.
        auto shortName = name;
        auto pos = shortName.find("_libnx");
        if (pos != std::string::npos)
            shortName.erase(pos, 6);
        candidate = fs::path(config.cores) / shortName;
        if (fs::is_regular_file(candidate))
            return candidate;
    }
    return {};
}
inline std::vector<Game> parseGames(const Json &items) {
    if (!items.is_array() || items.size() > 100000)
        throw std::runtime_error("Catálogo no válido");
    std::vector<Game> result;
    for (auto &j : items) {
        Game g;
        g.id = j.value("id", "");
        g.title = j.value("title", "");
        g.system = j.value("system_id", "");
        g.filename = j.value("filename", "");
        g.revision = j.value("revision", "0");
        g.size = j.value("size", uint64_t(0));
        g.favorite = j.value("favorite", false);
        if (!safeId(g.id) || !safeId(g.system) || !safeRelative(g.filename) ||
            g.filename.find('/') != std::string::npos)
            continue;
        if (coreNames(g.system).empty() || g.title.empty() || g.title.size() > 1000 || g.size == 0)
            continue;
        if (j.contains("cover_url") && j["cover_url"].is_string()) {
            // Solicitar siempre nuestro endpoint, nunca una URL externa del catálogo.
            g.cover = "/api/games/" + g.id + "/cover";
        }
        result.push_back(std::move(g));
    }
    return result;
}
inline std::vector<size_t> filterGames(const std::vector<Game> &games, const std::string &system,
                                       const std::string &query, bool favorites) {
    std::vector<size_t> result;
    auto q = lower(query);
    for (size_t i = 0; i < games.size(); ++i) {
        auto &g = games[i];
        if ((!favorites || g.favorite) && (system.empty() || g.system == system) &&
            lower(g.title).find(q) != std::string::npos)
            result.push_back(i);
    }
    return result;
}
inline std::string quoted(const std::string &s) {
    if (s.find_first_of("\"\r\n") != std::string::npos || s.find('\0') != std::string::npos)
        throw std::runtime_error("Ruta no válida para el reproductor");
    return "\"" + s + "\"";
}
inline std::string sessionConfig(const std::string &directory, const std::string &system, const std::string &home) {
    std::ostringstream out;
    out << "# GameClub: ajustes por sesión; no modifica retroarch.cfg\n"
        << "savestate_auto_load = false\nsavestate_auto_save = false\n"
        << "config_save_on_exit = false\nauto_overrides_enable = false\nuser_language = 3\nsavefiles_in_content_dir = "
           "false\nsavestates_in_content_dir = false\n"
        << "sort_savefiles_enable = false\nsort_savestates_enable = false\n"
        << "sort_savefiles_by_content_enable = false\nsort_savestates_by_content_enable = false\n"
        << "savefile_directory = " << quoted(directory + "/battery") << "\n"
        << "savestate_directory = " << quoted(directory + "/states") << "\n"
        << "content_history_path = " << quoted(home + "/history.lpl") << "\n"
        << "content_favorites_path = " << quoted(home + "/favorites.lpl") << "\n"
        << "autosave_interval = " << (persists(system) ? 10 : 0) << "\n";
    if (!persists(system))
        out << "menu_show_save_state = false\nmenu_show_load_state = false\n";
    return out.str();
}
inline Config loadConfig(const fs::path &root) {
    Config c;
    std::ifstream input(root / "config.json");
    if (!input)
        return c;
    auto j = Json::parse(input);
    c.server = normalizedServer(j.value("server", c.server));
    c.token = j.value("token", "");
    c.cores = j.value("cores", c.cores);
    if (c.token.size() > 2048 || c.token.find_first_of("\r\n") != std::string::npos)
        throw std::runtime_error("Token no válido");
    return c;
}
inline void writeText(const fs::path &path, const std::string &text) {
    fs::create_directories(path.parent_path());
    std::ofstream output(path, std::ios::binary);
    output << text;
    if (!output)
        throw std::runtime_error("No se pudo escribir en la SD");
}
inline void saveConfig(const fs::path &root, const Config &c) {
    normalizedServer(c.server);
    if (c.token.find_first_of("\r\n") != std::string::npos)
        throw std::runtime_error("Token no válido");
    writeText(root / "config.json", Json{{"server", c.server}, {"token", c.token}, {"cores", c.cores}}.dump(2));
}
} // namespace gc
