#pragma once
#include <chrono>
#include <ctime>

// Newlib does not supply timegm. Normalize UTC fields without changing the
// process timezone, which would race the emulation and audio threads.
inline std::time_t gameclubTimeGM(const std::tm *value) {
    using namespace std::chrono;
    const int y = value->tm_year + 1900;
    if (y < -32767 || y > 32767)
        return std::time_t(-1);
    const year_month ym = year{y}/January + months{value->tm_mon};
    const auto t = sys_days{ym/1} + days{value->tm_mday-1} + hours{value->tm_hour}
                   + minutes{value->tm_min} + seconds{value->tm_sec};
    return static_cast<std::time_t>(duration_cast<seconds>(t.time_since_epoch()).count());
}
