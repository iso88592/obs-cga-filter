cmake_minimum_required(VERSION 3.16)
project(obs-cga-filter VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 17)

find_package(PkgConfig REQUIRED)
pkg_check_modules(OBS REQUIRED libobs)

add_library(obs-cga-filter MODULE
    src/cga-filter.c
)

target_include_directories(obs-cga-filter PRIVATE ${OBS_INCLUDE_DIRS})
target_link_libraries(obs-cga-filter PRIVATE ${OBS_LIBRARIES})
target_compile_options(obs-cga-filter PRIVATE ${OBS_CFLAGS_OTHER})

set_target_properties(obs-cga-filter PROPERTIES PREFIX "")

install(TARGETS obs-cga-filter
    LIBRARY DESTINATION obs-cga-filter/bin/64bit
)

install(DIRECTORY data/
    DESTINATION obs-cga-filter/data
)