#pragma once
#include "model.hpp"
#include <atomic>
#include <functional>

namespace gc {
struct Response {
    std::vector<unsigned char> data;
    int status = 0;
};
using Progress = std::function<void(uint64_t, uint64_t)>;
using Status = std::function<void(const std::string &)>;
Response request(const Config &config, const std::string &endpoint, const std::atomic<bool> &cancel,
                 size_t limit = 32 * 1024 * 1024, const std::string &method = "GET", const std::string &body = "",
                 const fs::path &destination = {}, Progress progress = {});
} // namespace gc
