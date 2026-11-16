#define SDL_MAIN_HANDLED
#include "library.hpp"
#include "lru.hpp"
#include <SDL.h>
#include <SDL_image.h>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <functional>
#include <map>
#include <mutex>
#include <thread>
#include <memory>
#ifdef __SWITCH__
#include <curl/curl.h>
#include <switch.h>
#endif

using namespace gc;
namespace {
constexpr SDL_Color ink{16, 11, 32, 255}, background{33, 18, 61, 255}, panel{53, 32, 82, 255},
    purple{133, 73, 237, 255}, cream{255, 244, 220, 255}, muted{194, 181, 216, 255}, mint{117, 229, 202, 255},
    yellow{255, 212, 91, 255}, pink{255, 121, 184, 255};
SDL_Color accent(const std::string &s) {
    if (s == "nes" || s == "psx")
        return pink;
    if (s == "atari2600" || s == "mame")
        return yellow;
    if (s == "gb" || s == "gbc" || s == "gba" || s == "nds")
        return mint;
    return {197, 161, 255, 255};
}
std::string systemTitle(const std::string &id) {
    static const std::map<std::string, const char *> names{
        {"atari2600", "Atari 2600"}, {"gb", "Game Boy"}, {"gba", "Game Boy Advance"},
        {"gbc", "Game Boy Color"}, {"gc", "GameCube"}, {"mame", "Arcade / MAME"},
        {"n3ds", "Nintendo 3DS"}, {"n64", "Nintendo 64"}, {"nds", "Nintendo DS"},
        {"nes", "NES"}, {"ps2", "PlayStation 2"}, {"psp", "PSP"}, {"psvita", "PlayStation Vita"},
        {"psx", "PlayStation"}, {"snes", "Super Nintendo"}, {"switch", "Nintendo Switch"},
        {"vpinball", "Visual Pinball"}, {"wii", "Nintendo Wii"}, {"wiiu", "Nintendo Wii U"}
    };
    const auto name = names.find(id);
    return name == names.end() ? id : name->second;
}
std::string gameCount(size_t count) {
    return std::to_string(count) + (count == 1 ? " juego" : " juegos");
}
uint32_t nextChar(const std::string &s, size_t &i) {
    unsigned char c = s[i++];
    if (c < 128)
        return c;
    int count = c < 224 ? 1 : c < 240 ? 2 : 3;
    uint32_t n = c & ((1 << (6 - count)) - 1);
    while (count-- && i < s.size())
        n = (n << 6) | (s[i++] & 63);
    return n;
}
struct Glyph {
    SDL_Rect area;
    int advance;
};
struct Font {
    SDL_Texture *texture = nullptr;
    std::map<uint32_t, Glyph> glyphs;
    int line = 24;
    void load(SDL_Renderer *r, const fs::path &assets, const std::string &name) {
        texture = IMG_LoadTexture(r, (assets / (name + ".png")).string().c_str());
        if (!texture)
            throw std::runtime_error("No se pudo cargar la tipografía");
        std::ifstream file(assets / (name + ".json"));
        Json j;
        file >> j;
        line = j.at("line");
        for (auto &item : j.at("glyphs").items()) {
            auto v = item.value();
            glyphs[uint32_t(std::stoul(item.key()))] = {{v[0], v[1], v[2], v[3]}, v[4]};
        }
    }
    void text(SDL_Renderer *r, const std::string &value, int x, int y, SDL_Color color, int width = 1200,
              int lines = 1) {
        SDL_SetTextureColorMod(texture, color.r, color.g, color.b);
        int start = x, row = 0;
        for (size_t i = 0; i < value.size();) {
            auto ch = nextChar(value, i);
            if (ch == '\n') {
                x = start;
                y += line;
                if (++row >= lines)
                    break;
                continue;
            }
            auto it = glyphs.find(ch);
            if (it == glyphs.end())
                it = glyphs.find('?');
            if (it == glyphs.end())
                continue;
            auto &g = it->second;
            if (x + g.advance > start + width) {
                if (++row >= lines)
                    break;
                x = start;
                y += line;
            }
            SDL_Rect dst{x, y, g.area.w, g.area.h};
            SDL_RenderCopy(r, texture, &g.area, &dst);
            x += g.advance;
        }
    }
};
struct Event {
    int type = 0, generation = 0;
    std::string id, message;
    fs::path path;
    std::vector<Game> games;
    Launch launch;
    std::shared_ptr<SDL_Surface> image;
    bool favorite = false;
};
struct Worker {
    struct Task {
        int generation;
        bool quiet;
        std::function<Event()> work;
    };
    std::atomic<bool> cancel{false};
    std::atomic<bool> cancelOperation{false};
    std::atomic<uint64_t> received{0}, total{0};
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<Task> jobs;
    std::deque<Event> events;
    std::thread thread;
    std::mutex statusMutex;
    std::string statusText = "Preparando juego...";
    void setStatus(const std::string &text) {
        std::lock_guard<std::mutex> lock(statusMutex);
        statusText = text;
        received = 0;
        total = 0;
    }
    std::string status() {
        std::lock_guard<std::mutex> lock(statusMutex);
        return statusText;
    }
    Worker()
        : thread([this] {
              for (;;) {
                  Task task;
                  {
                      std::unique_lock<std::mutex> lock(mutex);
                      wake.wait(lock, [&] { return cancel || !jobs.empty(); });
                      if (cancel)
                          break;
                      task = std::move(jobs.front());
                      jobs.pop_front();
                  }
                  Event event;
                  try {
                      event = task.work();
                  } catch (const std::exception &e) {
                      event.type = task.quiet ? 6 : 5;
                      event.message = e.what();
                  }
                  event.generation = task.generation;
                  std::lock_guard<std::mutex> lock(mutex);
                  events.push_back(std::move(event));
              }
          }) {}
    void stop() {
        cancel = true;
        cancelOperation = true;
        wake.notify_all();
        if (thread.joinable())
            thread.join();
    }
    ~Worker() { stop(); }
    void push(int generation, bool quiet, std::function<Event()> task, bool priority = false) {
        std::lock_guard<std::mutex> lock(mutex);
        Task t{generation, quiet, std::move(task)};
        if (priority)
            jobs.push_front(std::move(t));
        else
            jobs.push_back(std::move(t));
        wake.notify_one();
    }
    std::deque<Event> take() {
        std::lock_guard<std::mutex> lock(mutex);
        std::deque<Event> out;
        out.swap(events);
        return out;
    }
    void clear() {
        std::lock_guard<std::mutex> lock(mutex);
        jobs.clear();
    }
    void clearCovers() {
        std::lock_guard<std::mutex> lock(mutex);
        jobs.erase(std::remove_if(jobs.begin(), jobs.end(), [](const Task &task) { return task.quiet; }), jobs.end());
    }
};
enum Section { Library, Favorites, Settings, SectionCount };
constexpr int tabX = 492, tabY = 10, tabWidth = 232, tabStep = 250;
constexpr int cardX = 32, cardY = 165, cardWidth = 224, cardHeight = 224, cardStepX = 248, cardStepY = 240;
constexpr int listX = 32, listWidth = 1210, consoleY = 145, consoleStep = 58, consolesPerPage = 8;

enum Input { Up, Down, Left, Right, Accept, Back, Search, Favorite, Prev, Next, Refresh, Exit, PageBack, PageForward };
class App {
    SDL_Renderer *renderer;
    fs::path root, assets;
    Config config;
    Font title, body, small;
    Worker worker;
    std::vector<Game> games;
    std::vector<size_t> visible;
    std::vector<std::string> systems;
    std::map<std::string, size_t> systemCounts;
    LruCache<std::shared_ptr<SDL_Texture>> textures{32};
    std::set<std::string> requested, unavailable;
    std::map<std::string, fs::path> corePaths;
    uint64_t coverJobs = 0, coverLoads = 0;
    std::string query, system, notice = "Conectando con tu biblioteca...", message, editText;
    bool navFocused = false, choosingConsole = true, busy = false, details = false, editing = false, launching = false;
    int tab = Library, selected = 0, field = 0, systemIndex = 0, generation = 1, editField = 0;
    std::string pickId;
    uint64_t inputTime = 0;
    void rect(int x, int y, int w, int h, SDL_Color c) {
        SDL_SetRenderDrawColor(renderer, c.r, c.g, c.b, c.a);
        SDL_Rect r{x, y, w, h};
        SDL_RenderFillRect(renderer, &r);
    }
    void pixel(int x, int y, int w, int h, SDL_Color c, bool focus = false) {
        rect(x + 5, y + 5, w, h, ink);
        rect(x + 10, y, w - 20, h, c);
        rect(x + 5, y + 5, w - 10, h - 10, c);
        rect(x, y + 10, w, h - 20, c);
        SDL_Color border = focus ? mint : ink;
        rect(x + 10, y, w - 20, 3, border);
        rect(x + 10, y + h - 3, w - 20, 3, border);
        rect(x, y + 10, 3, h - 20, border);
        rect(x + w - 3, y + 10, 3, h - 20, border);
        rect(x + 5, y + 5, 7, 3, border);
        rect(x + w - 12, y + 5, 7, 3, border);
        rect(x + 5, y + h - 8, 7, 3, border);
        rect(x + w - 12, y + h - 8, 7, 3, border);
    }
    void controller(int x, int y, int scale, SDL_Color c) {
        static const char *art[] = {"0001111111111000", "0012222222222100", "0122222222222210",
                                    "0122322222242210", "0123332222424210", "0122322112242210",
                                    "0122222222222210", "0012211111122100", "0001100000011000"};
        for (int row = 0; row < 9; row++)
            for (int col = 0; col < 16; col++) {
                int v = art[row][col] - '0';
                if (v)
                    rect(x + col * scale, y + row * scale, scale, scale, v == 1 || v == 3 ? ink : v == 4 ? pink : c);
            }
    }
    Game *current() { return selected >= 0 && selected < int(visible.size()) ? &games[visible[selected]] : nullptr; }
    bool consoleList() const { return tab == Library && choosingConsole; }
    void filter() {
        visible = filterGames(games, tab == Favorites ? "" : system, query, tab == Favorites);
        selected = std::clamp(selected, 0, std::max(0, int(visible.size()) - 1));
    }
    void updateSystems() {
        systemCounts.clear();
        for (const auto &game : games)
            ++systemCounts[game.system];
        systems.clear();
        for (const auto &[id, count] : systemCounts)
            systems.push_back(id);
        if (!systemCounts.count(system)) system.clear();
        systemIndex = system.empty() ? 0 : int(std::lower_bound(systems.begin(), systems.end(), system) - systems.begin()) + 1;
    }
    void loadCached() {
        try {
            auto folder = libraryRoot(root, config);
            cleanSessions(folder);
            std::ifstream input(folder / "catalog.json");
            if (input) {
                Json j;
                input >> j;
                games = parseGames(j);
                updateSystems();
                filter();
                notice = "Biblioteca en caché";
            }
        } catch (const std::exception &e) {
            notice = e.what();
        }
    }
    void reload() {
        if (busy)
            return;
        busy = true;
        notice = "Actualizando biblioteca...";
        auto cfg = config;
        auto folder = libraryRoot(root, cfg);
        worker.clearCovers();
        requested.clear();
        unavailable.clear();
        corePaths.clear();
        worker.push(
            generation, false,
            [this, cfg, folder] {
                auto data = request(cfg, "/api/games", worker.cancel);
                auto j = Json::parse(data.data);
                Event e;
                e.type = 0;
                e.games = parseGames(j);
                writeText(folder / "catalog.json", j.dump());
                return e;
            },
            true);
    }
    std::string coverKey(const Game &game) { return game.id + "-" + (safeId(game.revision) ? game.revision : "0"); }
    void cover(const Game &game, int x, int y, int w, int h) {
        auto key = coverKey(game);
        auto texture = textures.get(key);
        if (!texture && !unavailable.count(key) && requested.size() < 4 && requested.insert(key).second) {
            // Disk access, decoding and scaling must stay off the rendering thread.
            auto path = libraryRoot(root, config) / "covers" / (key + ".jpg");
            auto cfg = config;
            auto endpoint = game.cover;
            ++coverJobs;
            worker.push(generation, true, [this, cfg, path, endpoint, key] {
                Event e;
                e.type = 1;
                e.id = key;
                auto temp = fs::path(path.string() + ".part");
                try {
                    if (!fs::is_regular_file(path)) {
                        if (endpoint.empty()) return e;
                        request(cfg, endpoint, worker.cancel, 8 * 1024 * 1024, "GET", "", temp);
                        fs::rename(temp, path);
                    }
                    std::shared_ptr<SDL_Surface> original(IMG_Load(path.string().c_str()), SDL_FreeSurface);
                    if (!original || original->w <= 0 || original->h <= 0) return e;
                    double ratio = std::min(180.0 / original->w, 240.0 / original->h);
                    e.image.reset(SDL_CreateRGBSurfaceWithFormat(0, std::max(1, int(original->w * ratio)),
                        std::max(1, int(original->h * ratio)), 32, SDL_PIXELFORMAT_RGBA32), SDL_FreeSurface);
                    if (e.image && SDL_BlitScaled(original.get(), nullptr, e.image.get(), nullptr)) e.image.reset();
                } catch (...) {
                    std::error_code ec;
                    fs::remove(temp, ec);
                }
                return e;
            });
        }
        if (texture) {
            int tw = 0, th = 0;
            SDL_QueryTexture(texture->get(), nullptr, nullptr, &tw, &th);
            double ratio = std::min(double(w) / tw, double(h) / th);
            int dw = int(tw * ratio), dh = int(th * ratio);
            rect(x, y, w, h, ink);
            SDL_Rect dst{x + (w - dw) / 2, y + (h - dh) / 2, dw, dh};
            SDL_RenderCopy(renderer, texture->get(), nullptr, &dst);
        } else {
            rect(x, y, w, h, panel);
            int scale = std::max(2, std::min(w / 20, h / 12));
            controller(x + (w - 16 * scale) / 2, y + (h - 9 * scale) / 2, scale, accent(game.system));
        }
    }
    void resetSelection() {
        selected = 0;
        details = false;
        worker.clearCovers();
        requested.clear();
        filter();
    }
    void setTab(int value) {
        tab = (value + SectionCount) % SectionCount;
        if (tab == Library) choosingConsole = true;
        resetSelection();
        navFocused = false;
    }
    void chooseConsole() {
        system = systemIndex == 0 ? "" : systems[systemIndex - 1];
        choosingConsole = false;
        navFocused = false;
        resetSelection();
    }
    void openConsoles() {
        choosingConsole = true;
        navFocused = false;
        resetSelection();
    }
    void edit(int target) {
        editField = target;
        editText = target == 0 ? query : target == 1 ? config.server : target == 2 ? config.token : config.cores;
#ifdef __SWITCH__
        SwkbdConfig keyboard;
        if (R_FAILED(swkbdCreate(&keyboard, 0))) {
            message = "No se pudo abrir el teclado. Edita config.json en la SD.";
            return;
        }
        if (target == 2)
            swkbdConfigMakePresetPassword(&keyboard);
        else
            swkbdConfigMakePresetDefault(&keyboard);
        swkbdConfigSetHeaderText(&keyboard, target == 0   ? "Buscar juegos"
                                            : target == 1 ? "Servidor GameClub"
                                            : target == 2 ? "Token de acceso"
                                                          : "Carpeta de núcleos RetroArch");
        swkbdConfigSetInitialText(&keyboard, editText.c_str());
        swkbdConfigSetStringLenMax(&keyboard, target == 2 ? 2048 : 250);
        char result[4096]{};
        auto rc = swkbdShow(&keyboard, result, sizeof(result));
        swkbdClose(&keyboard);
        if (R_SUCCEEDED(rc)) {
            editText = result;
            applyEdit();
        }
#else
        editing = true;
        SDL_StartTextInput();
#endif
    }
    void applyEdit() {
        editing = false;
        SDL_StopTextInput();
        if (editField == 0) {
            query = editText;
            selected = 0;
            filter();
        } else if (editField == 1)
            config.server = editText;
        else if (editField == 2)
            config.token = editText;
        else
            config.cores = editText;
    }
    void favorite() {
        auto *game = current();
        if (!game || busy)
            return;
        busy = true;
        auto cfg = config;
        auto g = *game;
        worker.push(
            generation, false,
            [this, cfg, g] {
                request(cfg, "/api/games/" + g.id, worker.cancel, 1024 * 1024, "PATCH",
                        Json{{"favorite", !g.favorite}}.dump());
                Event e;
                e.type = 2;
                e.id = g.id;
                e.favorite = !g.favorite;
                return e;
            },
            true);
    }
    void play() {
        auto *game = current();
        if (!game || busy)
            return;
#ifdef __SWITCH__
        if (game->system == "vpinball" && appletGetAppletType() != AppletType_Application &&
            appletGetAppletType() != AppletType_SystemApplication) {
            message = "Pinball necesita memoria completa. Abre Homebrew Menu manteniendo R al iniciar un juego instalado y vuelve a abrir GameClub.";
            return;
        }
#endif
        busy = true;
        launching = true;
        worker.cancelOperation = false;
        worker.setStatus("Preparando juego...");
        notice = "Preparando juego...";
        auto cfg = config;
        auto g = *game;
        worker.received = 0;
        worker.total = 0;
        worker.push(
            generation, false,
            [this, cfg, g] {
                Event e;
                e.type = 3;
                try {
                    e.launch = prepareLaunch(root, cfg, g, worker.cancelOperation, [this](uint64_t a, uint64_t b) {
                        worker.received = a;
                        worker.total = b;
                    }, [this](const std::string &text) { worker.setStatus(text); });
                } catch (const std::exception &error) {
                    if (g.system == "vpinball") {
                        std::ofstream log(root / "pinball-prepare.log", std::ios::app);
                        log << "ERROR: " << error.what() << '\n';
                    }
                    throw;
                }
                return e;
            },
            true);
    }
    void connect() {
        try {
            config.server = normalizedServer(config.server);
            saveConfig(root, config);
            ++generation;
            worker.clear();
            textures.clear();
            unavailable.clear();
            corePaths.clear();
            games.clear();
            system.clear();
            query.clear();
            requested.clear();
            updateSystems();
            filter();
            busy = false;
            loadCached();
            reload();
        } catch (const std::exception &e) {
            message = e.what();
        }
    }

  public:
    bool running = true;
    Json performance() const {
        return { {"cover_jobs", coverJobs}, {"cover_uploads", coverLoads},
                 {"cached_textures", textures.size()}, {"pending_covers", requested.size()},
                 {"version", GAMECLUB_SWITCH_VERSION} };
    }
    std::string startupDetail;
    App(SDL_Renderer *r, fs::path data, fs::path resources, std::string q, int initialTab, std::string detail, bool showAll,
        bool pinballError)
        : renderer(r), root(std::move(data)), assets(std::move(resources)), query(std::move(q)),
          choosingConsole(!showAll && query.empty() && detail.empty()), tab(std::clamp(initialTab, int(Library), int(Settings))),
          pickId(std::move(detail)) {
        title.load(r, assets, "pixel");
        body.load(r, assets, "body");
        small.load(r, assets, "small");
        fs::create_directories(root);
        try {
            config = loadConfig(root);
        } catch (const std::exception &e) {
            message = std::string(e.what()) + ". Revisa config.json o Ajustes.";
            tab = Settings;
        }
        loadCached();
        reload();
        if (pinballError && message.empty())
            message = "El motor de pinball terminó con un error. Revisa switch-player.log en la carpeta de la mesa.";
    }
    ~App() {
        worker.stop();
        textures.clear();
        SDL_DestroyTexture(title.texture);
        SDL_DestroyTexture(body.texture);
        SDL_DestroyTexture(small.texture);
    }
    void poll() {
        for (auto &event : worker.take()) {
            if (event.generation != generation)
                continue;
            if (event.type == 0) {
                games = std::move(event.games);
                updateSystems();
                filter();
                busy = false;
                notice = "Biblioteca actualizada";
                if (!pickId.empty()) {
                    for (size_t i = 0; i < visible.size(); i++)
                        if (games[visible[i]].id == pickId) {
                            selected = int(i);
                            details = true;
                            break;
                        }
                    pickId.clear();
                }
            } else if (event.type == 1) {
                requested.erase(event.id);
                if (event.image) {
                    auto texture = std::shared_ptr<SDL_Texture>(SDL_CreateTextureFromSurface(renderer, event.image.get()), SDL_DestroyTexture);
                    if (texture) {
                        SDL_SetTextureScaleMode(texture.get(), SDL_ScaleModeLinear);
                        textures.put(event.id, std::move(texture));
                        unavailable.erase(event.id);
                        ++coverLoads;
                    } else unavailable.insert(event.id);
                } else unavailable.insert(event.id);
            } else if (event.type == 2) {
                for (auto &g : games)
                    if (g.id == event.id)
                        g.favorite = event.favorite;
                filter();
                busy = false;
                notice = "Favoritos actualizados";
            } else if (event.type == 3) {
                busy = false;
                launching = false;
                if (worker.cancelOperation) {
                    notice = "Preparación cancelada";
                    continue;
                }
#ifdef __SWITCH__
                if (!envHasNextLoad()) {
                    message = "El Homebrew Menu no permite abrir otro NRO en este entorno.";
                    continue;
                }
                auto rc = envSetNextLoad(event.launch.core.generic_string().c_str(), event.launch.args.c_str());
                {
                    std::ofstream log(root / "pinball-prepare.log", std::ios::app);
                    u64 memory = 0;
                    svcGetInfo(&memory, InfoType_TotalMemorySize, CUR_PROCESS_HANDLE, 0);
                    log << "AppletType: " << int(appletGetAppletType()) << ", memoria: " << memory << '\n';
                    log << "envSetNextLoad: " << rc << '\n';
                }
                if (R_SUCCEEDED(rc))
                    running = false;
                else
                    message = "No se pudo abrir el motor NRO (" + std::to_string(rc) + ").";
#else
                writeText(root / "launch-preview.json", Json{{"core", event.launch.core.generic_string()},
                                                             {"rom", event.launch.rom.generic_string()},
                                                             {"args", event.launch.args}}
                                                            .dump(2));
                message = "Preparación comprobada. La apertura del NRO necesita una Nintendo Switch.";
#endif
            } else if (event.type == 5) {
                busy = false;
                launching = false;
                message = event.message;
                notice = "No se pudo completar la operación";
            }
        }
    }
    void key(Input key) {
        if (editing) {
            if (key == Back) {
                editing = false;
                SDL_StopTextInput();
            } else if (key == Accept)
                applyEdit();
            return;
        }
        if (key == Exit) {
            running = false;
            return;
        }
        if (!message.empty()) {
            if (key == Accept || key == Back)
                message.clear();
            return;
        }
        if (busy) {
            if (key == Back && launching) {
                worker.cancelOperation = true;
                worker.setStatus("Cancelando preparación...");
                notice = "Cancelando preparación...";
            }
            return;
        }
        if (key == Refresh) {
            reload();
            return;
        }
        if (key == Prev) {
            setTab(tab - 1);
            return;
        }
        if (key == Next) {
            setTab(tab + 1);
            return;
        }
        if (details) {
            if (key == Back)
                details = false;
            else if (key == Accept)
                play();
            else if (key == Favorite)
                favorite();
            return;
        }
        if (navFocused) {
            if (key == Left || key == Right) {
                setTab(tab + (key == Left ? -1 : 1));
                navFocused = true;
            } else if (key == Accept || key == Down || key == Back) {
                navFocused = false;
            }
            return;
        }
        if (key == Search) {
            if (tab != Settings) {
                if (consoleList()) {
                    systemIndex = 0;
                    chooseConsole();
                }
                edit(0);
            }
            return;
        }
        if (key == Back) {
            if (tab == Library && !consoleList())
                openConsoles();
            else
                navFocused = true;
            return;
        }
        if (tab == Settings) {
            if (key == Up && field == 0)
                navFocused = true;
            else if (key == Up)
                --field;
            else if (key == Down)
                field = std::min(3, field + 1);
            else if (key == Accept) {
                if (field == 3)
                    connect();
                else
                    edit(field + 1);
            }
            return;
        }
        if (consoleList()) {
            if (key == Up && systemIndex == 0)
                navFocused = true;
            else if (key == Up)
                --systemIndex;
            else if (key == Down)
                systemIndex = std::min(int(systems.size()), systemIndex + 1);
            else if (key == PageBack)
                systemIndex = std::max(0, systemIndex - consolesPerPage);
            else if (key == PageForward)
                systemIndex = std::min(int(systems.size()), systemIndex + consolesPerPage);
            else if (key == Accept)
                chooseConsole();
            return;
        }
        if (key == Favorite) {
            favorite();
            return;
        }
        if (key == Accept) {
            if (current())
                details = true;
            return;
        }
        auto previousPage = selected / 10;
        if (key == PageBack)
            selected = std::max(0, selected - 10);
        else if (key == PageForward)
            selected = std::min(std::max(0, int(visible.size()) - 1), selected + 10);
        else if (key == Up && selected < 5)
            navFocused = true;
        else if (key == Up)
            selected -= 5;
        else if (key == Down)
            selected = std::min(std::max(0, int(visible.size()) - 1), selected + 5);
        else if (key == Left && selected % 5 != 0)
            --selected;
        else if (key == Right)
            selected = std::min(std::max(0, int(visible.size()) - 1), selected + 1);
        if (previousPage != selected / 10) {
            worker.clearCovers();
            requested.clear();
        }
    }
    void type(const char *text) {
        if (editing && editText.size() + std::strlen(text) < 2048)
            editText += text;
    }
    void erase() {
        if (!editing || editText.empty())
            return;
        size_t i = editText.size() - 1;
        while (i > 0 && (static_cast<unsigned char>(editText[i]) & 0xC0) == 0x80)
            --i;
        editText.resize(i);
    }
    void click(int x, int y) {
        if (editing || !message.empty()) {
            key(Accept);
            return;
        }
        if (busy) return;
        if (y >= tabY && y < tabY + 48 && x >= tabX) {
            const int index = (x - tabX) / tabStep;
            if (index < SectionCount && (x - tabX) % tabStep < tabWidth)
                setTab(index);
            return;
        }
        if (details) {
            if (y >= 548 && y < 606 && x >= 746 && x < 1098)
                key(Accept);
            else if (y >= 548 && y < 606 && x >= 471 && x < 706)
                key(Favorite);
            else if (x < 132 || x >= 1136 || y < 91 || y >= 646)
                key(Back);
            return;
        }
        navFocused = false;
        if (consoleList()) {
            if (x >= listX && x < listX + listWidth && y >= consoleY &&
                y < consoleY + consolesPerPage * consoleStep && (y - consoleY) % consoleStep < 48) {
                const int index = (systemIndex / consolesPerPage) * consolesPerPage + (y - consoleY) / consoleStep;
                if (index <= int(systems.size())) {
                    systemIndex = index;
                    chooseConsole();
                }
            }
        } else if (tab != Settings) {
            if (y >= 120 && y < 154) {
                if (tab == Library && x >= listX && x < 300)
                    openConsoles();
                else if (x >= (tab == Library ? 314 : listX) && x < listX + listWidth)
                    key(Search);
                return;
            }
            if (x >= cardX && y >= cardY) {
                const int col = (x - cardX) / cardStepX, row = (y - cardY) / cardStepY;
                const int n = (selected / 10) * 10 + row * 5 + col;
                if (col < 5 && row < 2 && (x - cardX) % cardStepX < cardWidth &&
                    (y - cardY) % cardStepY < cardHeight && n < int(visible.size())) {
                    selected = n;
                    details = true;
                }
            }
        } else if (x >= listX && x < listX + listWidth && y >= 155 && y < 475 && (y - 155) % 80 < 65) {
            field = (y - 155) / 80;
            key(Accept);
        }
    }
#ifndef __SWITCH__
    void checkLibraryNavigation() {
        // The preview fixture has a GBA catalog and one favorite, on NES.
        setTab(Library);
        const auto gba = std::find(systems.begin(), systems.end(), "gba");
        if (gba == systems.end()) throw std::runtime_error("Falta la consola de prueba");
        systemIndex = 0;
        for (auto i = systems.begin(); i <= gba; ++i)
            key(Down);
        key(Accept);
        if (consoleList() || visible.size() != 1 || !current() || current()->system != "gba")
            throw std::runtime_error("La biblioteca no filtró por consola");
        key(Back);
        if (!consoleList()) throw std::runtime_error("B no volvió a las consolas");
        key(Next);
        if (tab != Favorites || visible.size() != 1 || !current() || current()->system != "nes")
            throw std::runtime_error("Favoritos heredó el filtro de consola");
        click(tabX + tabStep * Settings + 20, tabY + 20);
        if (tab != Settings) throw std::runtime_error("Ajustes no se puede abrir en la barra superior");
        key(Next);
        click(listX + 20, consoleY + 20);
        if (tab != Library || consoleList() || visible.size() != games.size())
            throw std::runtime_error("No se pudo volver a todos los juegos");
    }
#endif
    void draw() {
        rect(0, 0, 1280, 720, background);
        for (int x = 4; x < 1280; x += 28)
            for (int y = 78; y < 720; y += 28)
                rect(x, y, 2, 2, panel);
        rect(0, 0, 1280, 68, ink);
        controller(20, 20, 3, mint);
        title.text(renderer, "GAMECLUB", 82, 22, cream);
        small.text(renderer, "SWITCH / " GAMECLUB_SWITCH_VERSION, 290, 25, muted);
        const char *labels[] = {"Biblioteca", "Favoritos", "Ajustes"};
        for (int i = 0; i < SectionCount; i++) {
            const int x = tabX + i * tabStep;
            pixel(x, tabY, tabWidth, 48, tab == i ? purple : panel, navFocused && tab == i);
            body.text(renderer, labels[i], x + 20, tabY + 11, cream, tabWidth - 40);
        }
        const std::string heading = tab == Settings ? "AJUSTES" : tab == Favorites ? "TUS FAVORITOS"
            : consoleList() ? "BIBLIOTECA / CONSOLAS" : system.empty() ? "TODOS LOS JUEGOS" : systemTitle(system);
        title.text(renderer, heading, listX, 86, cream, 1010);
        if (tab != Settings && !consoleList()) {
            small.text(renderer, gameCount(visible.size()), 1090, 90, muted, 155);
            int searchX = listX;
            if (tab == Library) {
                pixel(listX, 120, 268, 34, purple);
                small.text(renderer, "B  Volver a consolas", listX + 14, 126, cream, 236);
                searchX = 314;
            }
            pixel(searchX, 120, listX + listWidth - searchX, 34, ink);
            small.text(renderer, query.empty() ? "Y  Buscar juegos" : query, searchX + 15, 126,
                       query.empty() ? muted : cream, listX + listWidth - searchX - 30);
            int page = selected / 10;
            for (int n = page * 10; n < std::min(int(visible.size()), page * 10 + 10); n++) {
                auto &g = games[visible[n]];
                int slot = n - page * 10, x = cardX + (slot % 5) * cardStepX, y = cardY + (slot / 5) * cardStepY;
                pixel(x, y, cardWidth, cardHeight, panel, !navFocused && selected == n);
                cover(g, x + 5, y + 9, cardWidth - 10, 153);
                rect(x + 5, y + 162, cardWidth - 10, 4, accent(g.system));
                small.text(renderer, systemTitle(g.system), x + 12, y + 173, accent(g.system), cardWidth - 24);
                small.text(renderer, g.title, x + 12, y + 194, cream, cardWidth - 24, 1);
                if (g.favorite) {
                    rect(x + cardWidth - 31, y + 12, 22, 25, ink);
                    body.text(renderer, "*", x + cardWidth - 26, y + 11, yellow, 20);
                }
            }
            if (visible.empty()) {
                controller(544, 250, 12, mint);
                body.text(renderer,
                          games.empty() ? "Tu biblioteca está lista para la primera partida."
                                        : "No hay juegos en esta vista.",
                          366, 400, cream, 840);
                small.text(renderer, "Y: buscar   |   L/R: cambiar vista   |   -: actualizar", 366, 444, muted, 800);
            }
            if (!visible.empty())
                small.text(renderer,
                           "Página " + std::to_string(page + 1) + " / " + std::to_string((visible.size() + 9) / 10),
                           1060, 651, muted, 190);
        } else if (consoleList()) {
            const int first = (systemIndex / consolesPerPage) * consolesPerPage;
            for (int i = first; i <= std::min(int(systems.size()), first + consolesPerPage - 1); i++) {
                const std::string id = i == 0 ? "" : systems[i - 1];
                const std::string label = i == 0 ? "Todos los juegos" : systemTitle(id);
                const size_t count = i == 0 ? games.size() : systemCounts.at(id);
                const int y = consoleY + (i - first) * consoleStep;
                pixel(listX, y, listWidth, 48, systemIndex == i ? purple : panel, !navFocused && systemIndex == i);
                rect(listX + 12, y + 10, 5, 28, i == 0 ? mint : accent(id));
                body.text(renderer, label, listX + 31, y + 11, cream, 990);
                small.text(renderer, gameCount(count), 1068, y + 13, cream, 155);
            }
        } else {
            const std::string fields[] = {"Servidor: " + config.server,
                                          "Token: " + std::string(config.token.empty() ? "sin token" : "********"),
                                          "Núcleos: " + config.cores, "Guardar y conectar"};
            for (int i = 0; i < 4; i++) {
                pixel(listX, 155 + i * 80, listWidth, 65, i == 3 ? purple : panel, !navFocused && field == i);
                body.text(renderer, fields[i], listX + 23, 174 + i * 80, cream, listWidth - 46);
            }
            small.text(renderer, "Instala RetroArch para Switch y sus núcleos NRO en la SD.", listX + 15, 510, muted, 960);
            small.text(renderer, "MAME, NES y Atari: partida nueva. Otras consolas: batería local.", listX + 15, 544, muted, 970);
            small.text(renderer, "Los juegos y las BIOS no están incluidos.", listX + 15, 578, muted, 970);
        }
        rect(0, 681, 1280, 39, ink);
        const char *controls = consoleList() ? "A Elegir consola   Y Buscar   L/R Secciones   ZL/ZR Página   - Recargar   + Salir"
            : tab == Settings ? "A Editar / conectar   L/R Secciones   - Recargar   + Salir"
            : "A Abrir   B Volver   X Favorito   Y Buscar   L/R Secciones   ZL/ZR Página   - Recargar   + Salir";
        small.text(renderer, controls, listX, 691, cream, listWidth);
        small.text(renderer, notice, listX, 650, muted, 805);
        if (details && current()) {
            auto &g = *current();
            rect(0, 68, 1280, 613, background);
            pixel(132, 91, 1004, 555, panel);
            cover(g, 158, 126, 280, 385);
            title.text(renderer, systemTitle(g.system), 471, 125, accent(g.system), 620);
            body.text(renderer, g.title, 471, 174, cream, 620, 3);
            small.text(renderer, g.system == "vpinball" ? "Motor nativo Visual Pinball + PinMAME."
                                                       : "Se abre con RetroArch para Switch.", 471, 292, muted, 610, 2);
            small.text(renderer,
                       persists(g.system) ? "Conserva la batería de este juego en la SD."
                                          : "Cada apertura empieza de cero, sin restaurar partida.",
                       471, 348, mint, 610, 3);
            auto found = corePaths.find(g.system);
            if (found == corePaths.end()) {
                auto path = g.system == "vpinball" ? root / "pinball/GameClubPinball.nro" : findCore(config, g.system);
                if (!fs::is_regular_file(path)) path.clear();
                found = corePaths.emplace(g.system, std::move(path)).first;
            }
            const auto &core = found->second;
            small.text(renderer, core.empty() ? (g.system == "vpinball" ? "Falta el motor. Instala el ZIP de pinball."
                                                                     : "Falta el núcleo. Revisa Ajustes.") : core.filename().string(), 471, 427,
                       core.empty() ? pink : muted, 610, 2);
            pixel(471, 548, 235, 58, ink);
            body.text(renderer, g.favorite ? "X Quitar favorito" : "X Favorito", 489, 566, cream, 210);
            pixel(746, 548, 352, 58, yellow);
            body.text(renderer, g.system == "vpinball" ? "A Jugar pinball" : "A Jugar con RetroArch", 766, 566, ink, 320);
        }
        if (busy && launching) {
            pixel(430, 280, 650, 185, panel);
            body.text(renderer, worker.status(), 460, 307, cream, 590);
            auto total = worker.total.load(), received = worker.received.load();
            double ratio = total ? std::min(1., double(received) / double(total)) : 0.;
            rect(460, 358, 580, 18, ink);
            rect(460, 358, int(580 * ratio), 18, mint);
            small.text(renderer, total ? std::to_string(received / (1024*1024)) + " / " +
                       std::to_string(total / (1024*1024)) + " MiB" : "Preparando archivos...", 460, 389, muted, 580);
            small.text(renderer, "B Cancelar", 460, 426, cream, 580);
        }
        if (editing) {
            pixel(285, 240, 900, 230, panel);
            title.text(renderer, editField == 0 ? "BUSCAR" : "EDITAR", 315, 269, cream, 800);
            pixel(310, 320, 845, 58, ink, true);
            body.text(renderer, editField == 2 ? std::string(editText.size(), '*') : editText, 326, 337, cream, 810);
            small.text(renderer, "Enter: aceptar / Escape: cancelar", 315, 415, muted, 800);
        }
        if (!message.empty()) {
            pixel(300, 220, 880, 270, panel);
            title.text(renderer, "GAMECLUB", 330, 250, yellow, 800);
            body.text(renderer, message, 330, 300, cream, 810, 5);
            small.text(renderer, "A / B: volver", 330, 451, mint, 800);
        }
    }
};
} // namespace

int main(int argc, char **argv) {
    SDL_SetMainReady();
    fs::path assets, root;
    std::string screenshot, query, detail;
    int frames = 0, tab = 0;
    bool headless = false, exerciseCovers = false, showAll = false, pinballError = false;
#ifdef __SWITCH__
    pinballError = argc > 1 && std::strcmp(argv[1], "--pinball-error") == 0;
    romfsInit();
    auto socketResult = socketInitializeDefault();
    curl_global_init(CURL_GLOBAL_DEFAULT);
    assets = "romfs:/";
    root = "sdmc:/switch/gameclub";
    padConfigureInput(1, HidNpadStyleSet_NpadStandard);
    PadState pad;
    padInitializeDefault(&pad);
#else
    assets = "switch-client/build/romfs";
    root = "dist/switch-preview-data";
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--headless")
            headless = true;
        else if (arg == "--all")
            showAll = true;
        else if (arg == "--exercise-covers")
            exerciseCovers = true;
        else if (i + 1 < argc) {
            std::string value = argv[++i];
            if (arg == "--assets")
                assets = value;
            else if (arg == "--data-dir")
                root = value;
            else if (arg == "--screenshot")
                screenshot = value;
            else if (arg == "--frames")
                frames = std::stoi(value);
            else if (arg == "--query")
                query = value;
            else if (arg == "--detail")
                detail = value;
            else if (arg == "--tab")
                tab = std::stoi(value);
        }
    }
#endif
    SDL_Window *window = nullptr;
    SDL_Surface *surface = nullptr;
    SDL_Renderer *renderer = nullptr;
    int exitCode = 0;
    try {
#ifdef __SWITCH__
        if (R_FAILED(socketResult))
            throw std::runtime_error("No se pudo iniciar la red");
#endif
#ifdef __SWITCH__
        const auto subsystems = SDL_INIT_VIDEO;
#else
        const auto subsystems = SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER;
#endif
        if (SDL_Init(subsystems))
            throw std::runtime_error(SDL_GetError());
        IMG_Init(IMG_INIT_JPG | IMG_INIT_PNG);
        if (headless) {
            surface = SDL_CreateRGBSurfaceWithFormat(0, 1280, 720, 32, SDL_PIXELFORMAT_RGBA32);
            renderer = SDL_CreateSoftwareRenderer(surface);
        } else {
            window = SDL_CreateWindow("GameClub Switch - vista previa", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                      1280, 720, SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE);
            renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
            if (!renderer)
                renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
        }
        if (!renderer)
            throw std::runtime_error(SDL_GetError());
        SDL_RenderSetLogicalSize(renderer, 1280, 720);
        {
            App app(renderer, root, assets, query, tab, detail, showAll || exerciseCovers, pinballError);
            uint64_t lastMove = 0;
            const auto began = SDL_GetTicks64();
            uint64_t drawnFrames = 0;
            double maxDrawMs = 0;
            int direction = -1, count = 0;
            while (app.running) {
#ifdef __SWITCH__
                if (!appletMainLoop())
                    break;
                padUpdate(&pad);
                u64 down = padGetButtonsDown(&pad), held = padGetButtons(&pad);
                auto stick = padGetStickPos(&pad, 0);
                int move = -1;
                if ((held & HidNpadButton_AnyUp) || stick.y > 16000)
                    move = Up;
                else if ((held & HidNpadButton_AnyDown) || stick.y < -16000)
                    move = Down;
                else if ((held & HidNpadButton_AnyLeft) || stick.x < -16000)
                    move = Left;
                else if ((held & HidNpadButton_AnyRight) || stick.x > 16000)
                    move = Right;
                auto now = SDL_GetTicks64();
                if (move >= 0 && (direction != move || now - lastMove > (direction == move ? 170 : 300))) {
                    app.key(Input(move));
                    lastMove = now;
                }
                direction = move;
                const std::pair<u64, Input> buttons[] = {
                    {HidNpadButton_A, Accept},      {HidNpadButton_B, Back},    {HidNpadButton_X, Favorite},
                    {HidNpadButton_Y, Search},      {HidNpadButton_L, Prev},    {HidNpadButton_R, Next},
                    {HidNpadButton_Minus, Refresh}, {HidNpadButton_Plus, Exit}, {HidNpadButton_ZL, PageBack},
                    {HidNpadButton_ZR, PageForward}};
                for (auto &button : buttons)
                    if (down & button.first)
                        app.key(button.second);
#else
                (void)lastMove;
                (void)direction;
#endif
                SDL_Event event;
                while (SDL_PollEvent(&event)) {
                    if (event.type == SDL_QUIT)
                        app.running = false;
                    else if (event.type == SDL_TEXTINPUT)
                        app.type(event.text.text);
                    else if (event.type == SDL_KEYDOWN) {
                        auto key = event.key.keysym.sym;
                        if (key == SDLK_BACKSPACE)
                            app.erase();
                        else if (key == SDLK_UP)
                            app.key(Up);
                        else if (key == SDLK_DOWN)
                            app.key(Down);
                        else if (key == SDLK_LEFT)
                            app.key(Left);
                        else if (key == SDLK_RIGHT)
                            app.key(Right);
                        else if (key == SDLK_RETURN)
                            app.key(Accept);
                        else if (key == SDLK_ESCAPE)
                            app.key(Back);
                        else if (key == SDLK_F3)
                            app.key(Search);
                        else if (key == SDLK_F2)
                            app.key(Favorite);
                        else if (key == SDLK_PAGEUP)
                            app.key(Prev);
                        else if (key == SDLK_PAGEDOWN || key == SDLK_TAB)
                            app.key(Next);
                        else if (key == SDLK_F5)
                            app.key(Refresh);
                    } else if (event.type == SDL_MOUSEBUTTONUP && event.button.button == SDL_BUTTON_LEFT)
                        app.click(event.button.x, event.button.y);
                }
#ifndef __SWITCH__
                if (exerciseCovers && count == 60)
                    app.checkLibraryNavigation();
                if (exerciseCovers && count > 0 && count <= 420 && count % 60 == 0) {
                    const Input moves[] = {PageForward, PageForward, PageForward, PageBack, PageForward, PageBack, PageForward};
                    app.key(moves[count / 60 - 1]);
                }
#endif
                const auto drawStart = SDL_GetPerformanceCounter();
                app.poll();
                app.draw();
                maxDrawMs = std::max(maxDrawMs, 1000.0 * double(SDL_GetPerformanceCounter() - drawStart) /
                                                 double(SDL_GetPerformanceFrequency()));
                ++drawnFrames;
                if (frames && ++count >= frames) {
                    if (!screenshot.empty()) {
                        SDL_Surface *shot = SDL_CreateRGBSurfaceWithFormat(0, 1280, 720, 32, SDL_PIXELFORMAT_RGBA32);
                        SDL_RenderReadPixels(renderer, nullptr, SDL_PIXELFORMAT_RGBA32, shot->pixels, shot->pitch);
                        IMG_SavePNG(shot, screenshot.c_str());
                        SDL_FreeSurface(shot);
                    }
                    break;
                }
                SDL_RenderPresent(renderer);
#ifdef __SWITCH__
                SDL_Delay(1);
#endif
                if (headless)
                    SDL_Delay(16);
            }
            try {
                auto report = app.performance();
                report["frames"] = drawnFrames;
                report["elapsed_ms"] = SDL_GetTicks64() - began;
                report["max_draw_ms"] = maxDrawMs;
                SDL_RendererInfo info{};
                if (SDL_GetRendererInfo(renderer, &info) == 0) {
                    report["renderer"] = info.name ? info.name : "unknown";
                    report["accelerated"] = bool(info.flags & SDL_RENDERER_ACCELERATED);
                }
                writeText(root / "launcher-performance.json", report.dump(2));
            } catch (...) { /* Telemetry must never prevent launching or exiting. */ }
        }
    } catch (const std::exception &e) {
        exitCode = 1;
#ifdef __SWITCH__
        consoleInit(nullptr);
        printf("GameClub\n\n%s\n\nPulsa + para salir.\n", e.what());
        while (appletMainLoop()) {
            padUpdate(&pad);
            if (padGetButtonsDown(&pad) & HidNpadButton_Plus)
                break;
            consoleUpdate(nullptr);
        }
        consoleExit(nullptr);
#else
        std::fprintf(stderr, "GameClub: %s\n", e.what());
#endif
    }
    if (renderer)
        SDL_DestroyRenderer(renderer);
    if (surface)
        SDL_FreeSurface(surface);
    if (window)
        SDL_DestroyWindow(window);
    IMG_Quit();
    SDL_Quit();
#ifdef __SWITCH__
    curl_global_cleanup();
    socketExit();
    romfsExit();
#endif
    return exitCode;
}
