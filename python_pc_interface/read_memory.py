import easyadapter as ea
import os

# --- Configuration ---
# Define the range of I2C addresses to scan (from 0x08 to 0x77).
#I2C_ADDRESS_RANGE = range(0x08, 0x78)
I2C_ADDRESS_RANGE = range(0x01, 0x80)

# Define the number of bytes to read from each detected device.
BYTES_TO_READ = 256

# Define base output directory for saving files.
# This will create a 'i2c_data_output' folder in the script's directory.
OUTPUT_DIR = "i2c_data_output"

#COM_Port = 0
COM_Port = "COM15"

# --- Helper Functions for File Operations ---

def _ensure_output_directory(directory):
    """Ensures the output directory exists."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created output directory: {directory}")

def _calculate_checksum(record_bytes):
    """Calculates the Intel HEX checksum."""
    total_sum = sum(record_bytes)
    checksum = (256 - (total_sum % 256)) % 256
    return checksum

def _create_hex_record(byte_count, address, record_type, data_bytes=None):
    """Creates a single Intel HEX record line."""
    if data_bytes is None:
        data_bytes = []
    
    # Construct the record bytes list for checksum calculation
    record_parts = [byte_count, (address >> 8) & 0xFF, address & 0xFF, record_type]
    record_parts.extend(data_bytes)
    
    checksum = _calculate_checksum(record_parts)
    
    # Format the record string
    hex_line = f":{byte_count:02X}{address:04X}{record_type:02X}"
    for byte_data in data_bytes:
        hex_line += f"{byte_data:02X}"
    hex_line += f"{checksum:02X}"
    
    return hex_line

def _save_data_to_txt(directory, device_address, data_buffer):
    """
    Saves data from a buffer to a .txt file, named after the device address,
    including the 0x prefix.
    """
    # Filename will now include the '0x' prefix: i2c_device_0x4A.txt
    filename = os.path.join(directory, f"i2c_device_{hex(device_address)}.txt")
    try:
        with open(filename, 'w') as f: # Use 'w' to create/overwrite a new file for each device
            f.write(f"--- Data from I2C device at address: {hex(device_address)} ---\n")

            # Write hexadecimal representation
            hex_data = ' '.join([f'{b:02x}' for b in data_buffer])
            f.write(f"Hex: {hex_data}\n")

            # Attempt to write ASCII representation
            try:
                ascii_data = data_buffer.decode('utf-8', errors='ignore')
                f.write(f"ASCII: {ascii_data}\n")
            except UnicodeDecodeError:
                f.write("ASCII: Could not decode as UTF-8\n")
            
            f.write("\n") # Add a newline for separation
        print(f"Data from {hex(device_address)} saved to {filename}")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

def _save_data_to_intel_hex_file(directory, device_address, data_buffer):
    """
    Saves data from a buffer to a .hex file in Intel HEX (16-bit address) format,
    named after the device address, including the 0x prefix.
    """
    # Filename will now include the '0x' prefix: i2c_device_0x4A.hex
    filename = os.path.join(directory, f"i2c_device_{hex(device_address)}.hex")
    try:
        with open(filename, 'w') as f: # Use 'w' to create/overwrite a new file for each device
            # Create an Extended Linear Address Record (Type 04)
            segment_address = device_address 
            ela_record = _create_hex_record(0x02, 0x0000, 0x04, [(segment_address >> 8) & 0xFF, segment_address & 0xFF])
            f.write(ela_record + '\n')
            
            # Write data records (Type 00)
            current_offset = 0
            max_data_bytes_per_record = 16 

            for i in range(0, len(data_buffer), max_data_bytes_per_record):
                chunk = data_buffer[i : i + max_data_bytes_per_record]
                data_record = _create_hex_record(len(chunk), current_offset, 0x00, list(chunk))
                f.write(data_record + '\n')
                current_offset += len(chunk)
            
            # Add the End-of-File record (Type 01) at the end of each HEX file
            eof_record = _create_hex_record(0x00, 0x0000, 0x01) 
            f.write(eof_record + '\n')

        print(f"Data from {hex(device_address)} saved to {filename} in Intel HEX format.")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

# --- Main I2C Scan and Read Logic ---

def main():
    """
    Main function to initialize the adapter, scan I2C devices,
    read data, and save to separate files.
    """
    adapter = ea.EasyAdapter()

    print("Initializing EasyAdapter...")
    # Two ways to initialize:
    # 1. Auto-detect by board number: adapter.init(0)
    # 2. Direct COM port: adapter.init("COM15")
    init_result = adapter.init(COM_Port) # Using direct COM port
    if init_result:
        print("EasyAdapter initialized successfully.")
    else:
        print("Failed to initialize EasyAdapter. Please check your connection and drivers.")
        return 

    # Ensure the output directory exists
    _ensure_output_directory(OUTPUT_DIR)

    print("\nScanning for I2C devices...")
    found_devices = []
    for address in I2C_ADDRESS_RANGE:
        print(f"Trying address {hex(address)}...", end='\r')
        if adapter.i2c_try_address(address):
            print(f"Device found at I2C address: {hex(address)}")
            found_devices.append(address)

    print()  # Clear the scanning line
    if not found_devices:
        print("No I2C devices found in the specified range.")
    else:
        print(f"\n--- Found {len(found_devices)} Device(s) ---")
        for device_address in found_devices:
            print(f"Device: {hex(device_address)}")
            print(f"Attempting to read {BYTES_TO_READ} bytes...")
            try:
                buffer = adapter.i2c_read(device_address, BYTES_TO_READ)
                if buffer:
                    adapter.print_data(buffer) # Print data to console
                    
                    # Save data to separate .txt and .hex files for each device
                    _save_data_to_txt(OUTPUT_DIR, device_address, buffer)
                    _save_data_to_intel_hex_file(OUTPUT_DIR, device_address, buffer)
                else:
                    print(f"No data read from device {hex(device_address)} (buffer is empty).")
            except Exception as e:
                print(f"Error reading from device {hex(device_address)}: {e}")
            print("-" * 30) # Separator for readability

    print(f"\nScan complete. Data for each device saved in the '{OUTPUT_DIR}' directory.")

if __name__ == "__main__":
    main()