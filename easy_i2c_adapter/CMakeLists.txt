cmake_minimum_required(VERSION 3.13)
include(pico_sdk_import.cmake)

set(projname "easy_i2c_adapter")
project(${projname})

pico_sdk_init()

if (TARGET tinyusb_device)
        add_executable(${projname}
        main.c
        extrafunc.c
        )

        target_link_libraries(${projname}
                pico_stdlib
                hardware_i2c
                )

        # adjust to enable stdio via usb, or uart
        pico_enable_stdio_usb(${projname} 1)
        pico_enable_stdio_uart(${projname} 0)

        pico_add_extra_outputs(${projname})
elseif(PICO_ON_DEVICE)
        message("Skipping build because TinyUSB submodule is not initialized in the SDK")
endif()

