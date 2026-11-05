#pragma once
#include "http.hpp"
#include <chrono>
#include <set>

namespace gc {
inline fs::path libraryRoot(const fs::path &root, const Config &config) {
    return root / "libraries" / libraryKey(config.server);
}
inline std::string encode(const std::string &s) {
    static const char *hex = "0123456789ABCDEF";
    std::string out;
    for (unsigned char c : s) {
        if (std::isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~')
            out += char(c);
        else {
            out += '%';
            out += hex[c >> 4];
            out += hex[c & 15];
        }
    }
    return out;
}
inline void cleanSessions(const fs::path &library) {
    auto sessions = library / "sessions";
    if (!fs::is_directory(sessions))
        return;
    for (auto &item : fs::directory_iterator(sessions)) {
        auto name = item.path().filename().string();
        // Solo carpetas generadas y marcadas por GameClub; nunca otros guardados.
        if (!item.is_symlink() && item.is_directory() && name.rfind("run-", 0) == 0 &&
            fs::is_regular_file(item.path() / ".gameclub-session"))
            fs::remove_all(item.path());
    }
}
inline void fetchFile(const Config &config, const std::atomic<bool> &cancel, const std::string &endpoint,
                      const fs::path &dest, uint64_t size, const std::string &revision, Progress progress) {
    if (!size || size > uint64_t(4) * 1024 * 1024 * 1024)
        throw std::runtime_error("Archivo vacío o mayor de 4 GiB");
    auto meta = fs::path(dest.string() + ".json");
    try {
        if (fs::is_regular_file(dest) && fs::file_size(dest) == size) {
            std::ifstream stream(meta);
            Json j;
            stream >> j;
            if (j.value("revision", "") == revision)
                return;
        }
    } catch (...) { /* Una caché incompleta se vuelve a descargar. */
    }
    fs::create_directories(dest.parent_path());
    if (fs::space(dest.parent_path()).available < size + 16 * 1024 * 1024)
        throw std::runtime_error("No hay espacio suficiente en la SD");
    auto temp = fs::path(dest.string() + ".part");
    try {
        request(config, endpoint, cancel, size, "GET", "", temp, std::move(progress));
        if (fs::file_size(temp) != size)
            throw std::runtime_error("Descarga incompleta. Vuelve a intentarlo.");
        if (fs::exists(dest))
            fs::remove(dest);
        fs::rename(temp, dest);
        writeText(meta, Json{{"revision", revision}}.dump());
    } catch (...) {
        std::error_code ec;
        fs::remove(temp, ec);
        throw;
    }
}
struct Launch {
    fs::path core, rom, config;
    std::string args;
};
inline void validateCore(const fs::path &path) {
    std::ifstream input(path, std::ios::binary);
    char header[0x80]{};
    input.read(header, sizeof(header));
    if (input.gcount() != sizeof(header) || std::string(header + 16, 4) != "NRO0")
        throw std::runtime_error("El núcleo instalado no es un NRO válido: " + path.filename().string());
}
inline Launch prepareLaunch(const fs::path &root, const Config &config, const Game &game,
                            const std::atomic<bool> &cancel, Progress progress) {
    Launch result;
    result.core = findCore(config, game.system);
    if (result.core.empty())
        throw std::runtime_error("Instala el núcleo de RetroArch para " + game.system +
                                 " en la carpeta de núcleos de Ajustes.");
    validateCore(result.core);
    if (!safeId(game.id) || !safeRelative(game.filename))
        throw std::runtime_error("Juego no válido");
    auto library = libraryRoot(root, config);
    if (game.system == "mame") {
        auto response = request(config, "/api/games/" + game.id + "/arcade/cores?native=true", cancel);
        auto plans = Json::parse(response.data);
        Json chosen;
        for (auto &candidate : plans.at("candidates")) {
            auto id = candidate.value("core", "");
            if (id != "mame2003_plus" && id != "mame2003" && id != "fbneo")
                continue;
            Config exact = config;
            std::string core = id + "_libretro_libnx.nro";
            auto candidateCore = fs::path(config.cores) / core;
            if (!fs::is_regular_file(candidateCore))
                candidateCore = fs::path(config.cores) / (id + "_libretro.nro");
            if (fs::is_regular_file(candidateCore)) {
                chosen = candidate;
                result.core = candidateCore;
                break;
            }
        }
        if (chosen.is_null())
            throw std::runtime_error("No hay un núcleo instalado compatible con este ROMset. Revisa los núcleos MAME "
                                     "2003-Plus, MAME 2003 o FBNeo.");
        validateCore(result.core);
        auto signature = chosen.value("signature", "");
        auto code = chosen.value("game_code", "");
        if (!safeId(signature) || !safeId(code))
            throw std::runtime_error("Plan arcade no válido");
        auto folder = library / "arcade" / game.id / signature;
        auto files = chosen.at("files");
        if (!files.is_array() || files.empty() || files.size() > 128)
            throw std::runtime_error("Dependencias arcade no válidas");
        std::set<std::string> destinations;
        for (auto &file : files) {
            auto from = file.value("path", ""), to = file.value("destination", "");
            if (!safeRelative(from) || !safeRelative(to) || !destinations.insert(to).second)
                throw std::runtime_error("Ruta arcade no válida");
            fetchFile(config, cancel, "/api/mame/download?path=" + encode(from), folder / to,
                      file.at("size").get<uint64_t>(), signature, progress);
        }
        result.rom = folder / (code + ".zip");
        if (!fs::is_regular_file(result.rom))
            throw std::runtime_error("Falta el ZIP principal del ROMset");
    } else {
        auto ext = lower(fs::path(game.filename).extension().string());
        if (ext == ".7z" || ext == ".cue" || ext == ".m3u" || ext == ".dsi")
            throw std::runtime_error("Este formato necesita un paquete preparado. Usa un archivo de juego autónomo o "
                                     "ZIP compatible con el núcleo.");
        result.rom = library / "roms" / game.system / game.id / game.filename;
        fetchFile(config, cancel, "/api/games/" + game.id + "/download", result.rom, game.size, game.revision,
                  progress);
    }
    auto serial = std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
    auto workspace = library / "sessions" / ("run-" + serial);
    fs::create_directories(workspace);
    writeText(workspace / ".gameclub-session", game.id);
    auto saves = persists(game.system) ? library / "saves" / game.system / game.id : workspace;
    fs::create_directories(saves / "battery");
    fs::create_directories(saves / "states");
    result.config = workspace / "retroarch.cfg";
    writeText(result.config, sessionConfig(saves.generic_string(), game.system, library.generic_string()));
    result.args = quoted(result.core.generic_string()) + " " + quoted(result.rom.generic_string()) +
                  " --appendconfig " + quoted(result.config.generic_string());
    if (result.args.size() >= 4000)
        throw std::runtime_error("Ruta demasiado larga para lanzar el núcleo");
    return result;
}
} // namespace gc
