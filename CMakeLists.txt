cmake_minimum_required(VERSION 3.16)
project(obs-cga-filter VERSION 0.1.0)

set(CMAKE_C_STANDARD 17)

find_package(libobs REQUIRED)

add_library(obs-cga-filter MODULE
    src/cga-filter.c
)

target_link_libraries(obs-cga-filter PRIVATE OBS::libobs)

# OBS plugins have no "lib" prefix
set_target_properties(obs-cga-filter PROPERTIES PREFIX "")

install(TARGETS obs-cga-filter
    LIBRARY DESTINATION obs-cga-filter/bin/64bit
)

install(DIRECTORY data/
    DESTINATION obs-cga-filter/data
)
