// POSIX queries/allocation implemented with libnx's real process information.
#include <switch.h>
#include <unistd.h>
#include <malloc.h>
#include <cerrno>
#include <cstdint>

extern "C" int posix_memalign(void **result, size_t alignment, size_t size) {
    if (!result || alignment < sizeof(void *) || alignment % sizeof(void *) || (alignment & (alignment-1)))
        return EINVAL;
    void *value = memalign(alignment, size);
    if (!value)
        return ENOMEM;
    *result = value;
    return 0;
}

extern "C" int getpagesize() { return 0x1000; }

extern "C" long sysconf(int name) {
    if (name == _SC_PAGESIZE)
        return getpagesize();
    u64 value = 0;
    if (name == _SC_NPROCESSORS_ONLN || name == _SC_NPROCESSORS_CONF) {
        if (R_SUCCEEDED(svcGetInfo(&value, InfoType_CoreMask, CUR_PROCESS_HANDLE, 0)))
            return __builtin_popcountll(value);
        errno = EIO;
        return -1;
    }
    if (name == _SC_PHYS_PAGES || name == _SC_AVPHYS_PAGES) {
        if (R_FAILED(svcGetInfo(&value, InfoType_TotalMemorySize, CUR_PROCESS_HANDLE, 0))) {
            errno = EIO;
            return -1;
        }
        if (name == _SC_AVPHYS_PAGES) {
            u64 used = 0;
            if (R_FAILED(svcGetInfo(&used, InfoType_UsedMemorySize, CUR_PROCESS_HANDLE, 0))) {
                errno = EIO;
                return -1;
            }
            value = used > value ? 0 : value - used;
        }
        return static_cast<long>(value / getpagesize());
    }
    errno = EINVAL;
    return -1;
}
