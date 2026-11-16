#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <vector>

namespace gameclub {
// Small, aligned windows for the random sector reads of a compound VPX file.
// Callers share one cache per read-only container and serialize access.
class TableReadCache {
    static constexpr size_t windowSize = 256 * 1024;
    struct Window {
        uint64_t offset = 0, lastUse = 0;
        size_t size = 0;
        std::vector<unsigned char> data;
    };
    std::array<Window, 4> windows{};
    uint64_t access = 0, fills = 0;
public:
    uint64_t reads() const { return fills; }
    void reset() { *this = TableReadCache{}; }

    template <class ReadAt>
    size_t read(uint64_t offset, unsigned char *output, size_t length, uint64_t fileSize, ReadAt readAt) {
        if (offset >= fileSize) return 0;
        length = static_cast<size_t>(std::min<uint64_t>(length, fileSize - offset));
        size_t copied = 0;
        while (copied < length) {
            const uint64_t cursor = offset + copied;
            const uint64_t start = cursor - cursor % windowSize;
            auto window = std::find_if(windows.begin(), windows.end(), [&](const Window &item) {
                return item.size && item.offset == start;
            });
            if (window == windows.end()) {
                window = std::min_element(windows.begin(), windows.end(),
                    [](const Window &a, const Window &b) { return a.lastUse < b.lastUse; });
                const auto size = static_cast<size_t>(std::min<uint64_t>(windowSize, fileSize - start));
                window->data.resize(size);
                window->offset = start;
                window->size = readAt(start, window->data.data(), size);
                ++fills;
            }
            window->lastUse = ++access;
            const auto within = static_cast<size_t>(cursor - start);
            if (within >= window->size) break;
            const auto amount = std::min(length - copied, window->size - within);
            std::memcpy(output + copied, window->data.data() + within, amount);
            copied += amount;
        }
        return copied;
    }
};
}
