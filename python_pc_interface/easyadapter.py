# Python module for interfacing via serial to an I2C adapter
# requires pyserial
# rev 1.1 - shabaz - feb 2025 - added known I2C addresses

import serial  # Note: this is the pyserial module, NOT the serial module
from serial.tools import list_ports
from array import *
import time
import sys

class EasyAdapter:
    def __init__(self):
        self.txterm = b"\r"
        self.adapter_port = None
        self.cmd_wait_period = 500
        self.dbg_print = False

    # sends a command and returns the serial buffer result
    def send_command(self, cmd):
        if self.adapter_port is None:
            print("No easy_adapter selected. Call find_device() first")
            return
        ser = serial.Serial(self.adapter_port, 115200, timeout=0.2)
        if self.dbg_print:
            print(f"dbg send_command: {cmd}")
        ser.write(cmd.encode() + self.txterm)
        buffer = bytes()
        now = time.time_ns() // 1000000
        while ((time.time_ns() // 1000000) - now) < self.cmd_wait_period:
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
        ser.close()
        return buffer
    
    # sends a command and decodes the response (only use this function in m2m mode)
    # returns 1 if '.' is received, 2 if '&' is received,
    # returns 3 if '~' (protocol error) received, 0 for general error
    def send_and_confirm(self, cmd, wait_period=-1):
        if self.adapter_port is None:
            print("No easy_adapter selected. Call find_device() first")
            return
        if wait_period < 0:
            wait_period = self.cmd_wait_period
        ser = serial.Serial(self.adapter_port, 115200, timeout=0.2)
        if self.dbg_print:
            print(f"dbg send_and_confirm: {cmd}")
        ser.write(cmd.encode() + self.txterm)
        buffer = bytes()
        resp_found = 0
        now = time.time_ns() // 1000000
        while ((time.time_ns() // 1000000) - now) < wait_period:
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                if b"." in buffer:
                    resp_found = 1
                    break
                if b"&" in buffer:
                    resp_found = 2
                    break
                if b"~" in buffer:
                    resp_found = 3
                    break
        ser.close()
        if resp_found == 0:
            print(f"Error, sent '{cmd}' but received '{buffer}'")
        return resp_found
    
    # finds the easy_adapter device by searching available COM ports.
    # this function is called automatically by init() so the user doesn't have to call it
    def find_device(self, board=0):
        perm_error = 0
        ports = list_ports.comports()
        for port in ports:
            # try to see if port can be opened
            try:
                ser = serial.Serial(port.device, 115200, timeout=0.2)
                ser.write(self.txterm + b"device?" + self.txterm)
                found = 0
                buffer = bytes()
                now = time.time_ns() // 1000000
                while ((time.time_ns() // 1000000) - now) < self.cmd_wait_period:
                    if ser.in_waiting > 0:
                        buffer += ser.read(ser.in_waiting)
                if b"easy_adapter_" + str(board).encode() in buffer:
                # if b"easy_adapter" in buffer:
                    found = 1
                if found == 1:
                    print(f"Found easy_adapter_{board} at port {port.device}")
                    self.adapter_port = port.device
                    return port.device
                else:
                    ser.close()
            except serial.SerialException as e:
                if "PermissionError" in str(e):
                    perm_error = 1
                pass
            except Exception as e:
                print(f"Error: {e}")
                pass
        if perm_error == 1:
            print("Permission error. Close any serial console that may be using the port")
            print("Try using sudo if you're using Linux")
        else:
            print(f"No easy_adapter_{board} device found")
        return None
    
    # enters or exits M2M mode, 1 for entering the mode, 0 for exiting
    def m2m_mode(self, val):
        cmd = f"m2m_resp:{val}"
        buffer = self.send_command(cmd)
        if val == 1:
            if b"." not in buffer:
                print(f"Error entering M2M mode")
        else:
            if b"M2M response off" not in buffer:
                print(f"Error exiting M2M mode")
    
    # tries an I2C address, returns True if the address is found, False otherwise
    def i2c_try_address(self, addr):
        cmd = f"tryaddr:0x{addr:02x}"
        result = self.send_and_confirm(cmd)
        if result == 1:
            return True
        else:
            return False
    
    # sends an I2C write command to the adapter
    # addr: I2C address
    # byte1: first byte to send
    # data: list of remainder bytes to send
    # hold: 1 to hold the bus after sending the data (i.e. for a repeated start)
    # Note that the first byte is sent separately from the rest of the data,
    # to simplify scenarios where the first byte is an address or command for the I2C device
    # if you just have a single list of data with no first byte separation, you can
    # pass the first byte as data[0] and the rest as data[1:]
    # returns True if the command was successful, False otherwise
    def i2c_write(self, addr, byte1, data, hold=0):
        cmd = f"addr:0x{addr:02x}"
        result = self.send_and_confirm(cmd)
        num_bytes = len(data) + 1
        cmd = f"bytes:{num_bytes}"
        result = self.send_and_confirm(cmd)
        if hold == 1:
            cmd = f"send+hold {byte1:02x}"
        else:
            cmd = f"send {byte1:02x}"
        # loop though the data, in groups of 16 bytes
        for i in range(1, len(data)+1):
            if (i) % 16 != 0:
                if cmd == "":  # this is a new line, no need for preceding space
                    cmd += f"{data[i-1]:02x}"
                else:
                    cmd += f" {data[i-1]:02x}"
            else:
                result = self.send_and_confirm(cmd, wait_period=2000)
                cmd = ""
                if i != len(data) - 1:
                    if self.dbg_print:
                        print(f"checking for &, i is {i}, len(data) is {len(data)}")
                    # check if the result represents the '&' continuation character
                    if result == 3:
                        print("Protocol error, does the I2C device exist?")
                        return False
                    elif result != 2:
                        print(f"Error sending. Expected 2(&) but received {result}")
                        return False
                    cmd = f"{data[i-1]:02x}"
                else:
                    # check if the result represents the '.' character
                    if self.dbg_print:
                        print(f"i is {i}, len(data) is {len(data)}")
                        print("checking for .")
                    if result == 3:
                        print("Protocol error, does the I2C device exist?")
                        return False
                    elif result != 1:
                        print(f"Error sending. Expected 1(.) but received {result}")
                        return False
        # send any remaining content if cmd is not empty
        if cmd != "":
            if self.dbg_print:
                print("sending remainder")
            result = self.send_and_confirm(cmd, wait_period=2000)
            # check if the result represents contains the '.' character
            if result == 3:
                print("Protocol error, does the I2C device exist?")
                return False
            elif result != 1:
                print(f"Error sending. Expected 1(.) but received {result}")
                return False
        if self.dbg_print:
            print("done!")
        return True
    
    # sends an I2C read command to the adapter and returns the data read
    # addr: I2C address
    # num_bytes: number of bytes to read
    # returns the data read as a byte array
    # returns None if the read was unsuccessful
    def i2c_read(self, addr, num_bytes):
        status = False
        cmd = f"addr:0x{addr:02x}"
        result = self.send_and_confirm(cmd)
        cmd = f"bytes:{num_bytes}"
        result = self.send_and_confirm(cmd)
        cmd = "recv"
        if self.adapter_port is None:
            print("No easy_adapter selected. Call find_device() first")
            return
        ser = serial.Serial(self.adapter_port, 115200, timeout=0.2)
        if self.dbg_print:
            print(f"dbg i2c_read: {cmd}")
        ser.write(cmd.encode() + self.txterm)
        buffer = bytes()
        now = time.time_ns() // 1000000
        while ((time.time_ns() // 1000000) - now) < self.cmd_wait_period:
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                now = time.time_ns() // 1000000 # reset the timer
                if buffer[-1] == 38:  # check if the last byte is an '&' character
                    # we need to send back an '&' character to the adapter
                    ser.write(b"&")
                elif buffer[-1] == 46: # check if the last byte is a '.' character
                    # no more data to read, we are done
                    status = True
                    break
                elif buffer[-1] == 88: # check if the last byte is an 'X' character
                    # error
                    status = False
                    break
                elif buffer[-1] == 126: # check if the last byte is a '~' character
                    # protocol error
                    print("Protocol error, does the I2C device exist?")
                    status = False
                    break
        ser.close()
        if status:
            # read the hex data from the buffer, ignoring any & and . characters and save in a byte array
            buffer = buffer.replace(b"&", b"").replace(b".", b"")
            buffer = bytes.fromhex(buffer.decode())
            if self.dbg_print:
                print("done!")
            return buffer
        else:
            print("i2c_read was unsuccessful")
            return None
    
    # sets a GPIO pin to logic level 0 or 1
    # example, to set Pi Pico GPIO 5 to logic zero:
    # io_write(5, 0)
    def io_write(self, gpio_num, val):
        cmd = f"iowrite:{gpio_num},{val}"
        result = self.send_and_confirm(cmd)
        if result != 1:
            print(f"Error setting GPIO {gpio_num} to logic {val}")
            return False
        return True
    
    # reads a GPIO pin and returns the logic level
    # example, to read Pi Pico GPIO 5:
    # io_read(5)
    # returns -1 if the read was unsuccessful
    def io_read(self, gpio_num):
        cmd = f"ioread:{gpio_num}"
        buffer = self.send_command(cmd)
        # check if the buffer contains the '.' character
        if b"." not in buffer:
            print(f"Error reading GPIO {gpio_num}")
            return -1
        if b"0." in buffer:
            return 0
        elif b"1." in buffer:
            return 1
        else:
            return -1
    
    # this function is used to locate the easy_adapter, and to set it to M2M mode
    # the board value is between 0 and 7 (multiple easy_adapters can be connected to the PC)
    # the board value is set using certain GPIO pins shorted to ground 
    # on the easy adapter board (Pi Pico). ADDR[2..0] are GPIO [4..2] respectively
    # these GPIO pins float high normally, and are read once, when the easy adapter is powered on
    # since they float high, the default board value is 0
    # ADDR2  ADDR1  ADDR0   Address
    # 0      0      0       7
    # 0      0      1       6
    # 0      1      0       5
    # 0      1      1       4
    # 1      0      0       3
    # 1      0      1       2
    # 1      1      0       1
    # 1      1      1       0
    def init(self, board=0):
        res = self.find_device(board)
        if res is None:
            return False
        self.m2m_mode(1)
        return True
    
    # this utility function can be used to print data in hex and ASCII
    def print_data(self, buffer):
        for i in range(0, len(buffer), 16):
            if len(buffer) <= 256:
                print(f"{i:02x}: ", end='')
            elif len(buffer) <= 65536:
                print(f"{i:04x}: ", end='')
            elif len(buffer) <= 16777216:
                print(f"{i:06x}: ", end='')
            else:
                print(f"{i:08x}: ", end='')
            for j in range(16):
                if i+j < len(buffer):
                    print(f"{buffer[i+j]:02x} ", end='')
                else:
                    print("   ", end='')
            print(": ", end='')
            for j in range(16):
                if i+j < len(buffer):
                    if buffer[i+j] >= 32 and buffer[i+j] < 127:
                        print(f"{chr(buffer[i+j])}", end='')
                    else:
                        print(".", end='')
                else:
                    print(" ", end='')
            print()

    # this utility function can be used to return a list of possible device names
    # example:
    # names = get_known_device_names(0x40, adapter.db)
    def get_known_device_names(self, addr, dbname):
        reslist = []
        found = False
        for item in dbname:
            if item[0] == addr:
                reslist.append(item[1])
                found = True
        if not found:
            reslist.append("Unknown")
        return reslist
    
    # this utility can be used to do a reverse lookup based on
    # if the supplied search term is contained in the device name
    # example:
    # addr = get_known_device_address("PCA9685", adapter.db)
    def get_known_device_address(self, search_term, dbname):
        reslist = []
        for item in dbname:
            if search_term in item[1]:
                if item[0] not in reslist: # avoid duplicates
                    reslist.append(item[0])
        return reslist

    # array of known I2C addresses
    db = [ \
        [0x00, "Reserved"], \
        [0x01, "Reserved"], \
        [0x02, "Reserved"], \
        [0x03, "Reserved"], \
        [0x04, "Reserved"], \
        [0x05, "Reserved"], \
        [0x06, "Reserved"], \
        [0x07, "Reserved"], \
        [0x08, "Unknown"], \
        [0x0c, "AK8975"], \
        [0x0d, "AK8975"], \
        [0x0e, "MAG3110"], \
        [0x0e, "AK8975"], \
        [0x0e, "IST-8310"], \
        [0x0f, "AK8975"], \
        [0x10, "LM25066"], \
        [0x10, "VML6075"], \
        [0x10, "VEML6075"], \
        [0x10, "VEML7700"], \
        [0x11, "SAA5243P/E"], \
        [0x11, "LM25066"], \
        [0x11, "LC709203F"], \
        [0x11, "SAA5243P/L"], \
        [0x11, "Si4713"], \
        [0x11, "SAA5243P/H"], \
        [0x11, "SAA5246"], \
        [0x11, "SAA5243P/K"], \
        [0x12, "SEN-17374"], \
        [0x12, "PMSA003I"], \
        [0x12, "LM25066"], \
        [0x13, "VCNL40x0"], \
        [0x13, "SEN-17374"], \
        [0x13, "LM25066"], \
        [0x14, "LM25066"], \
        [0x15, "LM25066"], \
        [0x16, "LM25066"], \
        [0x17, "LM25066"], \
        [0x18, "MCP9808"], \
        [0x18, "LIS3DH"], \
        [0x18, "LSM303"], \
        [0x18, "COM-15093"], \
        [0x18, "47L04"], \
        [0x18, "47C04"], \
        [0x18, "47L16"], \
        [0x18, "47C16"], \
        [0x19, "MCP9808"], \
        [0x19, "LIS3DH"], \
        [0x19, "LSM303"], \
        [0x19, "COM-15093"], \
        [0x1a, "MCP9808"], \
        [0x1a, "47L04"], \
        [0x1a, "47C04"], \
        [0x1a, "47L16"], \
        [0x1a, "47C16"], \
        [0x1b, "MCP9808"], \
        [0x1c, "MCP9808"], \
        [0x1c, "MMA845x"], \
        [0x1c, "FXOS8700"], \
        [0x1c, "47L04"], \
        [0x1c, "47C04"], \
        [0x1c, "47L16"], \
        [0x1c, "47C16"], \
        [0x1c, "SAA7706H"], \
        [0x1d, "MCP9808"], \
        [0x1d, "MMA845x"], \
        [0x1d, "ADXL345"], \
        [0x1d, "FXOS8700"], \
        [0x1e, "MCP9808"], \
        [0x1e, "FXOS8700"], \
        [0x1e, "HMC5883"], \
        [0x1e, "LSM303"], \
        [0x1e, "LSM303"], \
        [0x1e, "47L04"], \
        [0x1e, "47C04"], \
        [0x1e, "47L16"], \
        [0x1e, "47C16"], \
        [0x1f, "MCP9808"], \
        [0x1f, "FXOS8700"], \
        [0x20, "FXAS21002"], \
        [0x20, "MCP23008"], \
        [0x20, "MCP23017"], \
        [0x20, "Chirp!"], \
        [0x20, "MA12070P"], \
        [0x20, "TCA9554"], \
        [0x20, "HW-061"], \
        [0x20, "XD8574A"], \
        [0x20, "PCF8575"], \
        [0x20, "PCA6408A"], \
        [0x20, "PCF8574"], \
        [0x21, "FXAS21002"], \
        [0x21, "MCP23008"], \
        [0x21, "MCP23017"], \
        [0x21, "SAA4700"], \
        [0x21, "MA12070P"], \
        [0x21, "TCA9554"], \
        [0x21, "HW-061"], \
        [0x21, "XD8574A"], \
        [0x21, "PCF8575"], \
        [0x21, "PCA6408A"], \
        [0x21, "PCF8574"], \
        [0x22, "MCP23008"], \
        [0x22, "MCP23017"], \
        [0x22, "PCA1070"], \
        [0x22, "MA12070P"], \
        [0x22, "TCA9554"], \
        [0x22, "HW-061"], \
        [0x22, "XD8574A"], \
        [0x22, "PCF8575"], \
        [0x22, "PCF8574"], \
        [0x23, "MCP23008"], \
        [0x23, "MCP23017"], \
        [0x23, "SAA4700"], \
        [0x23, "MA12070P"], \
        [0x23, "TCA9554"], \
        [0x23, "HW-061"], \
        [0x23, "BH1750FVI"], \
        [0x23, "XD8574A"], \
        [0x23, "PCF8575"], \
        [0x23, "PCF8574"], \
        [0x24, "MCP23008"], \
        [0x24, "MCP23017"], \
        [0x24, "PCD3311C"], \
        [0x24, "PCD3312C"], \
        [0x24, "TCA9554"], \
        [0x24, "HW-061"], \
        [0x24, "XD8574A"], \
        [0x24, "PCF8575"], \
        [0x24, "PCF8574"], \
        [0x25, "MCP23008"], \
        [0x25, "MCP23017"], \
        [0x25, "PCD3311C"], \
        [0x25, "PCD3312C"], \
        [0x25, "TCA9554"], \
        [0x25, "HW-061"], \
        [0x25, "XD8574A"], \
        [0x25, "PCF8575"], \
        [0x25, "PCF8574"], \
        [0x26, "MCP23008"], \
        [0x26, "PCF8574"], \
        [0x26, "HW-061"], \
        [0x26, "XD8574A"], \
        [0x26, "MCP23017"], \
        [0x26, "PCF8575"], \
        [0x26, "TCA9554"], \
        [0x27, "HIH6130"], \
        [0x27, "MCP23008"], \
        [0x27, "PCF8574"], \
        [0x27, "HW-061"], \
        [0x27, "XD8574A"], \
        [0x27, "MCP23017"], \
        [0x27, "PCF8575"], \
        [0x27, "TCA9554"], \
        [0x28, "DS1841"], \
        [0x28, "DS1881"], \
        [0x28, "MCP4532"], \
        [0x28, "PM2008"], \
        [0x28, "BNO055"], \
        [0x28, "DS3502"], \
        [0x28, "FS3000"], \
        [0x28, "CAP1188"], \
        [0x29, "BNO055"], \
        [0x29, "CAP1188"], \
        [0x29, "TCS34725"], \
        [0x29, "TSL2591"], \
        [0x29, "VL53L0x"], \
        [0x29, "VL6180X"], \
        [0x29, "DS1841"], \
        [0x29, "DS3502"], \
        [0x29, "DS1881"], \
        [0x29, "MCP4532"], \
        [0x2a, "DS1841"], \
        [0x2a, "DS1881"], \
        [0x2a, "MCP4532"], \
        [0x2a, "DS3502"], \
        [0x2a, "CAP1188"], \
        [0x2b, "CAP1188"], \
        [0x2b, "DS1841"], \
        [0x2b, "DS3502"], \
        [0x2b, "DS1881"], \
        [0x2b, "MCP4532"], \
        [0x2c, "CAT5171"], \
        [0x2c, "DS1881"], \
        [0x2c, "MCP4532"], \
        [0x2c, "AD5252"], \
        [0x2c, "AD5251"], \
        [0x2c, "CAP1188"], \
        [0x2c, "AD5248"], \
        [0x2d, "CAP1188"], \
        [0x2d, "AD5248"], \
        [0x2d, "AD5251"], \
        [0x2d, "AD5252"], \
        [0x2d, "CAT5171"], \
        [0x2d, "DS1881"], \
        [0x2d, "MCP4532"], \
        [0x2d, "ST25DV16K"], \
        [0x2e, "AD5248"], \
        [0x2e, "AD5251"], \
        [0x2e, "AD5252"], \
        [0x2e, "LPS22HB"], \
        [0x2e, "DS1881"], \
        [0x2e, "MCP4532"], \
        [0x2f, "DS1881"], \
        [0x2f, "MCP4532"], \
        [0x2f, "AD5252"], \
        [0x2f, "AD5243"], \
        [0x2f, "AD5251"], \
        [0x2f, "AD5248"], \
        [0x30, "SAA2502"], \
        [0x31, "SAA2502"], \
        [0x32, "ZMOD4410"], \
        [0x32, "ZMOD4450"], \
        [0x33, "MLX90640"], \
        [0x33, "ZMOD4510"], \
        [0x36, "MAX17048"], \
        [0x36, "MAX17048"], \
        [0x38, "SEN-15892"], \
        [0x38, "PCF8574AP"], \
        [0x38, "SAA1064"], \
        [0x38, "AHT20"], \
        [0x38, "FT6x06"], \
        [0x38, "BMA150"], \
        [0x38, "RRH46410"], \
        [0x38, "VEML6070"], \
        [0x38, "AHT10"], \
        [0x39, "TSL2561"], \
        [0x39, "APDS-9960"], \
        [0x39, "VEML6070"], \
        [0x39, "SAA1064"], \
        [0x39, "PCF8574AP"], \
        [0x3a, "PCF8577C"], \
        [0x3a, "SAA1064"], \
        [0x3a, "PCF8574AP"], \
        [0x3a, "MLX90632"], \
        [0x3b, "SAA1064"], \
        [0x3b, "PCF8569"], \
        [0x3b, "PCF8574AP"], \
        [0x3c, "SSD1305"], \
        [0x3c, "SSD1306"], \
        [0x3c, "PCF8578"], \
        [0x3c, "PCF8569"], \
        [0x3c, "SH1106"], \
        [0x3c, "PCF8574AP"], \
        [0x3d, "SSD1305"], \
        [0x3d, "SSD1306"], \
        [0x3d, "PCF8574AP"], \
        [0x3d, "SH1106"], \
        [0x3d, "PCF8578"], \
        [0x3e, "PCF8574AP"], \
        [0x3e, "BU9796"], \
        [0x3f, "PCF8574AP"], \
        [0x40, "Si7021"], \
        [0x40, "HTU21D-F"], \
        [0x40, "TMP007"], \
        [0x40, "TMP006"], \
        [0x40, "PCA9685"], \
        [0x40, "INA219"], \
        [0x40, "TEA6330"], \
        [0x40, "TEA6300"], \
        [0x40, "TDA9860"], \
        [0x40, "TEA6320"], \
        [0x40, "TDA8421"], \
        [0x40, "NE5751"], \
        [0x40, "INA260"], \
        [0x40, "PCF8574"], \
        [0x40, "HDC1080"], \
        [0x40, "LM25066"], \
        [0x40, "HTU31D"], \
        [0x41, "TMP007"], \
        [0x41, "TMP006"], \
        [0x41, "PCA9685"], \
        [0x41, "INA219"], \
        [0x41, "STMPE610"], \
        [0x41, "STMPE811"], \
        [0x41, "TDA8426"], \
        [0x41, "TDA9860"], \
        [0x41, "TDA8424"], \
        [0x41, "TDA8421"], \
        [0x41, "TDA8425"], \
        [0x41, "NE5751"], \
        [0x41, "INA260"], \
        [0x41, "PCF8574"], \
        [0x41, "LM25066"], \
        [0x41, "PCA9536"], \
        [0x41, "HTU31D"], \
        [0x42, "HDC1008"], \
        [0x42, "TMP007"], \
        [0x42, "TMP006"], \
        [0x42, "PCA9685"], \
        [0x42, "INA219"], \
        [0x42, "TDA8415"], \
        [0x42, "TDA8417"], \
        [0x42, "INA260"], \
        [0x42, "PCF8574"], \
        [0x42, "LM25066"], \
        [0x43, "HDC1008"], \
        [0x43, "INA219"], \
        [0x43, "PCA9685"], \
        [0x43, "TMP006"], \
        [0x43, "INA260"], \
        [0x43, "LM25066"], \
        [0x43, "PCF8574"], \
        [0x43, "TMP007"], \
        [0x44, "TMP007"], \
        [0x44, "TMP006"], \
        [0x44, "PCA9685"], \
        [0x44, "INA219"], \
        [0x44, "STMPE610"], \
        [0x44, "SHT31"], \
        [0x44, "ISL29125"], \
        [0x44, "STMPE811"], \
        [0x44, "TDA4688"], \
        [0x44, "TDA4672"], \
        [0x44, "TDA4780"], \
        [0x44, "TDA4670"], \
        [0x44, "TDA8442"], \
        [0x44, "TDA4687"], \
        [0x44, "TDA4671"], \
        [0x44, "TDA4680"], \
        [0x44, "INA260"], \
        [0x44, "PCF8574"], \
        [0x44, "LM25066"], \
        [0x44, "HS30xx"], \
        [0x45, "TMP007"], \
        [0x45, "TMP006"], \
        [0x45, "PCA9685"], \
        [0x45, "INA219"], \
        [0x45, "SHT31"], \
        [0x45, "TDA8376"], \
        [0x45, "INA260"], \
        [0x45, "TDA7433"], \
        [0x45, "PCF8574"], \
        [0x45, "LM25066"], \
        [0x46, "INA219"], \
        [0x46, "PCA9685"], \
        [0x46, "TMP006"], \
        [0x46, "INA260"], \
        [0x46, "LM25066"], \
        [0x46, "PCF8574"], \
        [0x46, "TMP007"], \
        [0x46, "TDA9150"], \
        [0x46, "TDA8370"], \
        [0x47, "INA219"], \
        [0x47, "PCA9685"], \
        [0x47, "TMP006"], \
        [0x47, "INA260"], \
        [0x47, "LM25066"], \
        [0x47, "PCF8574"], \
        [0x47, "TMP007"], \
        [0x48, "PCA9685"], \
        [0x48, "INA219"], \
        [0x48, "PN532"], \
        [0x48, "TMP102"], \
        [0x48, "INA260"], \
        [0x48, "ADS1115"], \
        [0x48, "PCF8574"], \
        [0x48, "ADS7828"], \
        [0x48, "LM75b"], \
        [0x48, "ADS1015"], \
        [0x48, "STDS75"], \
        [0x49, "TSL2561"], \
        [0x49, "PCA9685"], \
        [0x49, "INA219"], \
        [0x49, "TMP102"], \
        [0x49, "INA260"], \
        [0x49, "ADS1115"], \
        [0x49, "AS7262"], \
        [0x49, "PCF8574"], \
        [0x49, "ADS7828"], \
        [0x49, "LM75b"], \
        [0x49, "ADS1015"], \
        [0x49, "STDS75"], \
        [0x4a, "PCA9685"], \
        [0x4a, "INA219"], \
        [0x4a, "TMP102"], \
        [0x4a, "ADS1115"], \
        [0x4a, "MAX44009"], \
        [0x4a, "INA260"], \
        [0x4a, "PCF8574"], \
        [0x4a, "ADS7828"], \
        [0x4a, "LM75b"], \
        [0x4a, "ADS1015"], \
        [0x4a, "CS43L22"], \
        [0x4a, "STDS75"], \
        [0x4b, "PCA9685"], \
        [0x4b, "INA219"], \
        [0x4b, "TMP102"], \
        [0x4b, "ADS1115"], \
        [0x4b, "MAX44009"], \
        [0x4b, "INA260"], \
        [0x4b, "PCF8574"], \
        [0x4b, "ADS7828"], \
        [0x4b, "LM75b"], \
        [0x4b, "ADS1015"], \
        [0x4b, "STDS75"], \
        [0x4c, "LM75b"], \
        [0x4c, "INA219"], \
        [0x4c, "PCA9685"], \
        [0x4c, "INA260"], \
        [0x4c, "PCF8574"], \
        [0x4c, "STDS75"], \
        [0x4c, "EMC2101"], \
        [0x4d, "LM75b"], \
        [0x4d, "INA219"], \
        [0x4d, "PCA9685"], \
        [0x4d, "INA260"], \
        [0x4d, "PCF8574"], \
        [0x4d, "STDS75"], \
        [0x4e, "LM75b"], \
        [0x4e, "INA219"], \
        [0x4e, "PCA9685"], \
        [0x4e, "INA260"], \
        [0x4e, "PCF8574"], \
        [0x4e, "STDS75"], \
        [0x4f, "LM75b"], \
        [0x4f, "INA219"], \
        [0x4f, "PCA9685"], \
        [0x4f, "INA260"], \
        [0x4f, "PCF8574"], \
        [0x4f, "STDS75"], \
        [0x50, "PCA9685"], \
        [0x50, "MB85RC"], \
        [0x50, "CAT24C512"], \
        [0x50, "LM25066"], \
        [0x50, "47L04"], \
        [0x50, "47C04"], \
        [0x50, "47L16"], \
        [0x50, "47C16"], \
        [0x50, "FS1015"], \
        [0x50, "AT24C64"], \
        [0x50, "AT24C02N"], \
        [0x51, "PCA9685"], \
        [0x51, "MB85RC"], \
        [0x51, "CAT24C512"], \
        [0x51, "VCNL4200"], \
        [0x51, "LM25066"], \
        [0x51, "PCF8563"], \
        [0x51, "AT24C64"], \
        [0x51, "AT24C02N"], \
        [0x52, "PCA9685"], \
        [0x52, "MB85RC"], \
        [0x52, "Nunchuck"], \
        [0x52, "controller"], \
        [0x52, "APDS-9250"], \
        [0x52, "CAT24C512"], \
        [0x52, "SI1133"], \
        [0x52, "LM25066"], \
        [0x52, "47L04"], \
        [0x52, "47C04"], \
        [0x52, "47L16"], \
        [0x52, "47C16"], \
        [0x52, "AT24C64"], \
        [0x52, "AT24C02N"], \
        [0x53, "ADXL345"], \
        [0x53, "PCA9685"], \
        [0x53, "MB85RC"], \
        [0x53, "CAT24C512"], \
        [0x53, "LM25066"], \
        [0x53, "AT24C64"], \
        [0x53, "ST25DV16K"], \
        [0x53, "AT24C02N"], \
        [0x54, "AT24C64"], \
        [0x54, "47L04"], \
        [0x54, "47C04"], \
        [0x54, "47L16"], \
        [0x54, "47C16"], \
        [0x54, "PCA9685"], \
        [0x54, "LM25066"], \
        [0x54, "HS40xx"], \
        [0x54, "MB85RC"], \
        [0x54, "CAT24C512"], \
        [0x54, "AT24C02N"], \
        [0x55, "PCA9685"], \
        [0x55, "MB85RC"], \
        [0x55, "MAX30101"], \
        [0x55, "CAT24C512"], \
        [0x55, "SI1133"], \
        [0x55, "LM25066"], \
        [0x55, "AT24C64"], \
        [0x55, "D7S"], \
        [0x55, "AT24C02N"], \
        [0x56, "AT24C64"], \
        [0x56, "47L04"], \
        [0x56, "47C04"], \
        [0x56, "47L16"], \
        [0x56, "47C16"], \
        [0x56, "PCA9685"], \
        [0x56, "LM25066"], \
        [0x56, "MB85RC"], \
        [0x56, "CAT24C512"], \
        [0x56, "AT24C02N"], \
        [0x57, "PCA9685"], \
        [0x57, "MB85RC"], \
        [0x57, "MAX3010x"], \
        [0x57, "CAT24C512"], \
        [0x57, "LM25066"], \
        [0x57, "AT24C64"], \
        [0x57, "ST25DV16K"], \
        [0x57, "AT24C02N"], \
        [0x58, "PCA9685"], \
        [0x58, "TPA2016"], \
        [0x58, "SGP30"], \
        [0x58, "LM25066"], \
        [0x59, "PCA9685"], \
        [0x59, "LM25066"], \
        [0x59, "SGP40"], \
        [0x5a, "MLX90614"], \
        [0x5a, "PCA9685"], \
        [0x5a, "DRV2605"], \
        [0x5a, "LM25066"], \
        [0x5a, "CCS811"], \
        [0x5a, "CCS811"], \
        [0x5a, "MPR121"], \
        [0x5b, "PCA9685"], \
        [0x5b, "CCS811"], \
        [0x5b, "MPR121"], \
        [0x5b, "CCS811"], \
        [0x5c, "PCA9685"], \
        [0x5c, "AM2315"], \
        [0x5c, "MPR121"], \
        [0x5c, "BH1750FVI"], \
        [0x5c, "AM2320"], \
        [0x5d, "PCA9685"], \
        [0x5d, "MPR121"], \
        [0x5d, "SFA30"], \
        [0x5e, "PCA9685"], \
        [0x5f, "PCA9685"], \
        [0x5f, "HTS221"], \
        [0x60, "PCA9685"], \
        [0x60, "MPL115A2"], \
        [0x60, "MPL3115A2"], \
        [0x60, "Si5351A"], \
        [0x60, "Si1145"], \
        [0x60, "MCP4725A0"], \
        [0x60, "TEA5767"], \
        [0x60, "TSA5511"], \
        [0x60, "SAB3037"], \
        [0x60, "SAB3035"], \
        [0x60, "MCP4725A1"], \
        [0x60, "ATECC508A"], \
        [0x60, "ATECC608A"], \
        [0x60, "SI1132"], \
        [0x60, "MCP4728"], \
        [0x61, "PCA9685"], \
        [0x61, "Si5351A"], \
        [0x61, "MCP4725A0"], \
        [0x61, "TEA6100"], \
        [0x61, "TSA5511"], \
        [0x61, "SAB3037"], \
        [0x61, "SAB3035"], \
        [0x61, "MCP4725A1"], \
        [0x61, "SCD30"], \
        [0x61, "MCP4728"], \
        [0x62, "PCA9685"], \
        [0x62, "MCP4725A1"], \
        [0x62, "TSA5511"], \
        [0x62, "SAB3037"], \
        [0x62, "SAB3035"], \
        [0x62, "UMA1014T"], \
        [0x62, "SCD40-D-R2"], \
        [0x62, "SCD41"], \
        [0x62, "SCD40"], \
        [0x62, "MCP4728"], \
        [0x63, "UMA1014T"], \
        [0x63, "SAB3037"], \
        [0x63, "MCP4725A1"], \
        [0x63, "PCA9685"], \
        [0x63, "MCP4728"], \
        [0x63, "SAB3035"], \
        [0x63, "TSA5511"], \
        [0x63, "Si4713"], \
        [0x64, "PCA9685"], \
        [0x64, "MCP4725A2"], \
        [0x64, "MCP4725A1"], \
        [0x64, "MCP4728"], \
        [0x65, "PCA9685"], \
        [0x65, "MCP4725A2"], \
        [0x65, "MCP4725A1"], \
        [0x65, "MCP4728"], \
        [0x66, "IS31FL3731"], \
        [0x66, "MCP4725A1"], \
        [0x66, "LTC4151"], \
        [0x66, "PCA9685"], \
        [0x66, "MCP4728"], \
        [0x66, "MCP4725A3"], \
        [0x67, "PCA9685"], \
        [0x67, "MCP4725A3"], \
        [0x67, "MCP4725A1"], \
        [0x67, "MCP4728"], \
        [0x67, "LTC4151"], \
        [0x68, "PCA9685"], \
        [0x68, "AMG8833"], \
        [0x68, "DS1307"], \
        [0x68, "PCF8523"], \
        [0x68, "DS3231"], \
        [0x68, "MPU-9250"], \
        [0x68, "ITG3200"], \
        [0x68, "PCF8573"], \
        [0x68, "MPU6050"], \
        [0x68, "ICM-20948"], \
        [0x68, "WITTY"], \
        [0x68, "PI"], \
        [0x68, "3"], \
        [0x68, "MCP3422"], \
        [0x68, "DS1371"], \
        [0x68, "MPU-9250"], \
        [0x68, "LTC4151"], \
        [0x68, "BQ32000"], \
        [0x69, "PCA9685"], \
        [0x69, "AMG8833"], \
        [0x69, "MPU-9250"], \
        [0x69, "ITG3200"], \
        [0x69, "PCF8573"], \
        [0x69, "SPS30"], \
        [0x69, "MPU6050"], \
        [0x69, "ICM-20948"], \
        [0x69, "WITTY"], \
        [0x69, "PI"], \
        [0x69, "3"], \
        [0x69, "MAX31341"], \
        [0x69, "LTC4151"], \
        [0x69, "RRH62000"], \
        [0x6a, "PCA9685"], \
        [0x6a, "L3GD20H"], \
        [0x6a, "PCF8573"], \
        [0x6a, "LTC4151"], \
        [0x6b, "PCA9685"], \
        [0x6b, "L3GD20H"], \
        [0x6b, "PCF8573"], \
        [0x6b, "LTC4151"], \
        [0x6c, "PCA9685"], \
        [0x6c, "LTC4151"], \
        [0x6d, "PCA9685"], \
        [0x6d, "LTC4151"], \
        [0x6e, "PCA9685"], \
        [0x6e, "LTC4151"], \
        [0x6f, "PCA9685"], \
        [0x6f, "MCP7940N"], \
        [0x6f, "LTC4151"], \
        [0x70, "PCA9685"], \
        [0x70, "TCA9548"], \
        [0x70, "HT16K33"], \
        [0x70, "SHTC3"], \
        [0x70, "PCA9541"], \
        [0x70, "TCA9548A"], \
        [0x70, "XD8574"], \
        [0x71, "PCA9685"], \
        [0x71, "TCA9548"], \
        [0x71, "HT16K33"], \
        [0x71, "PCA9541"], \
        [0x71, "TCA9548A"], \
        [0x71, "XD8574"], \
        [0x72, "PCA9685"], \
        [0x72, "TCA9548"], \
        [0x72, "HT16K33"], \
        [0x72, "PCA9541"], \
        [0x72, "TCA9548A"], \
        [0x72, "XD8574"], \
        [0x73, "PCA9685"], \
        [0x73, "TCA9548"], \
        [0x73, "HT16K33"], \
        [0x73, "PCA9541"], \
        [0x73, "TCA9548A"], \
        [0x73, "XD8574"], \
        [0x74, "PCA9685"], \
        [0x74, "HT16K33"], \
        [0x74, "PCA9539"], \
        [0x74, "PCA9541"], \
        [0x74, "TCA9548A"], \
        [0x74, "TCA9548"], \
        [0x74, "XD8574"], \
        [0x75, "PCA9685"], \
        [0x75, "HT16K33"], \
        [0x75, "PCA9539"], \
        [0x75, "PCA9541"], \
        [0x75, "TCA9548A"], \
        [0x75, "TCA9548"], \
        [0x75, "XD8574"], \
        [0x76, "PCA9685"], \
        [0x76, "TCA9548"], \
        [0x76, "HT16K33"], \
        [0x76, "BME280"], \
        [0x76, "BMP280"], \
        [0x76, "MS5607"], \
        [0x76, "MS5611"], \
        [0x76, "BME680"], \
        [0x76, "BME688"], \
        [0x76, "PCA9541"], \
        [0x76, "SPL06-007"], \
        [0x76, "TCA9548A"], \
        [0x76, "XD8574"], \
        [0x76, "PCA9539"], \
        [0x77, "PCA9685"], \
        [0x77, "TCA9548"], \
        [0x77, "HT16K33"], \
        [0x77, "IS31FL3731"], \
        [0x77, "BME280"], \
        [0x77, "BMP280"], \
        [0x77, "MS5607"], \
        [0x77, "BMP180"], \
        [0x77, "BMP085"], \
        [0x77, "BMA180"], \
        [0x77, "MS5611"], \
        [0x77, "BME680"], \
        [0x77, "BME688"], \
        [0x77, "PCA9541"], \
        [0x77, "SPL06-007"], \
        [0x77, "TCA9548A"], \
        [0x77, "XD8574"], \
        [0x77, "PCA9539"], \
        [0x78, "PCA9685"], \
        [0x79, "PCA9685"], \
        [0x7a, "PCA9685"], \
        [0x7b, "PCA9685"], \
        [0x7c, "PCA9685"], \
        [0x7d, "PCA9685"], \
        [0x7e, "PCA9685"], \
        [0x7f, "PCA9685"], \
        ]

