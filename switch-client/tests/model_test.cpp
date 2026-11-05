#include "library.hpp"
#include "lru.hpp"
#include <memory>
#include <iostream>
#include "../../switch-pinball/include/utc.hpp"

using namespace gc;
static int checks = 0;
static void check(bool ok, const char *why) {
    ++checks;
    if (!ok)
        throw std::runtime_error(why);
}
template <class T> static void rejects(T action, const char *why) {
    bool caught = false;
    try {
        action();
    } catch (const std::exception &) {
        caught = true;
    }
    check(caught, why);
}
static void fakeCore(const fs::path &p) {
    std::string bytes(128, 0);
    bytes.replace(16, 4, "NRO0");
    writeText(p, bytes);
}
int main(int argc, char **argv) {
    try {
        LruCache<int> covers(24);
        for (int i = 0; i < 24; ++i) covers.put("old-" + std::to_string(i), i);
        covers.put("aaa-visible", 100);
        bool preserved = true;
        for (int i = 0; i < 100; ++i) {
            const auto value = covers.get("aaa-visible");
            preserved = preserved && value && *value == 100;
            covers.put("zzz-" + std::to_string(i), i);
        }
        check(preserved, "LRU: carátula visible conservada durante 100 inserciones");
        check(covers.size() == 24 && !covers.get("old-0"), "LRU: límite y descarte del menos usado");
        std::weak_ptr<int> retired;
        {
            LruCache<std::shared_ptr<int>> owned(1);
            auto resource = std::make_shared<int>(1); retired = resource;
            owned.put("a", std::move(resource));
            owned.put("b", std::make_shared<int>(2));
            check(retired.expired(), "LRU: liberar recursos expulsados");
            owned.clear(); check(owned.size() == 0, "LRU: limpiar al cambiar servidor");
        }
        check(validServer("http://192.168.0.47:8001"), "servidor LAN");
        check(validServer("https://gameclub.example/library"), "servidor HTTPS con prefijo");
        check(!validServer("http://user:password@host") && !validServer("file:///etc/passwd") &&
                  !validServer("http://x\r\nHeader:y"),
              "servidores inseguros");
        check(normalizedServer("http://host:8001///") == "http://host:8001", "normalizar servidor");
        check(libraryKey("http://host:8001/") == libraryKey("http://host:8001"), "misma biblioteca");
        check(libraryKey("http://host:8001") != libraryKey("http://host:8002"), "caché aislada por servidor");
        check(safeRelative("parent/disk.chd") && !safeRelative("../escape") && !safeRelative("folder/../../bad") &&
                  !safeRelative("sdmc:/bad") && !safeRelative("a//b"),
              "rutas de dependencias");
        check(!safeId("../oops") && !safeId("hello\" world") && safeId("aB_123-45"), "identificadores");
        rejects([] { quoted("sdmc:/rom\"injection"); }, "comillas de lanzamiento");
        rejects([] { quoted(std::string("a\0b", 3)); }, "NUL de lanzamiento");
        check(quoted("sdmc:/con espacios/game.gba") == "\"sdmc:/con espacios/game.gba\"", "argumentos con espacios");
        check(!persists("nes") && !persists("atari2600") && !persists("mame") && !persists("vpinball") &&
                  persists("nds") && persists("gba"),
              "política de guardados");
        auto session = sessionConfig("sdmc:/switch/gameclub/fresh", "nes", "sdmc:/switch/gameclub");
        check(session.find("savestate_auto_load = false") != std::string::npos &&
                  session.find("savestate_auto_save = false") != std::string::npos &&
                  session.find("menu_show_load_state = false") != std::string::npos,
              "sin restaurar ni guardar estados");
        check(sessionConfig("sdmc:/x", "nds", "sdmc:/g").find("autosave_interval = 10") != std::string::npos,
              "batería de Nintendo DS");
        Json one = {
            {"id", "abc"}, {"title", "Mi clásico"}, {"system_id", "nes"}, {"filename", "Juego con espacios.zip"},
            {"size", 4},   {"revision", "123"},     {"favorite", true},   {"cover_url", "https://evil.example/token"}};
        Json items = Json::array({one});
        auto bad = one;
        bad["id"] = "../outside";
        items.push_back(bad);
        bad = one;
        bad["system_id"] = "unsupported";
        items.push_back(bad);
        bad = one;
        bad["filename"] = "../bad.zip";
        items.push_back(bad);
        auto games = parseGames(items);
        check(games.size() == 1 && games[0].cover == "/api/games/abc/cover",
              "catálogo y carátula de origen controlado");
        check(filterGames(games, "nes", "CLÁSICO", true).size() == 1 &&
                  filterGames(games, "nes", "missing", false).empty(),
              "búsqueda y favoritos");
        rejects([] { parseGames(Json::object()); }, "catálogo no array");
        check(!coreNames("vpinball").empty() && coreNames("switch").empty() && !coreNames("nds").empty(),
              "sistemas soportados");
        std::tm utc{};
        utc.tm_year = 70; utc.tm_mday = 1;
        check(gameclubTimeGM(&utc) == 0, "UTC: época Unix");
        utc.tm_year = 100; utc.tm_mon = 1; utc.tm_mday = 29;
        check(gameclubTimeGM(&utc) == 951782400, "UTC: año bisiesto");
        utc.tm_year = 123; utc.tm_mon = 12; utc.tm_mday = 1;
        check(gameclubTimeGM(&utc) == 1704067200, "UTC: mes normalizado");
        if (argc >= 3) {
            fs::path root = fs::absolute(argv[2]);
            fs::create_directories(root);
            Config config;
            config.server = argv[1];
            config.token = "fixture-token";
            config.cores = (root / "cores").generic_string();
            saveConfig(root, config);
            auto loaded = loadConfig(root);
            check(loaded.server == config.server && loaded.token == config.token, "preferencias persistidas");
            fakeCore(root / "cores/nestopia_libretro_libnx.nro");
            fakeCore(root / "cores/mgba_libretro_libnx.nro");
            fakeCore(root / "cores/mame2003_plus_libretro_libnx.nro");
            std::atomic<bool> cancel{false};
            auto r = request(config, "/api/games", cancel);
            auto list = parseGames(Json::parse(r.data));
            check(list.size() == 4, "API autenticada real con mesas VPX");
            auto first = prepareLaunch(root, config, list[0], cancel, {});
            check(fs::file_size(first.rom) == 4 && first.args.find("--appendconfig") != std::string::npos,
                  "descarga y lanzamiento");
            auto before = fs::last_write_time(first.rom);
            auto second = prepareLaunch(root, config, list[0], cancel, {});
            check(first.rom == second.rom && fs::last_write_time(second.rom) == before && first.config != second.config,
                  "caché válida y sesión NES nueva");
            std::ifstream a(first.config);
            std::string text((std::istreambuf_iterator<char>(a)), {});
            check(text.find("/sessions/run-") != std::string::npos, "batería NES temporal");
            auto gba = prepareLaunch(root, config, list[1], cancel, {});
            std::ifstream b(gba.config);
            std::string gbaText((std::istreambuf_iterator<char>(b)), {});
            check(gbaText.find("/saves/gba/") != std::string::npos, "batería GBA persistente");
            auto again = prepareLaunch(root, config, list[1], cancel, {});
            std::ifstream c(again.config);
            std::string againText((std::istreambuf_iterator<char>(c)), {});
            check(againText == gbaText, "ruta de batería estable");
            auto mame = prepareLaunch(root, config, list[2], cancel, {});
            check(mame.rom.filename() == "fixture.zip" && fs::is_regular_file(mame.rom.parent_path() / "parent.zip"),
                  "dependencias MAME");
            auto evil = list[2];
            evil.id = "evil";
            rejects([&] { prepareLaunch(root, config, evil, cancel, {}); }, "dependencia con traversal rechazada");
            auto partial = list[0];
            partial.id = "partial";
            partial.size = 8;
            rejects([&] { prepareLaunch(root, config, partial, cancel, {}); }, "descarga truncada rechazada");
            auto dest = libraryRoot(root, config) / "roms/nes/partial" / partial.filename;
            check(!fs::exists(dest) && !fs::exists(dest.string() + ".part"), "no publicar descargas parciales");
            Config unauthorized = config;
            unauthorized.token = "incorrect";
            rejects([&] { request(unauthorized, "/api/games", cancel); }, "401 visible");
            rejects([&] { request(config, "//evil.example", cancel); }, "endpoint externo rechazado");
            Game pin;
            pin.id = "pinball"; pin.system = "vpinball"; pin.filename = "Fixture.zip";
            rejects([&] { prepareLaunch(root, config, pin, cancel, {}); }, "VPX exige su motor nativo");
            fakeCore(root / "pinball/GameClubPinball.nro");
            bool extracting = false, intermediate = false;
            int phases = 0;
            auto native = prepareLaunch(root, config, pin, cancel, [&](uint64_t done, uint64_t total) {
                if (extracting && done > 0 && done < total) intermediate = true;
            }, [&](const std::string &text) {
                ++phases;
                extracting = text.find("Extrayendo") != std::string::npos;
            });
            check(phases >= 5 && intermediate, "VPX: fases y progreso durante archivos grandes");
            check(native.rom.filename() == "Fixture.vpx" && fs::is_regular_file(native.rom.parent_path()/"pinmame/roms/fixture.zip"),
                  "VPX: extraer mesa y ROM del manifiesto");
            check(native.args.find("--gameclub-state") != std::string::npos && native.args.find("-Play") != std::string::npos &&
                  native.args.find("--appendconfig") == std::string::npos, "VPX: lanzamiento nativo");
            auto nvram = native.config.parent_path()/"nvram/fixture.nv";
            writeText(nvram, "machine configuration");
            auto repeated = prepareLaunch(root, config, pin, cancel, {});
            check(native.config == repeated.config && fs::file_size(nvram) == 21, "VPX: NVRAM estable entre sesiones");
            auto hostile = pin; hostile.id = "pinball-evil";
            rejects([&] { prepareLaunch(root, config, hostile, cancel, {}); }, "VPX: traversal del manifiesto rechazado");
            hostile.id = "pinball-crc";
            rejects([&] { prepareLaunch(root, config, hostile, cancel, {}); }, "VPX: CRC incorrecto rechazado");
            auto interrupted = pin; interrupted.id = "pinball-cancel";
            extracting = false;
            rejects([&] {
                prepareLaunch(root, config, interrupted, cancel, [&](uint64_t done, uint64_t) {
                    if (extracting && done > 0) cancel = true;
                }, [&](const std::string &text) { extracting = text.find("Extrayendo") != std::string::npos; });
            }, "VPX: cancelar durante la extracción de un archivo");
            const auto canceledFolder = libraryRoot(root, config) / "pinball/pinball-cancel";
            bool leftover = false;
            for (const auto &item : fs::directory_iterator(canceledFolder))
                if (item.is_directory()) leftover = true;
            check(!leftover, "VPX: cancelar limpia la extracción y no publica la caché");
            check(fs::is_regular_file(canceledFolder / "package.bin"), "VPX: conservar descarga completa al cancelar extracción");
            cancel = false;
            auto resumed = prepareLaunch(root, config, interrupted, cancel, {});
            check(fs::is_regular_file(resumed.rom), "VPX: reintentar tras cancelar sin volver a descargar");
            auto keep = libraryRoot(root, config) / "sessions/run-user-data";
            writeText(keep / "notes.txt", "preserve");
            auto save = libraryRoot(root, config) / "saves/gba/gba/battery/game.srm";
            writeText(save, "persistent");
            a.close();
            b.close();
            c.close();
            cleanSessions(libraryRoot(root, config));
            check(!fs::exists(first.config) && fs::exists(keep / "notes.txt") && fs::exists(save),
                  "limpieza limitada a sesiones marcadas");
            writeText(root / "cores/nestopia_libretro_libnx.nro", "bad");
            rejects([&] { prepareLaunch(root, config, list[0], cancel, {}); }, "núcleo inválido rechazado");
        }
        std::cout << checks << " comprobaciones Switch superadas.\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
