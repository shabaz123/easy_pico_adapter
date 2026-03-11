# Easy Pico Adapter - API Reference

Complete API reference for the Easy I2C Adapter including Python module methods and firmware command reference.

---

# Python API Reference

The `easyadapter.py` module provides the `EasyAdapter` class for controlling the I2C adapter from Python.

## Class: EasyAdapter

### Constructor

#### `__init__()`
Creates a new EasyAdapter instance.

```python
adapter = ea.EasyAdapter()
```

**Attributes:**
- `txterm` - Transmission terminator (default: `b"\r"`)
- `adapter_port` - Serial port name (set automatically by `find_device()`)
- `cmd_wait_period` - Command timeout in milliseconds (default: 500)
- `dbg_print` - Enable debug printing (default: False)
- `db` - Database of known I2C device addresses

### Initialization Methods

#### `init(board=0)`
Initializes the adapter by finding the device and setting M2M mode.

**Parameters:**
- `board` (int): Board ID from 0-7 (default: 0)

**Returns:**
- `True` if successful, `False` otherwise

**Example:**
```python
result = adapter.init(0)
```

#### `find_device(board=0)`
Searches available COM ports for the specified Easy Adapter board. Called automatically by `init()`.

**Parameters:**
- `board` (int): Board ID to search for (default: 0)

**Returns:**
- Port device name (string) if found, `None` otherwise

### I2C Methods

#### `i2c_write(addr, byte1, data, hold=0)`
Writes data to an I2C device.

**Parameters:**
- `addr` (int): I2C device address (7-bit)
- `byte1` (int): First byte to send (typically register address)
- `data` (list): List of remaining bytes to send
- `hold` (int): Set to 1 to hold bus for repeated start (default: 0)

**Returns:**
- `True` if successful, `False` otherwise

**Example:**
```python
# Write to register 0x00 with data [0x01, 0x02, 0x03]
adapter.i2c_write(0x50, 0x00, [0x01, 0x02, 0x03])

# Write single byte
adapter.i2c_write(0x70, 0x01, [])

# Write with repeated start
adapter.i2c_write(0x50, 0x00, [], hold=1)
```

#### `i2c_read(addr, num_bytes)`
Reads data from an I2C device.

**Parameters:**
- `addr` (int): I2C device address (7-bit)
- `num_bytes` (int): Number of bytes to read

**Returns:**
- `bytearray` with data read, or `None` if unsuccessful

**Example:**
```python
buffer = adapter.i2c_read(0x50, 16)
if buffer:
    print(f"Read {len(buffer)} bytes")
```

#### `i2c_try_address(addr)`
Checks if an I2C device exists at the specified address.

**Parameters:**
- `addr` (int): I2C device address to test (7-bit)

**Returns:**
- `True` if device responds, `False` otherwise

**Example:**
```python
if adapter.i2c_try_address(0x50):
    print("Device found at 0x50")
```

### GPIO Methods

#### `io_write(gpio_num, val)`
Sets a GPIO pin to a logic level. Automatically configures pin as output.

**Parameters:**
- `gpio_num` (int): GPIO pin number (0-28, excluding reserved pins)
- `val` (int): Logic level (0 or 1)

**Returns:**
- `True` if successful, `False` otherwise

**Example:**
```python
adapter.io_write(6, 1)  # Set GPIO 6 high
adapter.io_write(6, 0)  # Set GPIO 6 low
```

**Note:** Pins 2, 3, 4 (board ID), 14, 15 (I2C) are reserved and cannot be used.

#### `io_read(gpio_num)`
Reads the logic level of a GPIO pin. Automatically configures pin as input with pull-up.

**Parameters:**
- `gpio_num` (int): GPIO pin number (0-28, excluding reserved pins)

**Returns:**
- `0` or `1` for logic level, `-1` on error

**Example:**
```python
level = adapter.io_read(5)
if level >= 0:
    print(f"GPIO 5 is {level}")
```

### Utility Methods

#### `print_data(buffer)`
Prints data in a formatted hex and ASCII display.

**Parameters:**
- `buffer` (bytes/bytearray): Data to print

**Example:**
```python
buffer = adapter.i2c_read(0x50, 64)
adapter.print_data(buffer)
```

**Output format:**
```
00: 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 : ................
10: 11 12 13 14 15 16 17 18 19 1A 1B 1C 1D 1E 1F 20 : ...............
```

#### `get_known_device_names(addr, dbname)`
Returns a list of possible device names for an I2C address.

**Parameters:**
- `addr` (int): I2C address to lookup
- `dbname` (list): Database to search (use `adapter.db`)

**Returns:**
- List of device name strings

**Example:**
```python
names = adapter.get_known_device_names(0x18, adapter.db)
print(f"Possible devices at 0x18: {names}")
```

#### `get_known_device_address(search_term, dbname)`
Returns list of I2C addresses matching a device name search.

**Parameters:**
- `search_term` (string): Text to search for in device names
- `dbname` (list): Database to search (use `adapter.db`)

**Returns:**
- List of matching I2C addresses (int)

**Example:**
```python
addresses = adapter.get_known_device_address("MCP9808", adapter.db)
print(f"MCP9808 found at addresses: {[hex(a) for a in addresses]}")
```

### Low-Level Methods

#### `send_command(cmd)`
Sends a raw command string and returns the response buffer. Used internally.

**Parameters:**
- `cmd` (string): Command to send

**Returns:**
- `bytes` response buffer

#### `send_and_confirm(cmd, wait_period=-1)`
Sends a command and waits for M2M response character. Used internally.

**Parameters:**
- `cmd` (string): Command to send
- `wait_period` (int): Timeout in milliseconds (default: uses `cmd_wait_period`)

**Returns:**
- `1` if '.' received (OK)
- `2` if '&' received (continue)
- `3` if '~' received (protocol error)
- `0` for general error

#### `m2m_mode(val)`
Enters or exits machine-to-machine mode. Called automatically by `init()`.

**Parameters:**
- `val` (int): 1 to enter M2M mode, 0 to exit

---

# Firmware Command Reference

These commands can be sent to the Easy I2C Adapter in interactive mode (via serial terminal) or in M2M mode (programmatically). In M2M mode, responses use special characters instead of text.

## Connection and Identification

### `device?`
Returns the device identifier string.

**Interactive Response:**
```
easy_adapter_0
```

**M2M Response:** Same as interactive

**Example:**
```
device?
```

## Mode Control

### `m2m_resp:N`
Enables or disables machine-to-machine response mode.

**Parameters:**
- `N`: 1 to enable M2M mode, 0 to disable

**Interactive Response:**
```
M2M response off
```

**M2M Response:** 
- `.` (OK) when enabling
- Text message when disabling

**Example:**
```
m2m_resp:1
```

### `bin`
Switches to binary input mode (for binary data transfer).

**Interactive Response:**
```
Switching to binary mode
```

**M2M Response:** `.` (OK)

### `noecho`
Disables character echo in interactive mode.

**Interactive Response:**
```
Echo off
```

## I2C Address Configuration

### `addr:N` or `addr:0xNN`
Sets the target I2C address for subsequent operations.

**Parameters:**
- `N`: I2C address in decimal
- `0xNN`: I2C address in hexadecimal

**Interactive Response:**
```
I2C address set to 0x50
```

**M2M Response:** `.` (OK)

**Examples:**
```
addr:80
addr:0x50
```

### `tryaddr:N` or `tryaddr:0xNN`
Tests if an I2C device exists at the specified address using bitbang method.

**Parameters:**
- `N`: I2C address in decimal
- `0xNN`: I2C address in hexadecimal

**Interactive Response:**
```
Device found at address 0x50
```
or
```
Protocol error! Does the I2C device exist?
```

**M2M Response:** 
- `.` if device found
- `~` if device not found (protocol error)

**Examples:**
```
tryaddr:0x0b
tryaddr:80
```

## Data Transfer

### `bytes:N`
Sets the number of bytes for the next send or receive operation.

**Parameters:**
- `N`: Number of bytes (1-256)

**Interactive Response:**
```
Expecting 16 bytes
```

**M2M Response:** `.` (OK)

**Example:**
```
bytes:16
```

### `send`
Sends data bytes to the I2C device. Must be preceded by `addr:` and `bytes:` commands.

**Data Format:** Space-separated hexadecimal bytes

**Interactive Response:**
```
Sending 4 bytes
[Hex dump of data]
```

**M2M Response:** 
- `.` when complete
- `~` on protocol error

**Example:**
```
addr:0x50
bytes:4
send 01 02 03 04
```

### `send+hold`
Sends data bytes and holds the I2C bus (for repeated start condition).

**Data Format:** Same as `send`

**Interactive Response:** Same as `send`

**M2M Response:** Same as `send`

**Example (Reading from EEPROM):**
```
addr:0x50
bytes:2
send+hold 00 00
bytes:16
recv
```

### `recv`
Receives data bytes from the I2C device. Must be preceded by `addr:` and `bytes:` commands.

**Interactive Response:**
```
[Hex dump of received data]
```
or
```
Protocol error reading bytes! Does the I2C device exist?
```

**M2M Response:** 
- Hex bytes (in ASCII mode) or raw bytes (in binary mode)
- `&` every 16 bytes (ASCII) or 64 bytes (binary) requiring `&` acknowledgment
- `.` when complete
- `~` on protocol error

**Example:**
```
addr:0x50
bytes:16
recv
```

## GPIO Control

### `iowrite:P,V`
Sets a GPIO pin to a logic level. Automatically configures pin as output.

**Parameters:**
- `P`: GPIO pin number (0-28, excluding reserved pins 2,3,4,14,15)
- `V`: Value (0 or 1)

**Interactive Response:**
```
Port 6 set to output 1
```
or
```
Error, invalid IO port or value
```

**M2M Response:** 
- `.` (OK)
- `X` on error

**Examples:**
```
iowrite:6,1
iowrite:6,0
```

### `ioread:P`
Reads a GPIO pin logic level. Automatically configures pin as input with pull-up.

**Parameters:**
- `P`: GPIO pin number (0-28, excluding reserved pins)

**Interactive Response:**
```
Port 5 read input as 1
```
or
```
Error, invalid IO port
```

**M2M Response:** 
- `0.` or `1.` (value followed by OK)
- `X` on error

**Example:**
```
ioread:5
```

## M2M Response Characters

When in M2M mode (`m2m_resp:1`), the firmware uses these single-character responses:

| Character | Meaning |
|-----------|---------|
| `.` | Command completed successfully (OK) |
| `&` | Continue - send more data or acknowledge receipt |
| `X` | Error - general command error |
| `~` | Protocol error - I2C NACK or device not responding |

## Reserved GPIO Pins

The following GPIO pins are reserved and cannot be used with `iowrite` or `ioread`:

| Pin | Function |
|-----|----------|
| 2 | Board ID bit 0 |
| 3 | Board ID bit 1 |
| 4 | Board ID bit 2 |
| 14 | I2C SDA |
| 15 | I2C SCL |
| 25 | LED (on-board) |

## Typical Command Sequences

### Read from EEPROM with address pointer
```
addr:0x50
bytes:2
send+hold 00 10
bytes:16
recv
```

### Write to EEPROM
```
addr:0x50
bytes:5
send 00 00 AA BB CC DD
```

### Scan I2C bus
```
tryaddr:0x08
tryaddr:0x09
...
tryaddr:0x77
```

### Configure and read GPIO
```
iowrite:6,1
ioread:6
```
