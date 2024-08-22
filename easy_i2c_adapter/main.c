/******************************
 * main.c
 * rev 1.0 Jan 2021 shabaz
 * ****************************/

#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "extrafunc.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"

// definitions
#define I2C_PORT_SELECTED 1
#define I2C_SDA_PIN 14
#define I2C_SCL_PIN 15
#define MODE_ASCII 0
#define MODE_BIN 1
#define TOKEN_RESULT_ERROR 0
#define TOKEN_RESULT_OK 1
#define TOKEN_RESULT_LINE_COMPLETE 2
#define M2M_RESPONSE_OK_CHAR '.'
#define M2M_RESPONSE_CONTINUE_CHAR '&'
#define M2M_RESPONSE_ERR_CHAR 'X'
#define M2M_RESPONSE_PROT_ERR_CHAR '~'
#define TOKEN_PROGRESS_NONE 0
#define TOKEN_PROGRESS_SEND 1
#define TOKEN_PROGRESS_RECV 2
#define COL_RED printf("\033[31m")
#define COL_GREEN printf("\033[32m")
#define COL_YELLOW printf("\033[33m")
#define COL_BLUE printf("\033[34m")
#define COL_MAGENTA printf("\033[35m")
#define COL_CYAN printf("\033[36m")
#define COL_RESET printf("\033[0m")

// constants
const uint8_t EOL_BIN_MAGIC[] = {0xBA, 0xDC, 0x0F, 0xFE, 0xE0, 0x0F, 0xF0, 0x0D}; // BADC0FFEE0DDF00D

// global variables
i2c_inst_t *i2c_port;
uint8_t uart_buffer[305];
uint16_t uart_buffer_index = 0;
uint8_t input_mode = MODE_ASCII;
uint8_t m2m_resp = 0;
uint8_t do_echo = 1;
uint8_t i2c_addr = 0x00;
int expected_num = 0;
uint8_t byte_buffer[256];
uint8_t byte_buffer_index = 0;
uint8_t token_progress = TOKEN_PROGRESS_NONE;
uint8_t do_repeated_start = 0;
uint8_t led_hold_off = 0;
uint8_t led_hold_on = 0;
uint8_t led_counter = 0;
uint8_t led_counter_default = 0;

/************* functions ***************/

void i2c_setup(void) {
    if (I2C_PORT_SELECTED == 0) {
        i2c_port = &i2c0_inst;
    } else {
        i2c_port = &i2c1_inst;
    }
    i2c_init(i2c_port, 100 * 1000);
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);
}

// print_buf_hex prints a buffer in hex format, up to 304 bytes
// 000: 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F : 0123456789ABCDEF
void
print_buf_hex(uint8_t *buf, uint16_t len) {
    uint16_t i, j;
    uint8_t c;
    uint8_t index = 0;

    for (i = 0; i < len; i += 16) {
        COL_BLUE;
        printf("%03d: ", index);
        COL_CYAN;
        for (j = 0; j < 16; j++) {
            if (i + j < len) {
                printf("%02X ", buf[i + j]);
            } else {
                printf("   ");
            }
        }
        COL_BLUE;
        printf(": ");
        COL_GREEN;
        for (j = 0; j < 16; j++) {
            if (i + j < len) {
                c = buf[i + j];
                if ((c < 32) || (c > 126)) {
                    printf(".");
                } else {
                    printf("%c", c);
                }
            } else {
                printf(" ");
            }
        }
        printf("\n");
        index += 16;
    }
    COL_RESET;
}

// print the buffer as hex bytes, 16 per line, each line ending with '&'.
// remote side should respond with '&' to continue, or 'X' to abort
void print_buf_m2m_ascii(uint8_t *buf, uint16_t len) {
    uint16_t i;
    char ch;
    for (i = 0; i < len; i++) {
        printf("%02X ", buf[i]);
        if ((i % 16) == 15) {
            putchar(M2M_RESPONSE_CONTINUE_CHAR);
            //wait for a response for up to 1 second
            ch = getchar_timeout_us(1E6);
            if (ch == M2M_RESPONSE_ERR_CHAR) { // PC wishes to abort
                putchar(M2M_RESPONSE_OK_CHAR);
                return;
            }
            if (ch != M2M_RESPONSE_CONTINUE_CHAR) {
                // unexpected message, or timeout. Abort with error!
                putchar(M2M_RESPONSE_ERR_CHAR);
                return;
            }
        }
    }
    putchar(M2M_RESPONSE_OK_CHAR);
}

// print the buffer as raw bytes, 64 per line, each line ending with '&'.
// remote side should respond with '&' to continue, or 'X' to abort
void print_buf_m2m_bin(uint8_t *buf, uint16_t len) {
    uint16_t i;
    char ch;
    for (i = 0; i < len; i++) {
        putchar(buf[i]);
        if ((i % 64) == 63) {
            putchar(M2M_RESPONSE_CONTINUE_CHAR);
            //wait for a response for up to 1 second
            ch = getchar_timeout_us(1E6);
            if (ch == M2M_RESPONSE_ERR_CHAR) { // PC wishes to abort
                putchar(M2M_RESPONSE_OK_CHAR);
                return;
            }
            if (ch != M2M_RESPONSE_CONTINUE_CHAR) {
                // unexpected message, or timeout. Abort with error!
                putchar(M2M_RESPONSE_ERR_CHAR);
                return;
            }
        }
    }
    putchar(M2M_RESPONSE_OK_CHAR);
}

// used only in bitbang mode!
void pullup_gpio(uint8_t pin) {
    // set the pin to be an input, with pull-up enabled
    gpio_set_dir(pin, GPIO_IN);
    gpio_pull_up(pin);
}
// used only in bitbang mode!
void pulldown_gpio(uint8_t pin) {
    // set the pin to be an output, set low
    gpio_set_dir(pin, GPIO_OUT);
    gpio_put(pin, 0);
}
// this function will switch into GPIO mode and bitbang the I2C address to see if the ACK is received
// then it switches back to I2C mode
// returns 1 if ACK received, 0 otherwise
int bitbang_i2c_addr(unsigned int val) {
    uint8_t ack;
    uint8_t i;
    uint8_t addr = (uint8_t) val;
    gpio_init(I2C_SDA_PIN);
    gpio_init(I2C_SCL_PIN);
    pullup_gpio(I2C_SDA_PIN);
    pullup_gpio(I2C_SCL_PIN);
    // perform the I2C start condition
    pulldown_gpio(I2C_SDA_PIN);
    sleep_us(5);
    pulldown_gpio(I2C_SCL_PIN);
    sleep_us(5);
    addr <<= 1; // left-shift the address by 1 bit
    addr |= 1; // we want to do an I2C read
    // send the address
    for (i=0; i<8; i++) {
        if (addr & 0x80) {
            pullup_gpio(I2C_SDA_PIN);
        } else {
            pulldown_gpio(I2C_SDA_PIN);
        }
        sleep_us(5);
        pullup_gpio(I2C_SCL_PIN);
        sleep_us(5);
        pulldown_gpio(I2C_SCL_PIN);
        sleep_us(5);
        addr <<= 1;
    }
    // now read the ACK bit
    pullup_gpio(I2C_SDA_PIN);
    sleep_us(5);
    pullup_gpio(I2C_SCL_PIN);
    sleep_us(5);
    ack = gpio_get(I2C_SDA_PIN);
    pulldown_gpio(I2C_SCL_PIN);
    sleep_us(5);
    // now release the I2C bus
    pullup_gpio(I2C_SCL_PIN);
    sleep_us(5);
    pullup_gpio(I2C_SDA_PIN);
    sleep_us(5);
    // convert back to I2C mode
    i2c_init(i2c_port, 100 * 1000);
    gpio_set_function(I2C_SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA_PIN);
    gpio_pull_up(I2C_SCL_PIN);
    if (ack==0) { // held low means the device is present
        return 1;
        } else {
        return 0;
    }
}

// scan_uart_input fill the uart_buffer until a newline is received
// returns number of bytes if a newline is received, 0 otherwise
int
scan_uart_input(void) {
    int c;
    uint16_t num_bytes;
    c = getchar_timeout_us(1000);
    if (c == PICO_ERROR_TIMEOUT) {
        return 0;
    }
    // ASCII mode
    if (input_mode == MODE_ASCII) {
        if ((c == 8) || (c==127)) { // backspace pressed
            if (uart_buffer_index > 0) {
                uart_buffer_index--;
                if (do_echo) {
                    putchar(8);
                    putchar(' ');
                    putchar(8);
                }
            }
            return 0;
        }
        if (c == 13) {
            // add a space to simplify token parsing
            uart_buffer[uart_buffer_index++] = ' ';
            uart_buffer[uart_buffer_index] = 0;
            num_bytes = uart_buffer_index;
            uart_buffer_index = 0;
            if (m2m_resp) {
                // don't send anything
            } else {
                if (do_echo) {
                    printf("\n");
                }
            }
            return num_bytes;
        }
        uart_buffer[uart_buffer_index] = (uint8_t) c;
        if (do_echo) {
            if (m2m_resp) {
                // don't echo
            } else {
                putchar(c);
            }
        }
        uart_buffer_index++;
        if (uart_buffer_index >= 300) {
            uart_buffer_index = 0;
        }
        return 0;
    }
    // binary mode
    // we keep reading bytes until we find the magic number
    uart_buffer[uart_buffer_index] = (uint8_t) c;
    uart_buffer_index++;
    if (uart_buffer_index < 8) {
        return 0;
    }
    if (memcmp(&uart_buffer[uart_buffer_index-8], EOL_BIN_MAGIC, 8) == 0) {
        num_bytes = uart_buffer_index - 8;
        uart_buffer_index = 0;
        print_buf_hex(uart_buffer, num_bytes);
        return num_bytes;
    }
    return(0);
}

int decode_token(char *token) {
    unsigned int val;
    int retval = 0;
    if (strcmp(token, "device?") == 0) {
        printf("easy_adapter\n\r");
        led_hold_off = 1;
        // reset any state and variables
        token_progress = TOKEN_PROGRESS_NONE;
        expected_num = 0;
        byte_buffer_index = 0;
        do_repeated_start = 0;
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strcmp(token, "bin") == 0) {
        input_mode = MODE_BIN;
        if(m2m_resp) {
            putchar(M2M_RESPONSE_OK_CHAR);
        } else {
            printf("Switching to binary mode\n");
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strncmp(token, "bytes:", 6) == 0) {
        sscanf(token, "bytes:%d", &expected_num);
        if(m2m_resp) {
            putchar(M2M_RESPONSE_OK_CHAR);
        } else {
            COL_BLUE;
            printf("Expecting %d bytes\n", expected_num);
            COL_RESET;
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strcmp(token, "send+hold") == 0) { // perform send, but hold the bus for a later repeated start
        if (expected_num == 0) {
            COL_RED;
            printf("No bytes expected\n");
            COL_RESET;
            return TOKEN_RESULT_LINE_COMPLETE;
        }
        // consider remainder tokens on the line to be bytes for the send operation
        byte_buffer_index = 0;
        token_progress = TOKEN_PROGRESS_SEND;
        do_repeated_start = 1;
        return TOKEN_RESULT_OK;
    }
    if (strncmp(token, "tryaddr:", 8) == 0) {
        if (strncmp(token, "tryaddr:0x", 10) == 0) {
            // get i2c_addr in hex
            sscanf(token, "tryaddr:0x%02X", &val);
        } else {
            // get i2c_addr in decimal
            sscanf(token, "tryaddr:%d", &val);
        }
        retval = bitbang_i2c_addr(val);
        if(m2m_resp) {
            if (input_mode == MODE_ASCII) {
                if (retval == 0) {
                    putchar(M2M_RESPONSE_PROT_ERR_CHAR);
                } else {
                    putchar(M2M_RESPONSE_OK_CHAR);
                }
            } else {
                // binary mode, todo
            }
        } else {
            if (retval == 0) {
                COL_RED;
                printf("Protocol error! Does the I2C device exist?\n");
                COL_RESET;
            } else {
                COL_BLUE;
                printf("Device found at address 0x%02X\n", val);
                COL_RESET;
            }
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strcmp(token, "send") == 0) {
        if (expected_num == 0) {
            COL_RED;
            printf("No bytes expected\n");
            COL_RESET;
            return TOKEN_RESULT_LINE_COMPLETE;
        }
        // consider remainder tokens on the line to be bytes for the send operation
        byte_buffer_index = 0;
        token_progress = TOKEN_PROGRESS_SEND;
        do_repeated_start = 0;
        return TOKEN_RESULT_OK;
    }
    if (strcmp(token, "recv") == 0) {
        if (expected_num == 0) {
            COL_RED;
            printf("No bytes expected\n");
            COL_RESET;
            return TOKEN_RESULT_LINE_COMPLETE;
        }
        byte_buffer_index = 0;
        retval = i2c_read_blocking(i2c_port, i2c_addr, byte_buffer, expected_num, false);
        if(m2m_resp) {
            if (input_mode == MODE_ASCII) {
                if (retval == PICO_ERROR_GENERIC) {
                    putchar(M2M_RESPONSE_PROT_ERR_CHAR);
                } else {
                    print_buf_m2m_ascii(byte_buffer, expected_num);
                }
            } else {
                print_buf_m2m_bin(byte_buffer, expected_num);
            }
        } else {
            if (retval == PICO_ERROR_GENERIC) {
                COL_RED;
                printf("Protocol error reading bytes! Does the I2C device exist?\n");
                COL_RESET;
            } else {
                print_buf_hex(byte_buffer, expected_num);
            }
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strncmp(token, "m2m_resp:", 9) == 0) {
        if (token[9] == '1') {
            m2m_resp = 1;
            putchar(M2M_RESPONSE_OK_CHAR);
        } else {
            m2m_resp = 0;
            printf("M2M response off\n");
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strncmp(token, "addr:0x", 7) == 0) {
        // get i2c_addr
        sscanf(token, "addr:0x%02X", &val);
        i2c_addr = val;
        if(m2m_resp) {
            putchar(M2M_RESPONSE_OK_CHAR);
        } else {
            COL_BLUE;
            printf("I2C address set to 0x%02X\n", i2c_addr);
            COL_RESET;
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    } else if (strncmp(token, "addr:", 5) == 0) {
        // get i2c_addr in decimal
        sscanf(token, "addr:%d", &val);
        i2c_addr = val;
        if(m2m_resp) {
            putchar(M2M_RESPONSE_OK_CHAR);
        } else {
            COL_BLUE;
            printf("I2C address set to 0x%02X\n", i2c_addr);
            COL_RESET;
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (strcmp(token, "noecho") == 0) {
        do_echo = 0;
        COL_BLUE;
        printf("Echo off\n");
        COL_RESET;
        return 0;
    }
    if (strcmp(token, "end_tok") == 0) {
        if (token_progress == TOKEN_PROGRESS_SEND) {
            // we are still expecting more bytes, on the next line
            if (m2m_resp) {
                putchar(M2M_RESPONSE_CONTINUE_CHAR);
            } else {
                COL_BLUE;
                printf("Remaining bytes expected: %d\n", expected_num - byte_buffer_index);
                COL_RESET;
            }
        }
        return TOKEN_RESULT_LINE_COMPLETE;
    }
    if (token_progress == TOKEN_PROGRESS_SEND) {
        if (strlen(token) != 2) {
            COL_RED;
            printf("Invalid byte: %s\n", token);
            COL_RESET;
            return TOKEN_RESULT_LINE_COMPLETE;
        }
        sscanf(token, "%02X", &val);
        byte_buffer[byte_buffer_index] = val;
        byte_buffer_index++;
        if (byte_buffer_index == expected_num) {
            // send the bytes
            if (m2m_resp==0) {
                COL_BLUE;
                printf("Sending %d bytes\n", expected_num);
                COL_RESET;
                print_buf_hex(byte_buffer, expected_num);
            }
            if (do_repeated_start) {
                retval = i2c_write_blocking(i2c_port, i2c_addr, byte_buffer, expected_num, true);
            } else {
                retval = i2c_write_blocking(i2c_port, i2c_addr, byte_buffer, expected_num, false);
            }
            byte_buffer_index = 0;
            expected_num = 0;
            do_repeated_start = 0;
            token_progress = TOKEN_PROGRESS_NONE;
            if (retval == PICO_ERROR_GENERIC) {
                if (m2m_resp) {
                    putchar(M2M_RESPONSE_PROT_ERR_CHAR);
                } else {
                    COL_RED;
                    printf("Protocol error sending bytes! Does the I2C device exist?\n");
                    COL_RESET;
                }
                return TOKEN_RESULT_LINE_COMPLETE;
            }
            if (m2m_resp) {
                putchar(M2M_RESPONSE_OK_CHAR);
            }
            return TOKEN_RESULT_LINE_COMPLETE;
        }
        return TOKEN_RESULT_OK; // continue reading tokens on the send line
    }
    // done
    if (m2m_resp) {
        putchar(M2M_RESPONSE_ERR_CHAR);
        return TOKEN_RESULT_LINE_COMPLETE;
    } else {
        COL_RED;
        printf("Unknown command: %s\n", token);
        COL_RESET;
        return TOKEN_RESULT_LINE_COMPLETE;
    }
}

// if in ASCII mode, parse each space-separated token
int process_line(uint8_t *buf, uint16_t len) {
    int res;
    char token[20];
    uint16_t i = 0;
    uint16_t j = 0;
    if (len == 0) {
        return TOKEN_RESULT_ERROR;
    }
    while (i < len) {
        if (buf[i] == ' ') {
            token[j] = 0;
            //printf("token: %s\n", token);
            res = decode_token(token);
            if (res == TOKEN_RESULT_LINE_COMPLETE) {
                return TOKEN_RESULT_LINE_COMPLETE;
            }
            j = 0;
        } else {
            token[j] = buf[i];
            j++;
        }
        i++;
    }
    res = decode_token("end_tok");
}

int
main(void)
{
    int numbytes;
    stdio_init_all();
    sleep_ms(3000);
    led_setup(); // initialize LED pin to be an output
    i2c_setup(); // configures the I2C pins accordingly

    while (1) {
        numbytes = scan_uart_input();
        if (numbytes > 0) {
            process_line(uart_buffer, numbytes);
        }

        if (led_hold_off) {
            if (led_counter <= 0) {
                led_counter = 20;
                led_ctrl(0);
            }
            led_counter--;
            sleep_ms(20);
            if (led_counter == 0) {
                led_hold_off = 0;
            }
        } else if (led_hold_on) {
            if (led_counter <= 0) {
                led_counter = 20;
                led_ctrl(1);
            }
            led_counter--;
            sleep_ms(20);
            if (led_counter == 0) {
                led_hold_on = 0;
            }
        } else {
            if (led_counter_default<=0) {
                led_ctrl(1);    // turn LED on
                led_counter_default = 30;
            } else {
                led_counter_default--;
                if (led_counter_default==28) {
                    led_ctrl(0);    // turn LED off
                }
            }
        }
        sleep_ms(1);
    }
}
