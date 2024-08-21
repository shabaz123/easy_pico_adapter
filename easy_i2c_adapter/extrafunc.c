/****************************************
 * extrafunc.c
 * rev 1.0 shabaz Jan 2021
 * **************************************/

#include "extrafunc.h"
#include "pico/stdlib.h"

int
led_setup(void)
{
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);
    return(0);
}

int
led_ctrl(int v)
{
    if (v) {
        gpio_put(LED_PIN, 1);
    } else {
        gpio_put(LED_PIN, 0);
    }
    return(0);
}
