#include "glfx_parser.hpp"
#include "json.hpp"
#include <iostream>
#include <map>
#include <vector>

namespace fs = std::filesystem;
using Sections = std::map<std::string, std::string>;
static int checks = 0;
static void check(bool ok, const char *why) {
    ++checks;
    if (!ok) throw std::runtime_error(why);
}
static std::string read(const fs::path &path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("Missing shader fixture");
    return {std::istreambuf_iterator<char>(file), {}};
}
static void write(const fs::path &path, const std::string &raw) {
    fs::create_directories(path.parent_path());
    std::ofstream file(path, std::ios::binary); file << raw;
    if (!file) throw std::runtime_error("Writing shader fixture failed");
}
int main(int argc, char **argv) {
    try {
        if (argc != 3) throw std::runtime_error("Expected shader source and test directory");
        const fs::path source = argv[1], fixture = argv[2];
        const auto lf = fixture / "lf", crlf = fixture / "crlf";
        std::vector<std::string> names;
        for (const auto &entry : fs::directory_iterator(source)) {
            if (!entry.is_regular_file()) continue;
            auto raw = read(entry.path());
            for (size_t at = 0; (at = raw.find("\r\n", at)) != std::string::npos;) raw.erase(at, 1);
            if (raw.starts_with("\xef\xbb\xbf")) raw.erase(0, 3);
            write(lf / entry.path().filename(), raw);
            std::string windows;
            for (char byte : raw) { if (byte == '\n') windows += '\r'; windows += byte; }
            write(crlf / entry.path().filename(), windows);
            if (entry.path().extension() == ".glfx") names.push_back(entry.path().filename().string());
        }
        const std::string defines = "#define GLSL\n\n#define USE_GEOMETRY_SHADER 0\n#define N_EYES 1\n";
        size_t totalTechniques = 0;
        for (const auto &name : names) {
            Sections unixSource, windowsSource;
            std::string error;
            check(gameclub::parseGlfx(lf, name, 0, unixSource, "GLOBAL", defines, error), "LF parse failed");
            check(gameclub::parseGlfx(crlf, name, 0, windowsSource, "GLOBAL", defines, error), "CRLF parse failed");
            check(unixSource == windowsSource, "Different shader sections with CRLF");
            const auto count = gameclub::glfxTechniqueCount(windowsSource);
            check(count > 0, "Shader has no techniques");
            check(windowsSource.at("GLOBAL").find("#define GLSL") != std::string::npos, "Missing shader defines");
            std::istringstream lines(windowsSource.at("TECHNIQUES"));
            bool functionsFound = true;
            for (std::string line; std::getline(lines, line);) {
                if (line.empty() || line.starts_with("//") || std::count(line.begin(), line.end(), ':') < 3) continue;
                std::istringstream columns(line);
                for (int i = 0; std::getline(columns, line, ':'); ++i) {
                    if (i < 2 || line.empty()) continue;
                    const auto function = line.substr(0, line.find('('));
                    const auto found = windowsSource.find(function);
                    functionsFound = functionsFound && found != windowsSource.end() && !found->second.empty();
                }
            }
            check(functionsFound, "Shader technique references missing function");
            // Legacy comments contain Latin-1 bytes; diagnostic JSON replaces
            // those bytes without changing the parser's byte-for-byte checks.
            write(fixture / "sections" / (name + ".json"), nlohmann::json(windowsSource).dump(
                2, ' ', false, nlohmann::json::error_handler_t::replace));
            totalTechniques += count;
        }
        check(names.size() >= 9, "Shader set is incomplete");
        write(crlf / "UIShader.glfx", "\xef\xbb\xbf" + read(crlf / "UIShader.glfx"));
        Sections bom, plain; std::string error;
        check(gameclub::parseGlfx(crlf, "UIShader.glfx", 0, bom, "GLOBAL", defines, error) &&
              gameclub::parseGlfx(lf, "UIShader.glfx", 0, plain, "GLOBAL", defines, error) && bom == plain, "BOM parse failed");
        write(lf / "bad.glfx", "#include \"missing.fxh\"\n");
        Sections invalid;
        check(!gameclub::parseGlfx(lf, "bad.glfx", 0, invalid, "GLOBAL", defines, error), "Missing include accepted");
        write(lf / "bad.glfx", "#include \"bad.glfx\"\n");
        check(!gameclub::parseGlfx(lf, "bad.glfx", 0, invalid, "GLOBAL", defines, error), "Include recursion accepted");
        write(lf / "bad.glfx", "#include invalid\n");
        check(!gameclub::parseGlfx(lf, "bad.glfx", 0, invalid, "GLOBAL", defines, error), "Malformed include accepted");
        check(gameclub::glfxTechniqueCount(Sections{{"GLOBAL", "void main() {}"}}) == 0, "Missing technique not detected");
        const auto adapted = gameclub::preprocessGlfx430("#version 450 core\nvoid main() {}\n");
        check(adapted.starts_with("#version 430 core\n"), "GLSL 450 not adapted to 430");
        check(adapted.find("#version 450") == std::string::npos, "GLSL 450 leaked to driver");
        check(adapted.find("#define SHADER_STANDALONE") != std::string::npos, "Standalone define lost");
        check(gameclub::preprocessGlfx430("#version 400\n").starts_with("#version 400\n"), "GLSL 400 changed");
        check(gameclub::preprocessGlfx430("#version 430\n").starts_with("#version 430\n"), "GLSL 430 changed");
        check(gameclub::preprocessGlfx430("#version 450 core\r\nvoid main() {}\r\n") == adapted, "CRLF GLSL adaptation changed");
        std::cout << checks << " comprobaciones GLFX superadas: " << names.size() << " archivos, " << totalTechniques
                  << " técnicas; LF/CRLF/BOM e includes. Sin compilar GPU en esta prueba.\n";
        return 0;
    } catch (const std::exception &e) { std::cerr << "GLFX: " << e.what() << '\n'; return 1; }
}
