cmake_minimum_required(VERSION 3.25)
project(GameClubPinball LANGUAGES C CXX)
set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 20)
set(PORT_ROOT "${CMAKE_SOURCE_DIR}/../../../switch-pinball")
get_filename_component(PORT_ROOT "${PORT_ROOT}" ABSOLUTE)
file(READ "${PORT_ROOT}/../client/pubspec.yaml" GAMECLUB_PUBSPEC)
string(REGEX MATCH "version: ([0-9]+\\.[0-9]+\\.[0-9]+)" _ "${GAMECLUB_PUBSPEC}")
set_source_files_properties("${PORT_ROOT}/src/entry.cpp" PROPERTIES
  COMPILE_DEFINITIONS GAMECLUB_PINBALL_VERSION="${CMAKE_MATCH_1}")
set(DEPS_ROOT "${CMAKE_SOURCE_DIR}/..")
set(PREFIX "${DEPS_ROOT}/prefix")
set(PLATFORM switch)
set(ARCH arm64)
set(VERSION_MAJOR 10)
set(VERSION_MINOR 8)
set(VERSION_REV 1)
include(make/CMakeLists_sources.txt)
add_library(glad STATIC third-party/include/glad/src/gl.c)
target_include_directories(glad PUBLIC third-party/include/glad/include)
add_executable(vpinball ${VPX_STANDALONE_SOURCES} "${PORT_ROOT}/src/entry.cpp" "${PORT_ROOT}/src/plugins.cpp" "${PORT_ROOT}/src/utc.cpp" "${PORT_ROOT}/src/input.cpp" "${PORT_ROOT}/src/posix.cpp")
set_target_properties(vpinball PROPERTIES OUTPUT_NAME GameClubPinball SUFFIX .elf)
target_compile_definitions(vpinball PRIVATE
  __STANDALONE__ __LIBWINEVBS__ __WINESRC__ WINE_UNICODE_NATIVE
  ENABLE_OPENGL SDL_MAIN_HANDLED FREEIMAGE_LIB
  "__forceinline=__attribute__((always_inline)) inline")
target_include_directories(vpinball PRIVATE
  "${PORT_ROOT}/include"
  "${PREFIX}/include"
  "${DEPS_ROOT}/libwinevbs/atl/include"
  "${DEPS_ROOT}/libwinevbs/atlmfc/include"
  "${DEPS_ROOT}/libwinevbs/wine/include"
  "${DEPS_ROOT}/freeimage/Source"
  "${CMAKE_SOURCE_DIR}/third-party/include"
  "${CMAKE_SOURCE_DIR}" src plugins)
target_precompile_headers(vpinball PRIVATE
  "$<$<COMPILE_LANGUAGE:CXX>:${CMAKE_SOURCE_DIR}/src/core/stdafx.h>")
set_source_files_properties("${PORT_ROOT}/src/entry.cpp" "${PORT_ROOT}/src/plugins.cpp"
  "${PORT_ROOT}/src/utc.cpp" "${PORT_ROOT}/src/input.cpp" PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
set_source_files_properties("${PORT_ROOT}/src/posix.cpp" PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
set_source_files_properties(third-party/include/tinyxml2/tinyxml2.cpp PROPERTIES SKIP_PRECOMPILE_HEADERS ON)
set_source_files_properties(third-party/include/imgui/imgui.cpp PROPERTIES
  SKIP_PRECOMPILE_HEADERS ON COMPILE_DEFINITIONS IMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS)
target_compile_options(vpinball PRIVATE -O2 -ffunction-sections -fdata-sections)
set_source_files_properties(src/core/Settings.cpp PROPERTIES COMPILE_OPTIONS -fno-tree-pta)
set(BUILD_SHARED OFF)
set(BUILD_STATIC ON)
include(make/CMakeLists_plugin_PinMAME.txt)
include(make/CMakeLists_plugin_B2S.txt)
include(make/CMakeLists_plugin_FlexDMD.txt)
foreach(plugin PinMAMEPlugin B2SPlugin FlexDMDPlugin)
  target_include_directories(${plugin} PRIVATE "${PREFIX}/include")
  target_compile_options(${plugin} PRIVATE -O2)
endforeach()
target_link_directories(vpinball PRIVATE "${PREFIX}/lib")
target_link_libraries(vpinball PRIVATE -Wl,--start-group
  PinMAMEPlugin B2SPlugin FlexDMDPlugin
  "${DEPS_ROOT}/pinmame-vpx-build/libpinmame.a"
  "${DEPS_ROOT}/winevbs-build/libwinevbs.a"
  "${DEPS_ROOT}/freeimage-build/libfreeimage.a"
  SDL3_image SDL3_ttf SDL3 glad
  avcodec avformat avutil swresample swscale ass fribidi dav1d
  freetype harfbuzz bz2 png jpeg webp z EGL glapi drm_nouveau nx m pthread
  -Wl,--end-group)
target_link_options(vpinball PRIVATE -Wl,--gc-sections "-Wl,-Map,${CMAKE_BINARY_DIR}/GameClubPinball.map")
