// Exercises the Horizon branch using host threads: no self-detach is required.
#include <thread>
#include <future>
// Fail compilation if this branch reintroduces the unsupported operation.
#define detach gameclub_detach_is_not_supported
#include "ThreadPool.h"
#undef detach
#include <iostream>
#include <stdexcept>

static int checks = 0;
static void check(bool value) {
    if (!value) throw std::runtime_error("ThreadPool regression");
    ++checks;
}
int main() {
    try {
        std::atomic<int> completed{0};
        for (int round = 0; round < 50; ++round) {
            ThreadPool pool(3);
            for (int i = 0; i < 32; ++i) pool.enqueue([&] { ++completed; });
        }
        check(completed == 1600); // Destruction drains all queued work and joins.
        ThreadPool pool(3);
        auto result = pool.enqueue([] { return 42; });
        check(result.get() == 42);
        auto failure = pool.enqueue([]() -> int { throw std::runtime_error("fixture"); });
        bool caught = false;
        try { failure.get(); } catch (const std::runtime_error &) { caught = true; }
        check(caught);
        completed = 0;
        pool.set_queue_size_limit(2);
        for (int i = 0; i < 100; ++i) pool.enqueue([&] { ++completed; });
        pool.wait_until_empty();
        pool.wait_until_nothing_in_flight();
        check(completed == 100);
        for (int round = 0; round < 15; ++round) {
            for (int i = 0; i < 20; ++i) pool.enqueue([&] { ++completed; });
            pool.set_pool_size(1);
            pool.set_pool_size(4);
        }
        pool.wait_until_nothing_in_flight();
        check(completed == 400); // Downsizing retains queued work; growth restarts workers.
        pool.set_pool_size(0); // The API clamps zero to one worker.
        check(pool.enqueue([] { return 9; }).get() == 9);
        struct ThreadLifetime {
            std::atomic<int> *live = nullptr;
            ~ThreadLifetime() { if (live) --*live; }
        };
        std::atomic<int> live{0};
        {
            ThreadPool workers(3);
            std::promise<void> release;
            auto gate = release.get_future().share();
            std::atomic<int> started{0};
            for (int i = 0; i < 3; ++i) workers.enqueue([&] {
                thread_local ThreadLifetime lifetime;
                lifetime.live = &live;
                ++live;
                ++started;
                gate.wait();
            });
            while (started != 3) std::this_thread::yield();
            check(live == 3);
            release.set_value();
        }
        check(live == 0); // TLS destructors have finished when the pool is destroyed.
        std::cout << checks << " comprobaciones de hilos Switch superadas.\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
