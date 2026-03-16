cmake_minimum_required(VERSION 4.1)
project(pi_top)

set(CMAKE_CXX_STANDARD 14)

add_executable(pi_top
        core_engine.cpp
        hardware_engine.cpp)
