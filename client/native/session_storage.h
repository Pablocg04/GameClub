#pragma once
#include <filesystem>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>

namespace gameclub {
// The native host runs MAME/NES/2600 only. Core-owned NVRAM, SRAM and states
// live in a fresh workspace, never in the previous session's save directory.
class SessionStorage {
 public:
  std::filesystem::path path;
  explicit SessionStorage(const std::filesystem::path& root) {
    const auto parent=root/"sessions";
    std::filesystem::create_directories(parent);
    std::random_device random;
    for(int attempt=0;attempt<100;++attempt) {
      auto candidate=parent/("session-"+std::to_string(random())+"-"+std::to_string(random()));
      if(std::filesystem::create_directory(candidate)){path=std::move(candidate);return;}
    }
    throw std::runtime_error("No se pudo preparar una sesión nueva");
  }
  SessionStorage(const SessionStorage&)=delete;
  SessionStorage& operator=(const SessionStorage&)=delete;
  ~SessionStorage() {
    std::error_code error;
    if(!path.empty())std::filesystem::remove_all(path,error);
  }
};
}
