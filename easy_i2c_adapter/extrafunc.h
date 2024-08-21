#ifndef _EXTRAFUNC_HEADER_FILE_
#define _EXTRAFUNC_HEADER_FILE_

/***********************************
 * extrafunc.h
 * rev 1.0 - shabaz Jan 2021
 * *********************************/

#define LED_PIN 25

int led_setup(void); // sets LED pin as an output
int led_ctrl(int v); // turns LED on (v=1) or off (v=0)

#endif // _EXTRAFUNC_HEADER_FILE_
