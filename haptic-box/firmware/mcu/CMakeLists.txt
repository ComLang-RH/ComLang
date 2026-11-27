# ComLang box controller firmware.
#   simulated board (runs on the PC; the demo app talks to it):
#       cmake -S firmware/mcu -B build/mcu-sim && cmake --build build/mcu-sim
#   real board (Raspberry Pi Pico, needs the Pico SDK and arm-none-eabi-gcc):
#       cmake -S firmware/mcu -B build/mcu-rp2040 -DCOMLANG_TARGET=rp2040 -DPICO_SDK_PATH=...
#       cmake --build build/mcu-rp2040        -> comlang_mcu.uf2
cmake_minimum_required(VERSION 3.13)
set(COMLANG_TARGET "sim" CACHE STRING "sim or rp2040")
set(FW_SRC src/fw.c src/motion.c src/servo.c src/braille.c src/controls.c src/display.c src/link.c)

if(COMLANG_TARGET STREQUAL "rp2040")
  if(NOT PICO_SDK_PATH)
    set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
  endif()
  include(${PICO_SDK_PATH}/external/pico_sdk_import.cmake)
  project(comlang_mcu C CXX ASM)
  pico_sdk_init()
  add_executable(comlang_mcu ${FW_SRC} rp2040/hal_rp2040.c rp2040/main.c)
  target_include_directories(comlang_mcu PRIVATE src)
  target_compile_options(comlang_mcu PRIVATE -Wall -Wextra)
  target_link_libraries(comlang_mcu pico_stdlib hardware_spi hardware_pwm hardware_watchdog hardware_sync)
  pico_enable_stdio_usb(comlang_mcu 1)
  pico_enable_stdio_uart(comlang_mcu 0)
  pico_add_extra_outputs(comlang_mcu)
else()
  project(comlang_mcu C)
  add_executable(comlang_sim ${FW_SRC} sim/hal_sim.c)
  target_include_directories(comlang_sim PRIVATE src)
  target_compile_options(comlang_sim PRIVATE -std=c11 -Wall -Wextra -Werror -O2)
  target_link_libraries(comlang_sim m)
endif()
