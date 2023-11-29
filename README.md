# Telink Zigbee serial flash tool

> **NOTE:** This project is not thoroughly tested yet!

Reliably read, write and erase flash memory for Telink Zigbee boards (eg. 8258) with just a USB-to-serial converter.

## Connections

![](/docs/connections.png)
![](/docs/connection_example.jpg)

## Usage

Clone or download the repository and execute Telink_Tools.py in a system with Python installed.

## Examples

### Backup entire flash

1 MB flash

    Telink_Tools.py -p COM3 read_flash 0 1048576 dump.bin

512 KB flash

    Telink_Tools.py -p COM3 read_flash 0 524288 dump.bin

### Burn firmware at address 0

    Telink_Tools.py -p COM3 write_flash 0 motionSensor_TS0202.bin

### Erase first 3 flash sectors (aka 12 KB. 1 sector = 4 KB)

    Telink_Tools.py -p COM3 erase_flash 0 3

## Flash layout

![](/docs/flash_allocation.PNG)
![](/docs/flash_description.PNG)

## Credits

https://github.com/Ai-Thinker-Open/TBXX_Flash_Tool
https://github.com/Ai-Thinker-Open/Telink_825X_SDK/tree/master/example/bootloader
https://github.com/pvvx/TlsrComProg825x