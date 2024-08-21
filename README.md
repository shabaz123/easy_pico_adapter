# easy_pico_adapter

The easy_i2c_adapter allows the user to communicate to I2C devices from a PC. The hardware interface is simply a Pi Pico board.

The communication can be controlled in two ways:

(1) Interactively, from a serial console/terminal. This is the user mode.

(2) Programmatically, via a programming language on the PC, such as Python. This is the machine-to-machine (M2M) mode. 

Here is an example of interactive control from a serial terminal, demonstrating all the main commands. Note that the command **send+hold** will hold the I2C bus after completion, so that an 'I2C Repeated Start' is performed with the next command.:

<img width="100%" align="left" src="assets\i2c-example-interaction.png">

If you wish to use the M2M mode from Python, import from the **python_pc_interface** folder, the file called **easy_interface.py**. Here is an example of how it can be used:

```
# sending data 0x01, 0x02, 0x03, 0x04 to I2C address 0x50
# append hold=1 to the i2c_write parameters, to hold the I2C bus for I2C repeated starts.
import easy_interface as adapter
result = adapter.init()
data = [0x01, 0x02, 0x03, 0x04]
adapter.i2c_write(0x50, data[0], data[1:])

# reading four bytes from I2C address 0x50
buffer = adapter.i2c_read(0x50, 4)

# printing data to the screen in a friendly hex+ASCII format
from easy_interface import print_data
print_data(buffer)
```

# Connection Diagram

Optionally (but recommended) add pull-up resistors to the I2C SDA and SCL lines. I used 10 kohm resistors.

<img width="100%" align="left" src="assets\i2c-adapter-wiring-diag.jpg">

