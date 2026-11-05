#pragma once
#include "http.hpp"

namespace gc {
Launch preparePinball(const fs::path &root, const Config &config, const Game &game,
                      const std::atomic<bool> &cancel, Progress progress, Status status = {});
}
