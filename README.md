# i2c_usb_pi_pico_adapter

The easy_i2c_adapter allows the user to communicate to I2C devices from a PC.

The hardware interface is simply a Pi Pico board. Program it by holding down the BOOTSEL button on it, then plug the USB connector into the PC, then release the button. A USB drive letter appears on the PC. Drag-and-drop the file in the **pre_built_pico_binary** folder onto the drive letter. The firmware will be transferred within seconds, and will then begin execution. The green LED on the Pi Pico will dimly flicker, when the firmware is successfully running. 

## Features

- 🔌 **Dual Control Modes** - Interactive terminal or programmatic Python control
- 🔍 **I2C Operations** - Read, write, address scanning, repeated starts
- ⚡ **GPIO Control** - Read/write any GPIO pin on the Pico
- 🔢 **Multiple Adapters** - Support for up to 8 Pico boards simultaneously
- 💾 **Memory Backup/Restore** - Utility scripts for I2C EEPROM backup in Intel HEX format
- 🐍 **Python API** - Complete `EasyAdapter` class with extensive I2C device database
- 📡 **Pre-built Firmware** - Ready-to-use .uf2 file included

## Quick Links

- [Connection Diagram](#connection-diagram)
- [Using Multiple Adapters](#using-multiple-adapters)
- [Using GPIO](#using-gpio)
- [Utility Scripts (Backup/Restore I2C Memory)](#utility-scripts)
- [API Documentation](#api-documentation)

## Control Modes

The communication can be controlled in two ways:

(1) Interactively, from a serial console/terminal. This is the interactive (also known as user) mode.

(2) Programmatically, via a programming language on the PC, such as Python. This is the machine-to-machine (M2M) mode. 

Here is an example of interactive control from a serial terminal, demonstrating all the main commands. Note that the command **send+hold** will hold the I2C bus after completion, so that an 'I2C Repeated Start' is performed with the next command.:

<img width="100%" align="left" src="assets\i2c-example-interaction.png">

Another example: type **tryaddr:0x0b** if you wish to see if a device exists at (say) address 0x0b.

You can also read/write any GPIO number on the Pi Pico; for example to read GPIO#5 in interactive mode:

```
ioread:5
```
To write logic level 1 to GPIO6 in interactive mode:

```
iowrite:6,1
```

If you wish to use the M2M mode from Python, import from the **python_pc_interface** folder, the file called **easyadapter.py**. Here are examples of how it can be used:

```
# sending data 0x01, 0x02, 0x03, 0x04 to I2C address 0x50
# append hold=1 to the i2c_write parameters, to hold the I2C bus for I2C repeated starts.

import easyadapter as ea
adapter = ea.EasyAdapter()
result = adapter.init(0)
data = [0x01, 0x02, 0x03, 0x04]
adapter.i2c_write(0x50, data[0], data[1:])

# sending a single byte to address 0x70
val = 0x01;
address = 0x70;
adapter.i2c_write(address, val, [])

# reading four bytes from I2C address 0x50
buffer = adapter.i2c_read(0x50, 4)

# printing data to the screen in a friendly hex+ASCII format
adapter.print_data(buffer)

# trying an I2C address to see if a device at address 0x0b exists
# returns True if the I2C device is present
result = adapter.i2c_try_address(0x0b)

# attaching and using a second adapter board
secondAdapter = adapter.init(1)
buffer = secondAdapter.i2c_read(0x50, 4)

# reading a GPIO port #5
val = adapter.io_read(5)

# writing logic level 1 to GPIO port #6
adapter.io_write(6, 1)
```

# Connection Diagram

Optionally (but recommended) add pull-up resistors to the I2C SDA and SCL lines. I used 10 kohm resistors.

<img width="100%" align="left" src="assets\i2c-adapter-wiring-diag.jpg">

The Easy I2C Adapter is powered from the USB connection. The red and orange connections in the diagram above are 5V and 3.3V outputs, which could be used for powering attached hardware.

The connections labeled BOARD_ID in the diagram can be left disconnected, but, if you wish to use multiple Easy I2C Adapter boards, then you can short some of the BOARD_ID pins to ground, so that each board has a unique identifier. It is described next.

# Using Multiple Adapters
You can connect up to eight Pi Pico boards, and control them all from the same Python code if you wish. Each will automatically get a separate COM port number automatically, so if you're using the interactive mode (i.e. user mode) then you'd simply open two instances of your serial comms software, open to each port.

 If you wish to use the machine-to-machine mode, i.e. such as Python, then for the Python code to be able to identify each board, you'll need to give each Pico board a unique identifier called BOARD_ID in the table below. To do that, set GPIO pins 4..2 as follows:

| BOARD_ID | GPIO4 | GPIO3 | GPIO2 |
|----------|-------|-------|-------|
| 0        | 1     | 1     | 1     |
| 1        | 1     | 1     | 0     |
| 2        | 1     | 0     | 1     |
| 3        | 1     | 0     | 0     |
| 4        | 0     | 1     | 1     |
| 5        | 0     | 1     | 0     |
| 6        | 0     | 0     | 1     |
| 7        | 0     | 0     | 0     |

These three GPIO pins are only read on startup, so if you make changes to these pins, you'll need to power-cycle the Pico boards.

By default, these three GPIO pins 4..2 float high, so the board identifier is 0 by default. For example, if you wish to use a total of two boards, then you could leave the GPIO4..2 pins alone on one board and it will become board ID 0, and if you short GPIO2 to GND then that board will have board ID 1.

In the Python code, you'd use the two boards as follows (this example simply sets a GPIO pin on each adapter):

```
import easyadapter as ea
firstAdapter = ea.EasyAdapter()
secondAdapter = ea.EasyAdapter()
result = firstAdapter.init(0)   # this is board ID 0
result = secondAdapter.init(1)  # this is board ID 1

firstAdapter.io_write(6, 1)  # set GPIO 6 high on the first adapter
secondAdapter.io_write(6,0)  # set GPIO 6 low on the second adapter
```

# Using GPIO
As well as I2C capability, the easy adapter supports GPIO input/output.

Whenever you attempt a GPIO write operation, then the Easy Adapter will automatically set the GPIO pin as an output, and drive the logic level out.

Whenever you attempt a GPIO read operation, then the Easy Adapter will automatically set the GPIO pin as an input, pull it lightly high (so that it doesn't float if it is disconnected), and then read the logic level. 

The GPIO pin remains in the mode that it was set to, until the next GPIO command.

In interactive mode (i.e. serial port console session), use a command such as the following, to set a GPIO pin high or low:

```
iowrite:6,1
iowrite:6,0
```

Use the following interactive mode syntax to read a GPIO pin:

```
ioread:6
```

In the M2M mode (from Python), use the following syntax:

```
import easyadapter as ea
adapter = ea.EasyAdapter()
result = adapter.init(0)
adapter.io_write(6,1)
adapter.io_read(6)
```

# Utility Scripts

The **python_pc_interface** folder includes two powerful utility scripts for backing up and restoring I2C device memory (such as EEPROMs).

## Reading I2C Device Memory (read_memory.py)

The `read_memory.py` script automatically scans the I2C bus for devices and saves their data to files in Intel HEX format.

**Features:**
- Scans I2C addresses from 0x08 to 0x77
- Reads 256 bytes from each detected device
- Saves data in both `.txt` (human-readable) and `.hex` (Intel HEX) formats
- Creates files named by I2C address (e.g., `i2c_device_0x50.hex`)
- Output saved to `i2c_data_output/` directory

**Usage:**
```bash
cd python_pc_interface
python read_memory.py
```

**Example Output:**
```
Initializing EasyAdapter...
EasyAdapter initialized successfully.

Scanning for I2C devices...
Device found at I2C address: 0x50
Device found at I2C address: 0x51

--- Found 2 Device(s) ---
Device: 0x50
Attempting to read 256 bytes...
00: 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 : ................
Data from 0x50 saved to i2c_data_output/i2c_device_0x50.txt
Data from 0x50 saved to i2c_data_output/i2c_device_0x50.hex in Intel HEX format.
```

**Configuration:**
Edit the script to customize:
- `I2C_ADDRESS_RANGE` - Range of addresses to scan (default: 0x08 to 0x77)
- `BYTES_TO_READ` - Number of bytes to read per device (default: 256)
- `OUTPUT_DIR` - Output directory name (default: "i2c_data_output")

## Writing I2C Device Memory (write_memory.py)

The `write_memory.py` script writes Intel HEX files back to I2C devices using page-write operations with acknowledge polling.

**Features:**
- Reads Intel HEX files from `i2c_data_output/` directory
- Automatically detects target I2C address from filename
- Uses page-write operations (16-byte pages for M24C01 EEPROM)
- Implements acknowledge polling for write cycle completion
- Verifies device presence before writing

**Usage:**
```bash
cd python_pc_interface
python write_memory.py
```

**Example Output:**
```
Initializing EasyAdapter...
EasyAdapter initialized successfully.

Found 2 .hex file(s) in 'i2c_data_output'. Attempting to write data...

--- Processing i2c_device_0x50.hex (Target I2C Address: 0x50) ---
Checking for device at I2C address: 0x50
Device found at 0x50. Attempting to write 128 bytes in 16-byte page chunks...
  Writing 16 bytes to Reg 0x00 (Page Write)...
  Page written successfully. Total bytes written: 16/128
  Writing 16 bytes to Reg 0x10 (Page Write)...
  Page written successfully. Total bytes written: 32/128
...
Successfully wrote all 128 bytes to device 0x50.
```

**Configuration:**
Edit the script to customize:
- `INPUT_DIR` - Directory containing .hex files (default: "i2c_data_output")
- `EEPROM_PAGE_SIZE` - Page size for write operations (default: 16 bytes)

**Important Notes:**
- Page size should match your I2C device specifications (e.g., M24C01 = 16 bytes, AT24C256 = 64 bytes)
- The script includes ~500ms timeout for acknowledge polling after each page write
- Ensure correct I2C address is in the filename (e.g., `i2c_device_0x50.hex`)

## Typical Workflow

**Backup an I2C device:**
```bash
python read_memory.py
# Creates i2c_data_output/i2c_device_0x50.hex
```

**Modify the hex file** (optional) using a hex editor or text editor

**Restore to the same or different device:**
```bash
python write_memory.py
# Writes the .hex file back to the device
```

**Clone multiple devices:**
1. Read from source device (creates .hex file)
2. Connect different device at same I2C address
3. Run write script to program it with identical data

# API Documentation

For complete Python API reference and firmware command reference, see **[API_readme.md](API_readme.md)**.

This includes:
- Complete Python `EasyAdapter` class documentation
- All I2C, GPIO, and utility method references
- Firmware command syntax and responses
- M2M protocol details
- Example code snippets

