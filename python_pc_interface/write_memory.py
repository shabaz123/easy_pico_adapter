import easyadapter as ea
import os
import re # For regular expressions to parse filenames
import time # Import time for delays/polling

# --- Configuration ---
# Define the directory where your saved .hex files are located.
INPUT_DIR = "i2c_data_output"
# Define the EEPROM page size for the M24C01
EEPROM_PAGE_SIZE = 16 # M24C01 has 16-byte pages

# --- Intel HEX Parser Functions ---

def _calculate_checksum(record_bytes):
    """Calculates the Intel HEX checksum."""
    total_sum = sum(record_bytes)
    checksum = (256 - (total_sum % 256)) % 256
    return checksum

def _parse_hex_line(line):
    """Parses a single Intel HEX line into its components."""
    if not line.startswith(':'):
        raise ValueError("Intel HEX line must start with ':'")

    try:
        # Remove colon, then parse parts
        record_str = line[1:].strip()
        
        byte_count = int(record_str[0:2], 16)
        address = int(record_str[2:6], 16)
        record_type = int(record_str[6:8], 16)
        data_str = record_str[8:8 + byte_count * 2]
        checksum_str = record_str[8 + byte_count * 2:]
        
        data_bytes = []
        for i in range(0, len(data_str), 2):
            data_bytes.append(int(data_str[i:i+2], 16))
        
        checksum = int(checksum_str, 16)

        # Verify checksum (optional but highly recommended for data integrity)
        calculated_checksum = _calculate_checksum([byte_count, (address >> 8) & 0xFF, address & 0xFF, record_type] + data_bytes)
        if calculated_checksum != checksum:
            print(f"Warning: Checksum mismatch for line: {line.strip()}. Expected {calculated_checksum:02X}, got {checksum:02X}")
            
        return {
            "byte_count": byte_count,
            "address": address,
            "record_type": record_type,
            "data": bytearray(data_bytes),
            "checksum": checksum
        }
    except (ValueError, IndexError) as e:
        raise ValueError(f"Failed to parse Intel HEX line '{line.strip()}': {e}")


def _load_data_from_intel_hex(filepath):
    """
    Loads data and extracts the intended I2C device address from an Intel HEX file.
    Returns (i2c_device_address, data_buffer).
    """
    i2c_device_address = None
    
    # Use a dictionary to store data by absolute linear address.
    data_map = {} 
    current_linear_address_segment = 0 

    try:
        with open(filepath, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue 

                record = _parse_hex_line(line)

                if record["record_type"] == 0x04: # Extended Linear Address Record
                    if record["byte_count"] != 2:
                        print(f"Warning: Type 04 record on line {line_num} in {filepath} has unexpected byte count ({record['byte_count']}). Expected 2.")
                        continue
                    upper_16_bits = (record["data"][0] << 8) | record["data"][1]
                    current_linear_address_segment = upper_16_bits << 16 
                    
                    i2c_device_address = upper_16_bits 
                    
                elif record["record_type"] == 0x00: # Data Record
                    abs_address = current_linear_address_segment + record["address"]
                    
                    for i, byte_val in enumerate(record["data"]):
                        data_map[abs_address + i] = byte_val

                elif record["record_type"] == 0x01: # End-of-File Record
                    break 
                else:
                    print(f"Warning: Unknown record type {record['record_type']:02X} on line {line_num} in {filepath}")
        
        if not data_map:
            return i2c_device_address, bytearray() 

        min_addr = min(data_map.keys())
        max_addr = max(data_map.keys())
        
        data_buffer = bytearray()
        for addr in range(min_addr, max_addr + 1):
            data_buffer.append(data_map.get(addr, 0xFF)) 
        
        return i2c_device_address, data_buffer

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None, None
    except ValueError as e:
        print(f"Error parsing Intel HEX file {filepath}: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred while reading {filepath}: {e}")
        return None, None

# --- Main Write Logic (`main` function) ---

def main():
    """
    Main function to read .hex files from the input directory,
    identify devices, and write data to them via EasyAdapter using page writes.
    """
    adapter = ea.EasyAdapter()

    print("Initializing EasyAdapter...")
    init_result = adapter.init(0) 
    if init_result:
        print("EasyAdapter initialized successfully.")
    else:
        print("Failed to initialize EasyAdapter. Please check your connection and drivers.")
        print("Cannot proceed with writing data without a connected adapter.")
        return 

    if not os.path.isdir(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' does not exist.")
        return

    hex_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.hex')]

    if not hex_files:
        print(f"No .hex files found in the directory: {INPUT_DIR}")
        return

    print(f"\nFound {len(hex_files)} .hex file(s) in '{INPUT_DIR}'. Attempting to write data...")

    for hex_filename in hex_files:
        filepath = os.path.join(INPUT_DIR, hex_filename)
        
        match = re.search(r"0x([0-9a-fA-F]+)", hex_filename)
        if not match:
            print(f"Skipping {hex_filename}: Could not extract I2C address (e.g., '0xXX') from filename.")
            continue
        
        try:
            device_address_from_filename = int(match.group(0), 16) 
        except ValueError:
            print(f"Skipping {hex_filename}: Invalid hexadecimal address in filename.")
            continue

        print(f"\n--- Processing {hex_filename} (Target I2C Address: {hex(device_address_from_filename)}) ---")

        i2c_address_from_hex_content, data_to_write = _load_data_from_intel_hex(filepath)

        if i2c_address_from_hex_content is None and data_to_write is None:
            print(f"Failed to load or parse data from {filepath}. Skipping write operation for this file.")
            continue
        
        if not data_to_write: 
            print(f"No data to write from {filepath}. Skipping write operation for this file.")
            continue

        if i2c_address_from_hex_content is not None and i2c_address_from_hex_content != device_address_from_filename:
            print(f"Warning: I2C address found in HEX file content ({hex(i2c_address_from_hex_content)}) "
                  f"does not match filename ({hex(device_address_from_filename)}). "
                  f"Proceeding with filename address for device detection.")
        
        print(f"Checking for device at I2C address: {hex(device_address_from_filename)}")
        if adapter.i2c_try_address(device_address_from_filename):
            print(f"Device found at {hex(device_address_from_filename)}. Attempting to write {len(data_to_write)} bytes in {EEPROM_PAGE_SIZE}-byte page chunks...")
            
            total_bytes_written = 0
            write_successful_overall = True

            # Iterate through the data in page-sized chunks
            # Ensure the offset is aligned to page boundaries
            for offset in range(0, len(data_to_write), EEPROM_PAGE_SIZE):
                current_register_address = offset
                # Slice the data to get the current page's chunk
                # This ensures the chunk size is at most EEPROM_PAGE_SIZE
                page_data_chunk = data_to_write[offset : offset + EEPROM_PAGE_SIZE]
                
                if not page_data_chunk:
                    continue # Should not happen with range step, but good defensive check

                print(f"  Writing {len(page_data_chunk)} bytes to Reg 0x{current_register_address:02X} (Page Write)...")
                
                try:
                    # byte1 is the current register address (start of the page)
                    # data is the chunk payload (up to EEPROM_PAGE_SIZE bytes)
                    write_success = adapter.i2c_write(
                        device_address_from_filename, 
                        current_register_address, 
                        list(page_data_chunk) 
                    )
                    
                    if write_success:
                        total_bytes_written += len(page_data_chunk)
                        print(f"  Page written successfully. Total bytes written: {total_bytes_written}/{len(data_to_write)}")

                        # --- Implement Acknowledge Polling to wait for t_WC ---
                        # The M24C01 datasheet specifies ~5ms for t_WC.
                        # Poll by repeatedly trying to address the device until it ACKs.
                        poll_timeout_ms = 500 # Maximum time to poll before giving up (e.g., 500ms)
                        poll_interval_ms = 1  # How frequently to check (e.g., every 1ms)
                        polls_attempted = 0
                        max_polls = poll_timeout_ms // poll_interval_ms

                        polled_ok = False
                        while polls_attempted < max_polls:
                            if adapter.i2c_try_address(device_address_from_filename):
                                polled_ok = True
                                break # Device ACKed, internal write cycle finished
                            time.sleep(poll_interval_ms / 1000.0) # Convert ms to seconds for time.sleep
                            polls_attempted += 1
                        
                        if not polled_ok:
                            print(f"  Warning: Device 0x{device_address_from_filename:02X} did not acknowledge after page write (polling timeout).")
                            write_successful_overall = False
                            break # Stop on polling failure
                        # --- End Acknowledge Polling ---

                    else:
                        print(f"  Failed to write page to device {hex(device_address_from_filename)} at Reg 0x{current_register_address:02X}. EasyAdapter reported failure.")
                        write_successful_overall = False
                        break # Stop on first write failure
                except Exception as e:
                    print(f"  An unexpected error occurred during page write to {hex(device_address_from_filename)} at Reg 0x{current_register_address:02X}: {e}")
                    write_successful_overall = False
                    break # Stop on exception

            if write_successful_overall:
                print(f"Successfully wrote all {total_bytes_written} bytes to device {hex(device_address_from_filename)}.")
            else:
                print(f"Finished processing {hex_filename} with errors during write operation.")
        else:
            print(f"Device not found at {hex(device_address_from_filename)}. Cannot write data.")
        print("=" * 60) 

    print("\nAll HEX files processed. Script finished.")

if __name__ == "__main__":
    main()