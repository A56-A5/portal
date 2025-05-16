cmake_minimum_required(VERSION 3.10)
project(AudioStreamer)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# OS-specific logic
if(WIN32)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
    set(PORTAUDIO_LIB portaudio ws2_32)
else()
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(PORTAUDIO REQUIRED portaudio-2.0)
    include_directories(${PORTAUDIO_INCLUDE_DIRS})
    link_directories(${PORTAUDIO_LIBRARY_DIRS})
    set(PORTAUDIO_LIB ${PORTAUDIO_LIBRARIES})
endif()

# CLIENT TARGETS
add_executable(client_linux client/client_linux.cpp)
if(UNIX)
    target_link_libraries(client_linux pthread)
endif()

add_executable(client_windows client/client_windows.cpp)
target_link_libraries(client_windows ${PORTAUDIO_LIB})

# SERVER TARGETS
add_executable(server_linux server/server_linux.cpp)
target_link_libraries(server_linux ${PORTAUDIO_LIB})

add_executable(server_windows server/server_windows.cpp)
target_link_libraries(server_windows ${PORTAUDIO_LIB})

# GUI TARGET
add_executable(audio_gui gui/audio_gui.cpp)

# Install target (optional)
install(TARGETS client_linux client_windows server_linux server_windows audio_gui
        RUNTIME DESTINATION bin)
