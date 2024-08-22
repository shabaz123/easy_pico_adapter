# Python module for interfacing via serial to an I2C adapter
# requires pyserial

import serial  # Note: this is the pyserial module, NOT the serial module
from serial.tools import list_ports
import time
import sys

txterm = b"\r"
adapter_port = None
cmd_wait_period = 500
dbg_print = False

# sends a command and returns the serial buffer result
def send_command(cmd):
    if adapter_port is None:
        print("No easy_adapter selected. Call find_device() first")
        return
    ser = serial.Serial(adapter_port, 115200, timeout=0.2)
    if dbg_print:
        print(f"dbg send_command: {cmd}")
    ser.write(cmd.encode() + txterm)
    buffer = bytes()
    now = time.time_ns() // 1000000
    while ((time.time_ns() // 1000000) - now) < cmd_wait_period:
        if ser.in_waiting > 0:
            buffer += ser.read(ser.in_waiting)
    ser.close()
    return buffer

# sends a command and decodes the response (only use this function in m2m mode)
# returns 1 if '.' is received, 2 if '&' is received,
# returns 3 if '~' (protocol error) received, 0 for general error
def send_and_confirm(cmd, wait_period=cmd_wait_period):
    if adapter_port is None:
        print("No easy_adapter selected. Call find_device() first")
        return
    ser = serial.Serial(adapter_port, 115200, timeout=0.2)
    if dbg_print:
        print(f"dbg send_and_confirm: {cmd}")
    ser.write(cmd.encode() + txterm)
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
def find_device():
    global adapter_port
    perm_error = 0
    ports = list_ports.comports()
    for port in ports:
        # try to see if port can be opened
        try:
            ser = serial.Serial(port.device, 115200, timeout=0.2)
            ser.write(txterm + b"device?" + txterm)
            found = 0
            buffer = bytes()
            now = time.time_ns() // 1000000
            while ((time.time_ns() // 1000000) - now) < cmd_wait_period:
                if ser.in_waiting > 0:
                    buffer += ser.read(ser.in_waiting)
            if b"easy_adapter" in buffer:
                found = 1
            if found == 1:
                print(f"Found easy_adapter at port {port.device}")
                adapter_port = port.device
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
        print("No easy_adapter device found")
    return None

# enters or exits M2M mode, 1 for entering the mode, 0 for exiting
def m2m_mode(val):
    cmd = f"m2m_resp:{val}"
    buffer = send_command(cmd)
    if val == 1:
        if b"." not in buffer:
            print(f"Error entering M2M mode")
    else:
        if b"M2M response off" not in buffer:
            print(f"Error exiting M2M mode")


# tries an I2C address, returns True if the address is found, False otherwise
def i2c_try_address(addr):
    cmd = f"tryaddr:0x{addr:02x}"
    result = send_and_confirm(cmd)
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
def i2c_write(addr, byte1, data, hold=0):
    cmd = f"addr:0x{addr:02x}"
    result = send_and_confirm(cmd)
    num_bytes = len(data) + 1
    cmd = f"bytes:{num_bytes}"
    result = send_and_confirm(cmd)
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
            result = send_and_confirm(cmd, wait_period=2000)
            cmd = ""
            if i != len(data) - 1:
                if dbg_print:
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
                if dbg_print:
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
        if dbg_print:
            print("sending remainder")
        result = send_and_confirm(cmd, wait_period=2000)
        # check if the result represents contains the '.' character
        if result == 3:
            print("Protocol error, does the I2C device exist?")
            return False
        elif result != 1:
            print(f"Error sending. Expected 1(.) but received {result}")
            return False
    if dbg_print:
        print("done!")
    return True

# sends an I2C read command to the adapter and returns the data read
# addr: I2C address
# num_bytes: number of bytes to read
# returns the data read as a byte array
# returns None if the read was unsuccessful
def i2c_read(addr, num_bytes):
    status = False
    cmd = f"addr:0x{addr:02x}"
    result = send_and_confirm(cmd)
    cmd = f"bytes:{num_bytes}"
    result = send_and_confirm(cmd)
    cmd = "recv"
    if adapter_port is None:
        print("No easy_adapter selected. Call find_device() first")
        return
    ser = serial.Serial(adapter_port, 115200, timeout=0.2)
    if dbg_print:
        print(f"dbg i2c_read: {cmd}")
    ser.write(cmd.encode() + txterm)
    buffer = bytes()
    now = time.time_ns() // 1000000
    while ((time.time_ns() // 1000000) - now) < cmd_wait_period:
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
        if dbg_print:
            print("done!")
        return buffer
    else:
        print("i2c_read was unsuccessful")
        return None

# this function is used to locate the easy_adapter, and to set it to M2M mode
def init():
    res = find_device()
    if res is None:
        return False
    m2m_mode(1)
    return True

# this utility function can be used to print data in hex and ASCII
def print_data(buffer):
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
