#include "library.hpp"
#include "miniz/miniz.h"
#include <map>
#include <memory>
#ifdef _WIN32
#include <thread>
#endif

namespace gc {
namespace {
constexpr uint64_t limit = uint64_t(8) * 1024 * 1024 * 1024;
struct Zip {
    mz_zip_archive zip{};
    explicit Zip(const fs::path &path) {
        if (!mz_zip_reader_init_file(&zip, path.string().c_str(), 0))
            throw std::runtime_error("No se pudo abrir el paquete de pinball");
    }
    ~Zip() { mz_zip_reader_end(&zip); }
    Zip(const Zip &) = delete;
};
bool validFile(const std::string &name) {
    if (!safeRelative(name))
        return false;
    const std::set<std::string> blocked = {".exe", ".dll", ".so", ".nro", ".apk", ".bat", ".cmd", ".ps1", ".sh", ".lnk", ".url"};
    return !blocked.count(lower(fs::path(name).extension().string()));
}
void checkTable(const fs::path &path) {
    const std::string magic("\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 8);
    char bytes[8]{};
    std::ifstream f(path, std::ios::binary);
    f.read(bytes, sizeof(bytes));
    if (f.gcount() != 8 || std::string(bytes, 8) != magic)
        throw std::runtime_error("El paquete no contiene una mesa VPX válida");
}
void publishCache(const fs::path &staging, const fs::path &cache) {
    std::error_code error;
    fs::rename(staging, cache, error);
#ifdef _WIN32
    // Windows can briefly deny a directory rename just after its files close.
    // Preserve atomic publication; retry only sharing/access failures, bounded.
    for (int retry = 0; error && retry < 5 &&
         (error == std::errc::permission_denied || error == std::errc::device_or_resource_busy || error.value() == 32); ++retry) {
        std::this_thread::sleep_for(std::chrono::milliseconds(25 << retry));
        fs::rename(staging, cache, error);
    }
#endif
    if (error) throw fs::filesystem_error("Publicar caché de pinball", staging, cache, error);
}
struct Extract {
    FILE *file;
    const std::atomic<bool> &cancel;
    const Progress &progress;
    uint64_t base, total, written = 0;
};
size_t extractBytes(void *user, mz_uint64 offset, const void *bytes, size_t size) {
    auto &out = *static_cast<Extract *>(user);
    if (out.cancel || offset != out.written || std::fwrite(bytes, 1, size, out.file) != size)
        return 0;
    out.written += size;
    if (out.progress) out.progress(out.base + out.written, out.total);
    return size;
}
void unpack(const fs::path &package, const fs::path &staging, const Json &manifest,
            const std::atomic<bool> &cancel, const Progress &progress) {
    const auto &files = manifest.at("files");
    if (!files.is_array() || files.empty() || files.size() > 10000)
        throw std::runtime_error("Manifiesto de pinball no válido");
    Zip input(package);
    if (mz_zip_reader_get_num_files(&input.zip) > 12000)
        throw std::runtime_error("Demasiados archivos en el paquete de pinball");
    std::map<std::string, mz_uint> members;
    uint64_t total = 0;
    for (mz_uint i = 0; i < mz_zip_reader_get_num_files(&input.zip); ++i) {
        mz_zip_archive_file_stat stat{};
        if (!mz_zip_reader_file_stat(&input.zip, i, &stat) || (stat.m_bit_flag & 1) ||
            ((stat.m_external_attr >> 16) & 0170000) == 0120000)
            throw std::runtime_error("El paquete contiene una entrada no admitida");
        if (stat.m_is_directory)
            continue;
        auto size = mz_zip_reader_get_filename(&input.zip, i, nullptr, 0);
        if (size < 2 || size > 1024)
            throw std::runtime_error("Nombre de archivo demasiado largo");
        std::string name(size, '\0');
        mz_zip_reader_get_filename(&input.zip, i, name.data(), size);
        if (name.find('\0') != size - 1)
            throw std::runtime_error("Nombre ZIP no válido");
        name.pop_back();
        std::replace(name.begin(), name.end(), '\\', '/');
        if (!validFile(name) || !members.emplace(lower(name), i).second || stat.m_uncomp_size > limit - total)
            throw std::runtime_error("Paquete inseguro o demasiado grande");
        total += stat.m_uncomp_size;
    }
    if (total + 16 * 1024 * 1024 > fs::space(staging).available)
        throw std::runtime_error("No hay espacio para descomprimir la mesa en la SD");
    std::set<std::string> destinations;
    uint64_t unpacked = 0;
    if (progress) progress(0, total);
    for (const auto &item : files) {
        if (cancel)
            throw std::runtime_error("Preparación cancelada");
        auto member = item.at("member").get<std::string>();
        std::replace(member.begin(), member.end(), '\\', '/');
        auto dest = item.at("destination").get<std::string>();
        if (!validFile(member) || !validFile(dest) || !destinations.insert(lower(dest)).second)
            throw std::runtime_error("Rutas del manifiesto no válidas");
        const auto found = members.find(lower(member));
        if (found == members.end())
            throw std::runtime_error("El paquete no coincide con el manifiesto");
        mz_zip_archive_file_stat stat{};
        mz_zip_reader_file_stat(&input.zip, found->second, &stat);
        auto crc = lower(item.at("crc").get<std::string>());
        if (crc.size() != 8 || crc.find_first_not_of("0123456789abcdef") != std::string::npos ||
            stat.m_uncomp_size != item.at("size").get<uint64_t>() || stat.m_crc32 != std::stoul(crc, nullptr, 16))
            throw std::runtime_error("El paquete ha cambiado. Actualiza la biblioteca");
        auto output = staging / dest;
        fs::create_directories(output.parent_path());
        std::vector<char> buffer(512 * 1024);
        std::unique_ptr<FILE, decltype(&std::fclose)> file(std::fopen(output.string().c_str(), "wb"), &std::fclose);
        if (!file) throw std::runtime_error("No se pudo escribir la mesa en la SD");
        std::setvbuf(file.get(), buffer.data(), _IOFBF, buffer.size());
        Extract sink{file.get(), cancel, progress, unpacked, total};
        bool ok = mz_zip_reader_extract_to_callback(&input.zip, found->second, extractBytes, &sink, 0);
        if (std::fclose(file.release())) ok = false;
        if (cancel) throw std::runtime_error("Preparación cancelada");
        if (!ok)
            throw std::runtime_error("Archivo dañado al extraer la mesa");
        unpacked += stat.m_uncomp_size;
    }
}
}

Launch preparePinball(const fs::path &root, const Config &config, const Game &game,
                      const std::atomic<bool> &cancel, Progress progress, Status status) {
    const auto logPath = root / "pinball-prepare.log";
    writeText(logPath, "GameClub: preparación de pinball " + game.id + "\n");
    auto phase = [&](const std::string &text) {
        std::ofstream log(logPath, std::ios::app);
        log << text << '\n';
        log.flush();
        if (status) status(text);
    };
    if (!safeId(game.id))
        throw std::runtime_error("Mesa no válida");
    Launch result;
    result.core = root / "pinball/GameClubPinball.nro";
    if (!fs::is_regular_file(result.core))
        throw std::runtime_error("Instala el paquete del motor VPX/PinMAME para Switch en switch/gameclub/pinball");
    validateCore(result.core);
    phase("Consultando paquete de la mesa...");
    auto manifest = Json::parse(request(config, "/api/games/" + game.id + "/pinball", cancel).data);
    auto signature = manifest.at("signature").get<std::string>();
    auto table = manifest.at("table").get<std::string>();
    if (!safeId(signature) || !safeRelative(table) || table.find('/') != std::string::npos ||
        lower(fs::path(table).extension().string()) != ".vpx")
        throw std::runtime_error("Manifiesto de pinball no válido");
    const auto library = libraryRoot(root, config);
    const auto folder = library / "pinball" / game.id;
    const auto package = folder / "package.bin";
    phase("Descargando paquete de la mesa...");
    fetchFile(config, cancel, "/api/games/" + game.id + "/download", package,
              manifest.at("size").get<uint64_t>(), manifest.at("revision").get<std::string>(), progress);
    const auto cache = folder / signature;
    result.rom = cache / table;
    if (!fs::is_regular_file(cache / ".gameclub-pinball-ready") || !fs::is_regular_file(result.rom)) {
        const auto staging = folder / ("extract-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
        fs::create_directories(staging);
        try {
            phase("Extrayendo mesa y recursos...");
            if (manifest.value("raw_table", false))
                fs::copy_file(package, staging / table);
            else
                unpack(package, staging, manifest, cancel, progress);
            if (cancel) throw std::runtime_error("Preparación cancelada");
            checkTable(staging / table);
            writeText(staging / ".gameclub-pinball-ready", signature);
            if (fs::exists(cache)) {
                // Only our own cache can be replaced. Never remove an unrelated directory.
                if (!fs::is_regular_file(cache / ".gameclub-pinball-ready"))
                    throw std::runtime_error("La caché de la mesa necesita revisión");
                fs::remove_all(cache);
            }
            publishCache(staging, cache);
        } catch (...) {
            fs::remove_all(staging);
            throw;
        }
    }
    checkTable(result.rom);
    if (cancel) throw std::runtime_error("Preparación cancelada");
    phase("Preparando la configuración de PinMAME...");
    const auto prefs = library / "pinball-state" / game.id;
    for (const auto *name : {"nvram", "cfg", "hi"})
        fs::create_directories(prefs / name);
    result.config = prefs / "VPinballX.ini";
    if (!fs::exists(result.config))
        writeText(result.config, "[Player]\nPlayfieldWidth=1280\nPlayfieldHeight=720\nPlayfieldFSWidth=1280\nPlayfieldFSHeight=720\nPlayfieldFullScreen=1\nMaxTexDimension=1024\nMSAASamples=0\nFXAA=0\n\n[Backglass]\nBackglassOutput=0\n\n[Plugin.PinMAME]\nEnable=1\n");
    result.args = quoted(result.core.generic_string()) + " --gameclub-state " + quoted(prefs.generic_string()) +
                  " -PrefPath " + quoted(prefs.generic_string()) + " -Ini " + quoted(result.config.generic_string()) +
                  " -Play " + quoted(result.rom.generic_string());
    if (result.args.size() >= 4000)
        throw std::runtime_error("Ruta demasiado larga para abrir pinball");
    phase("Paquete preparado. Abriendo motor nativo...");
    std::ofstream log(logPath, std::ios::app);
    log << "Motor: " << result.core.generic_string() << "\nMesa: " << result.rom.generic_string() << '\n';
    return result;
}
}
