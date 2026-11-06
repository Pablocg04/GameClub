#pragma once
#include <array>
#include <filesystem>

namespace gameclub {
// Rotate only these owned files. Append instead if rotation cannot be completed.
inline bool rotateSessionLogs(const std::filesystem::path &folder) {
    namespace fs = std::filesystem;
    const std::array<const char *, 3> names{
        "switch-player.log", "switch-player.previous.log", "switch-player.previous2.log"};
    std::error_code error;
    for (auto name : names) {
        const auto path = folder / name;
        const auto exists = fs::exists(path, error);
        if (error || (exists && !fs::is_regular_file(path, error)) || error) return false;
    }
    for (size_t i = names.size() - 1; i > 0; --i) {
        const auto from = folder / names[i - 1], to = folder / names[i];
        if (!fs::exists(from, error)) { if (error) return false; else continue; }
        fs::remove(to, error);
        if (error) return false;
        fs::rename(from, to, error);
        if (error) return false;
    }
    return true;
}
}
