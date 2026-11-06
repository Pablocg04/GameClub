#pragma once
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

namespace gameclub {
// CPU workers may queue work; only the context owner may submit OpenGL uploads.
template<class Image> class TextureUploadQueue {
    std::thread::id owner = std::this_thread::get_id();
    std::mutex mutex;
    std::vector<std::pair<Image *, bool>> pending;
public:
    void defer(Image *image, bool linear) {
        std::lock_guard lock(mutex);
        pending.emplace_back(image, linear);
    }
    template<class Upload> size_t flush(Upload upload) {
        if (std::this_thread::get_id() != owner)
            throw std::logic_error("Texture upload outside OpenGL context thread");
        std::vector<std::pair<Image *, bool>> ready;
        { std::lock_guard lock(mutex); ready.swap(pending); }
        for (const auto &[image, linear] : ready) upload(image, linear);
        return ready.size();
    }
};
}
