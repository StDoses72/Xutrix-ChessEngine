cmake_minimum_required(VERSION 3.16)
project(xutrix_c C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(xutrix
    src/board.c
    src/eval.c
    src/main.c
    src/movegen.c
    src/nnue.c
    src/search.c
)

if (MSVC)
    target_compile_options(xutrix PRIVATE /O2 /W4)
else()
    target_compile_options(xutrix PRIVATE -O2 -Wall -Wextra -Wpedantic)
endif()
