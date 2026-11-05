#include "http.hpp"
#include <cstdio>
#ifdef __SWITCH__
#include <curl/curl.h>
#else
#define NOMINMAX
#include <windows.h>
#include <winhttp.h>
#endif

namespace gc {
namespace {
struct Sink {
    Response response;
    FILE *file = nullptr;
    std::vector<char> buffer;
    size_t written = 0, limit;
    const std::atomic<bool> &cancel;
    Progress progress;
    Sink(size_t maximum, const std::atomic<bool> &stop, Progress report)
        : limit(maximum), cancel(stop), progress(std::move(report)) {}
    ~Sink() {
        if (file)
            std::fclose(file);
    }
    size_t append(const unsigned char *data, size_t size) {
        if (cancel || size > limit - written)
            return 0;
        if (file) {
            if (std::fwrite(data, 1, size, file) != size)
                return 0;
        } else
            response.data.insert(response.data.end(), data, data + size);
        written += size;
        if (progress)
            progress(written, limit);
        return size;
    }
};
#ifdef __SWITCH__
size_t receive(char *data, size_t width, size_t count, void *p) {
    return static_cast<Sink *>(p)->append(reinterpret_cast<unsigned char *>(data), width * count);
}
int report(void *p, curl_off_t total, curl_off_t current, curl_off_t, curl_off_t) {
    auto &s = *static_cast<Sink *>(p);
    if (s.progress && total > 0)
        s.progress(uint64_t(current), uint64_t(total));
    return s.cancel ? 1 : 0;
}
#else
std::wstring wide(const std::string &s) {
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), int(s.size()), nullptr, 0);
    if (!n && !s.empty())
        throw std::runtime_error("Texto UTF-8 no válido");
    std::wstring result(n, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), result.data(), n);
    return result;
}
struct Handle {
    HINTERNET h;
    ~Handle() {
        if (h)
            WinHttpCloseHandle(h);
    }
    operator HINTERNET() const { return h; }
};
#endif
} // namespace
Response request(const Config &config, const std::string &endpoint, const std::atomic<bool> &cancel, size_t limit,
                 const std::string &method, const std::string &body, const fs::path &destination, Progress progress) {
    if (endpoint.rfind("/api/", 0) != 0 || endpoint.find_first_of("\r\n") != std::string::npos)
        throw std::runtime_error("Endpoint no válido");
    auto url = normalizedServer(config.server) + endpoint;
    if (config.token.find_first_of("\r\n") != std::string::npos)
        throw std::runtime_error("Token no válido");
    Sink sink(limit, cancel, std::move(progress));
    if (!destination.empty()) {
        fs::create_directories(destination.parent_path());
        sink.file = std::fopen(destination.string().c_str(), "wb");
        if (!sink.file)
            throw std::runtime_error("No se pudo abrir la descarga en la SD");
        sink.buffer.resize(256 * 1024);
        std::setvbuf(sink.file, sink.buffer.data(), _IOFBF, sink.buffer.size());
    }
#ifdef __SWITCH__
    CURL *curl = curl_easy_init();
    if (!curl)
        throw std::runtime_error("No se pudo iniciar la conexión");
    curl_slist *headers = nullptr;
    if (!config.token.empty())
        headers = curl_slist_append(headers, ("Authorization: Bearer " + config.token).c_str());
    if (!body.empty())
        headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 8L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, destination.empty() ? 180L : 3600L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_BUFFERSIZE, 256L * 1024);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 1024L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 45L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
    curl_easy_setopt(curl, CURLOPT_PROTOCOLS, long(CURLPROTO_HTTP | CURLPROTO_HTTPS));
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, receive);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &sink);
    curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);
    curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, report);
    curl_easy_setopt(curl, CURLOPT_XFERINFODATA, &sink);
    if (method != "GET")
        curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, method.c_str());
    if (!body.empty()) {
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, long(body.size()));
    }
    auto code = curl_easy_perform(curl);
    long status = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    sink.response.status = int(status);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    if (code != CURLE_OK)
        throw std::runtime_error(cancel ? "Operación cancelada"
                                        : "Sin conexión con la Raspberry: revisa Wi-Fi y servidor");
#else
    auto full = wide(url);
    URL_COMPONENTS parts{};
    parts.dwStructSize = sizeof(parts);
    parts.dwHostNameLength = parts.dwUrlPathLength = parts.dwExtraInfoLength = DWORD(-1);
    if (!WinHttpCrackUrl(full.c_str(), 0, 0, &parts))
        throw std::runtime_error("Servidor no válido");
    std::wstring host(parts.lpszHostName, parts.dwHostNameLength);
    std::wstring path(parts.lpszUrlPath, parts.dwUrlPathLength);
    if (parts.dwExtraInfoLength)
        path.append(parts.lpszExtraInfo, parts.dwExtraInfoLength);
    Handle session{WinHttpOpen(L"GameClub-Switch/0.12", WINHTTP_ACCESS_TYPE_NO_PROXY, nullptr, nullptr, 0)};
    if (!session.h)
        throw std::runtime_error("No se pudo iniciar HTTP");
    WinHttpSetTimeouts(session, 8000, 8000, 15000, 15000);
    Handle connection{WinHttpConnect(session, host.c_str(), parts.nPort, 0)};
    auto verb = wide(method);
    Handle req{WinHttpOpenRequest(connection, verb.c_str(), path.c_str(), nullptr, nullptr, nullptr,
                                  parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0)};
    if (!req.h)
        throw std::runtime_error("No se pudo abrir HTTP");
    DWORD disable = WINHTTP_DISABLE_REDIRECTS;
    WinHttpSetOption(req, WINHTTP_OPTION_DISABLE_FEATURE, &disable, sizeof(disable));
    auto headers = wide((config.token.empty() ? "" : "Authorization: Bearer " + config.token + "\r\n") +
                        (body.empty() ? "" : "Content-Type: application/json\r\n"));
    if (!WinHttpSendRequest(req, headers.c_str(), DWORD(headers.size()),
                            body.empty() ? nullptr : const_cast<char *>(body.data()), DWORD(body.size()),
                            DWORD(body.size()), 0) ||
        !WinHttpReceiveResponse(req, nullptr))
        throw std::runtime_error("Sin conexión con la Raspberry");
    DWORD status = 0, size = sizeof(status);
    WinHttpQueryHeaders(req, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, nullptr, &status, &size, nullptr);
    sink.response.status = int(status);
    unsigned char buffer[65536];
    DWORD count = 0;
    while (!cancel) {
        if (!WinHttpReadData(req, buffer, sizeof(buffer), &count))
            throw std::runtime_error("Descarga interrumpida");
        if (!count)
            break;
        if (sink.append(buffer, count) != count)
            throw std::runtime_error("Descarga cancelada, demasiado grande o sin espacio");
    }
    if (cancel)
        throw std::runtime_error("Operación cancelada");
#endif
    if (sink.response.status < 200 || sink.response.status >= 300) {
        if (sink.response.status == 401)
            throw std::runtime_error("Token incorrecto. Revisa Ajustes.");
        throw std::runtime_error("El servidor respondió HTTP " + std::to_string(sink.response.status));
    }
    if (sink.file && std::fflush(sink.file))
        throw std::runtime_error("No se pudo guardar la descarga");
    return std::move(sink.response);
}
} // namespace gc
