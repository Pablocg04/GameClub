#include "input_bindings.hpp"
#include "session_logs.hpp"
#include "texture_upload_queue.hpp"
#include <atomic>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;
static int checks = 0;
static void check(bool ok, const char *message) {
    ++checks; if (!ok) throw std::runtime_error(message);
}
static void write(const fs::path &p, const std::string &s) { std::ofstream f(p); f << s; }
static std::string read(const fs::path &p) { std::ifstream f(p); return {std::istreambuf_iterator<char>(f), {}}; }
int main(int argc, char **argv) {
    try {
        if (argc != 2) throw std::runtime_error("Expected fixture directory");
        const fs::path root = argv[1]; fs::create_directories(root);
        check(gameclub::buttonKeys[10].scan == SDL_SCANCODE_1, "Plus must start, never exit");
        check(gameclub::buttonKeys[3].scan == SDL_SCANCODE_1, "Y must start");
        check(gameclub::buttonKeys[1].scan == SDL_SCANCODE_F12, "B must open VPX menu");
        check(gameclub::buttonKeys[2].scan == SDL_SCANCODE_5 && gameclub::buttonKeys[11].scan == SDL_SCANCODE_5, "Coin controls");
        check(gameclub::buttonKeys[0].scan == SDL_SCANCODE_RETURN, "Plunger control");
        check(gameclub::buttonKeys[6].scan == SDL_SCANCODE_LSHIFT && gameclub::buttonKeys[8].scan == SDL_SCANCODE_LSHIFT &&
              gameclub::buttonKeys[7].scan == SDL_SCANCODE_RSHIFT && gameclub::buttonKeys[9].scan == SDL_SCANCODE_RSHIFT, "Flipper controls");
        bool escape = false; for (auto key : gameclub::buttonKeys) escape |= key.scan == SDL_SCANCODE_ESCAPE;
        check(!escape, "No raw button may directly exit VPX");
        gameclub::TextureUploadQueue<int> uploads;
        int image = 5; std::atomic<int> completed{0}; const auto owner = std::this_thread::get_id();
        std::thread worker([&] { for (int i = 0; i < 100; ++i) uploads.defer(&image, i % 2); });
        worker.join();
        check(completed == 0, "A CPU worker must not upload");
        bool correctThread = true; int linear = 0;
        const auto count = uploads.flush([&](int *p, bool flag) {
            correctThread &= std::this_thread::get_id() == owner && p == &image;
            linear += flag; ++completed;
            if (completed == 1) uploads.defer(p, flag); // Callback must run outside the queue mutex.
        });
        check(count == 100 && completed == 100 && linear == 50 && correctThread, "Cached texture uploads on context owner");
        check(uploads.flush([&](int *, bool) { ++completed; }) == 1 && completed == 101, "Deferred work from upload callback");
        check(uploads.flush([](int *, bool) {}) == 0, "Empty cache path");
        std::atomic<bool> rejected{false};
        uploads.defer(&image, true);
        std::thread wrong([&] { try { uploads.flush([](int *, bool) {}); } catch (const std::logic_error &) { rejected = true; } });
        wrong.join(); check(rejected, "Reject GPU submission from a worker");
        check(uploads.flush([](int *, bool) {}) == 1, "Rejected flush preserves work");
        const auto logs = root / "logs"; fs::create_directories(logs / "nvram");
        write(logs / "nvram/machine.nv", "machine configuration");
        check(gameclub::rotateSessionLogs(logs), "First session log");
        write(logs / "switch-player.log", "first attempt");
        check(gameclub::rotateSessionLogs(logs) && read(logs / "switch-player.previous.log") == "first attempt", "Preserve first attempt");
        write(logs / "switch-player.log", "second attempt");
        check(gameclub::rotateSessionLogs(logs) && read(logs / "switch-player.previous.log") == "second attempt" &&
              read(logs / "switch-player.previous2.log") == "first attempt", "Preserve two attempts");
        check(read(logs / "nvram/machine.nv") == "machine configuration", "Rotation preserves NVRAM");
        const auto collision = root / "collision"; fs::create_directories(collision / "switch-player.previous.log");
        write(collision / "switch-player.log", "preserve current");
        check(!gameclub::rotateSessionLogs(collision) && read(collision / "switch-player.log") == "preserve current", "Do not overwrite unrelated directories");
        std::cout << checks << " comprobaciones de arranque, controles y texturas superadas.\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << "Runtime: " << e.what() << '\n'; return 1; }
}
