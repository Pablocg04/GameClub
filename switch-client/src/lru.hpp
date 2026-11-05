#pragma once
#include <list>
#include <map>
#include <string>
#include <stdexcept>
#include <utility>

namespace gc {
template<class T> class LruCache {
    using Entries = std::list<std::pair<std::string, T>>;
    Entries entries;
    std::map<std::string, typename Entries::iterator> lookup;
    size_t capacity;
public:
    explicit LruCache(size_t limit) : capacity(limit) {
        if (!limit) throw std::invalid_argument("Empty cache capacity");
    }
    LruCache(const LruCache &) = delete;
    LruCache &operator=(const LruCache &) = delete;
    T *get(const std::string &key) {
        auto found = lookup.find(key);
        if (found == lookup.end()) return nullptr;
        entries.splice(entries.begin(), entries, found->second);
        return &found->second->second;
    }
    void put(const std::string &key, T value) {
        if (auto old = get(key)) { *old = std::move(value); return; }
        entries.emplace_front(key, std::move(value));
        lookup.emplace(key, entries.begin());
        if (entries.size() > capacity) {
            lookup.erase(entries.back().first);
            entries.pop_back();
        }
    }
    void clear() { lookup.clear(); entries.clear(); }
    size_t size() const { return entries.size(); }
};
}
