# easy_pico_adapter

The easy_i2c_adapter allows the user to communicate to I2C devices from a PC.

The hardware interface is simply a Pi Pico board. Program it by holding down the BOOTSEL button on it, then plug the USB connector into the PC, then release the button. A USB drive letter appears on the PC. Drag-and-drop the file in the **pre_built_pico_binary** folder onto the drive letter. The firmware will be transferred within seconds, and will then begin execution. The green LED on the Pi Pico will dimly flicker, when the firmware is successfully running. 

The communication can be controlled in two ways:

(1) Interactively, from a serial console/terminal. This is the user mode.

(2) Programmatically, via a programming language on the PC, such as Python. This is the machine-to-machine (M2M) mode. 

Here is an example of interactive control from a serial terminal, demonstrating all the main commands. Note that the command **send+hold** will hold the I2C bus after completion, so that an 'I2C Repeated Start' is performed with the next command.:

<img width="100%" align="left" src="assets\i2c-example-interaction.png">

Another example: type **tryaddr:0x0b** if you wish to see if a device exists at (say) address 0x0b.

You can also read/write any GPIO number on the Pi Pico; for example to GPIO#5, and write logic level 1 to GPIO6:
ioread:5
iowrite:6,1

If you wish to use the M2M mode from Python, import from the **python_pc_interface** folder, the file called **easyadapter.py**. Here is an example of how it can be used:

```
# sending data 0x01, 0x02, 0x03, 0x04 to I2C address 0x50
# append hold=1 to the i2c_write parameters, to hold the I2C bus for I2C repeated starts.

import easyadapter as ea
adapter = ea.EasyAdapter()
result = adapter.init(0)
data = [0x01, 0x02, 0x03, 0x04]
adapter.i2c_write(0x50, data[0], data[1:])

# reading four bytes from I2C address 0x50
buffer = adapter.i2c_read(0x50, 4)

# printing data to the screen in a friendly hex+ASCII format
from easy_interface import print_data
print_data(buffer)

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

