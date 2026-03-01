cmake_minimum_required(VERSION 3.16)
project(obs-cga-filter VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 17)

add_library(obs-cga-filter MODULE
    src/cga-filter.c
)

if(DEFINED OBS_INCLUDE_DIR AND DEFINED OBS_LIB)
    # Windows CI: headers + import library supplied manually
    target_include_directories(obs-cga-filter PRIVATE "${OBS_INCLUDE_DIR}")
    target_link_libraries(obs-cga-filter PRIVATE "${OBS_LIB}")
else()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(OBS REQUIRED libobs)
    target_include_directories(obs-cga-filter PRIVATE ${OBS_INCLUDE_DIRS})
    target_link_libraries(obs-cga-filter PRIVATE ${OBS_LIBRARIES})
    target_compile_options(obs-cga-filter PRIVATE ${OBS_CFLAGS_OTHER})
endif()

set_target_properties(obs-cga-filter PROPERTIES PREFIX "")

install(TARGETS obs-cga-filter
    LIBRARY DESTINATION obs-cga-filter/bin/64bit
)

install(DIRECTORY data/
    DESTINATION obs-cga-filter/data
)