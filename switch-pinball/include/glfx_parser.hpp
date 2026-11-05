#pragma once
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace gameclub {
// Read in binary mode so behavior is identical on Windows and Horizon.
// Section names and entry points must never retain a CR from a CRLF file.
template<class Sections>
bool parseGlfx(const std::filesystem::path &root, const std::string &name, int level,
               Sections &values, const std::string &parent, const std::string &defines, std::string &error) {
    if (level > 16) { error = "Shader include recursion: " + name; return false; }
    std::ifstream input(root / name, std::ios::binary);
    if (!input) { error = "Shader file not found: " + name; return false; }
    auto previous = values.find(parent);
    std::string mode = parent, text = previous == values.end() ? std::string() : previous->second;
    size_t number = 0;
    for (std::string line; std::getline(input, line);) {
        ++number;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (number == 1 && line.starts_with("\xef\xbb\xbf")) line.erase(0, 3);
        if (line.starts_with("////")) {
            const auto next = line.substr(4);
            if (next == "DEFINES") text += defines;
            else if (next != mode) {
                values[mode] = text;
                previous = values.find(next);
                text = previous == values.end() ? std::string() : previous->second;
                mode = next;
            }
        } else if (line.starts_with("#include ")) {
            const auto start = line.find('"', 8), end = line.find('"', start == std::string::npos ? 8 : start + 1);
            if (start == std::string::npos || end == std::string::npos || end <= start) {
                error = name + ':' + std::to_string(number) + ": invalid shader include";
                return false;
            }
            values[mode] = text;
            if (!parseGlfx(root, line.substr(start + 1, end - start - 1), level + 1, values, mode, defines, error)) return false;
            text = values[mode];
        } else text += line + '\n';
    }
    if (input.bad()) { error = "Shader read failed: " + name; return false; }
    values[mode] = std::move(text);
    return true;
}

template<class Sections> size_t glfxTechniqueCount(const Sections &values) {
    const auto found = values.find("TECHNIQUES");
    if (found == values.end()) return 0;
    std::istringstream lines(found->second);
    size_t count = 0;
    for (std::string line; std::getline(lines, line);)
        if (!line.empty() && !line.starts_with("//") && std::count(line.begin(), line.end(), ':') >= 3) ++count;
    return count;
}
}
