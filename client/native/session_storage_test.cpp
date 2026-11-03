#include "session_storage.h"
#include <fstream>
#include <cstdio>
#include <cstdlib>

void check(bool value,const char* text){if(!value){std::fprintf(stderr,"%s\n",text);std::exit(1);}}
int main() {
  gameclub::SessionStorage fixture(std::filesystem::temp_directory_path());
  const auto root=fixture.path;
  std::ofstream(root/"battery.srm",std::ios::binary)<<"old battery";
  std::filesystem::path first;
  {
    gameclub::SessionStorage session(root);
    first=session.path;
    check(std::filesystem::is_empty(first),"La sesión leyó datos anteriores");
    std::ofstream(first/"game.nv")<<"new NVRAM";
    std::ofstream(first/"game.sta")<<"new state";
    gameclub::SessionStorage simultaneous(root);
    check(simultaneous.path!=first&&std::filesystem::is_empty(simultaneous.path),"Dos sesiones comparten progreso");
  }
  check(!std::filesystem::exists(first),"Se conservó la partida al salir");
  {
    gameclub::SessionStorage reopened(root);
    check(reopened.path!=first&&std::filesystem::is_empty(reopened.path),"Reabrir restauró la partida");
  }
  std::ifstream input(root/"battery.srm");std::string data;std::getline(input,data);
  check(data=="old battery","Se modificaron guardados anteriores");
  check(std::filesystem::is_empty(root/"sessions"),"La salida dejó archivos de partida");
  std::puts("Sesiones nuevas aisladas, salida sin partida y guardados antiguos ignorados.");
}
