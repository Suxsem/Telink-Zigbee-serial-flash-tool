#coding=utf-8
import argparse
import base64
import binascii
import copy
import hashlib
import inspect
import io
import os
import shlex
import struct
import sys
import time
import zlib
import string
from UartBoot import uart_boot

# edit by Suxsem 28/11/2023

try:
    import serial
except ImportError:
    print("Pyserial is not installed for %s. Check the README for installation instructions." % (sys.executable))
    raise

# check 'serial' is 'pyserial' and not 'serial' https://github.com/espressif/esptool/issues/269
try:
    if "serialization" in serial.__doc__ and "deserialization" in serial.__doc__:
        raise ImportError("""
Telink_Tools.py depends on pyserial, but there is a conflict with a currently installed package named 'serial'.
You may be able to work around this by 'pip uninstall serial; pip install pyserial' \
but this may break other installed Python software that depends on 'serial'.
There is no good fix for this right now, apart from configuring virtualenvs. \
See https://github.com/espressif/esptool/issues/269#issuecomment-385298196 for discussion of the underlying issue(s).""")
except TypeError:
    pass  # __doc__ returns None for pyserial

try:
    import serial.tools.list_ports as list_ports
except ImportError:
    print("The installed version (%s) of pyserial appears to be too old for Telink_Tools.py (Python interpreter %s). "
          "Check the README for installation instructions." % (sys.VERSION, sys.executable))
    raise

__version__ = "0.2 dev Suxsem"

PYTHON2 = sys.version_info[0] < 3  # True if on pre-Python 3

CMD_GET_VERSION = 0x00
CMD_WRITE_FLASH = 0x01
CMD_READ_FLASH  = 0x02
CMD_ERASE_FLASH = 0x03
CMD_CHIP_INFO   = 0x04

RES_WRITE_FLASH = 'OK_01'
RES_READ_FLASH  = 'OK_02'
RES_ERASE_FLASH = 'OK_03'
RES_CHIP_INFO   = 'OK_04'


def tl_open_port(port_name):
    _port = serial.serial_for_url(port_name)

    _port.baudrate = 500000
    _port.timeout = 0.3

    return _port

def get_port_list():
    return list(serial.tools.list_ports.comports())

def uart_read(_port):
    data = ''
    while _port.inWaiting() > 0:
        try:
            data += _port.read_all().decode(encoding='utf-8')
        except Exception as e:
            break
    return str(data)

def uart_write(_port, data):
    _port.flushInput()
    _port.flushOutput()

    _port.write(data)

def wait_result(_port, res, time_out = 200):
    wait_c = 0
    result = ''
    while True:
        result += uart_read(_port)
        if(len(result) > 5): 
            break
        time.sleep(0.01)
        wait_c += 1
        if(wait_c > time_out): break

    if result.find(res) == -1:
        return False
    return True

def telink_flash_write(_port, addr, data):
    cmd_len = len(data) + 5

    error_c = 3
    while error_c > 0:
        uart_write(_port, struct.pack('>BHIB', CMD_WRITE_FLASH, cmd_len, addr, 0) + data)
        if wait_result(_port, RES_WRITE_FLASH): return True
        time.sleep(0.5)
        error_c-=1
    return False

def telink_flash_read(_port, addr, len_b):
    wait_c = 0 
    uart_write(_port, struct.pack('>BHIB', CMD_READ_FLASH, 5, addr, len_b))
    time.sleep(0.01)

    data = bytes()
    while True :
        if _port.inWaiting() > 0:
            staging = _port.read_all()
            data += staging
        if str(data[-7:]).find(RES_READ_FLASH) >= 0:
            return True, data[:len_b]
        time.sleep(0.01)
        wait_c += 1
        if(wait_c > 500): break

    return False, 0

def telink_flash_erase(_port, addr, len_t):

    uart_write(_port, struct.pack('>BHIB', CMD_ERASE_FLASH, 5, addr, len_t))

    sys.stdout.write('\033[?25l-')
    sys.stdout.flush()
    for i in range((int)(len_t/3)):
        time.sleep(0.1) #wait erase complect
        m = i%4
        if m == 1: sys.stdout.write("\b\\")
        elif m == 2: sys.stdout.write("\b|")
        elif m == 3: sys.stdout.write("\b/")
        elif m == 0: sys.stdout.write("\b-")
        sys.stdout.flush()

    sys.stdout.write("\b \b\033[?25h");sys.stdout.flush()

    return wait_result(_port, RES_ERASE_FLASH)

def connect_chip(_port):

    if not uart_boot(_port):
        return False

    time.sleep(0.1)

    _port.baudrate = 921600

    time.sleep(0.1)

    uart_write(_port, struct.pack('>BH', CMD_GET_VERSION, 0))

    if wait_result(_port, "S"):
        return True
    return False

def get_chip_info(_port):
   
    uart_write(_port, struct.pack('>BH', CMD_CHIP_INFO, 0))
    time.sleep(0.05)
    return _port.read_all().decode(encoding='utf-8')
       
def erase_flash(_port, args):

    flash_addr = int(args.addr, 0)
    sector_len = int(args.len,  0)

    sys.stdout.write("Erase Flash at " + args.addr + " " + args.len + " Sector ... ... ")
    sys.stdout.flush()

    if telink_flash_erase(_port, flash_addr, sector_len):
        print("\033[3;32mOK!\033[0m")
    else:
        print("\033[3;31mFail!\033[0m")
        
    print("")
    _port.close()

def read_flash(_port, args):
    
    print("Reading to binary file: "  + args.filename)

    fo = open(args.filename, "wb")
    firmware_addr = int(args.addr, 0)
    current_addr = firmware_addr
    firmware_size = int(args.len,  0)

    bar_len = 50
    
    while True:

        data_len = min(128, firmware_size-(current_addr-firmware_addr))
        if data_len < 1: break
        
        res, data = telink_flash_read(_port, current_addr, data_len)

        if not res:
            print("\033[3;31mRead Fail!\033[0m")
            break
            
        fo.write(data)

        current_addr += data_len

        percent = (int)((current_addr - firmware_addr) *100 / firmware_size)
        sys.stdout.write("\r" + str(percent) + "% [\033[3;32m{0}\033[0m{1}]".format(">"*(int)(percent*bar_len/100),"="*(bar_len-(int)(percent*bar_len/100))))
        sys.stdout.flush()

    print("")
    fo.close()
    _port.close()

def write_flash(_port, args):
    
    print("Writing binary file: "  + args.filename)

    fo = open(args.filename, "rb")
    firmware_addr = int(args.addr, 0)
    current_addr = firmware_addr
    firmware_size = os.path.getsize(args.filename)

    bar_len = 50

    while True:
        data = fo.read(256)
        if len(data) < 1: break 

        if not telink_flash_write(_port, current_addr, data):
            print("\033[3;31mWrite Fail!\033[0m")
            break

        current_addr += len(data)

        percent = (int)((current_addr - firmware_addr) *100 / firmware_size)
        sys.stdout.write("\r" + str(percent) + "% [\033[3;32m{0}\033[0m{1}]".format(">"*(int)(percent*bar_len/100),"="*(bar_len-(int)(percent*bar_len/100))))
        sys.stdout.flush()

    print("")
    fo.close()
    _port.close()

def burn_triad(_port, args):
    #TODO fix for 1M flash
    print("TODO fix for 1M flash")
    return
    
    data = struct.pack('<I', int(args.productID)) + bytearray.fromhex(args.MAC) + bytearray.fromhex(args.Secret)
    if(len(data) != 26):
        print("\033[3;31mTriad Error!\033[0m")
        return

    print("Your productID =  " + args.productID )
    print("Your MAC =   " + args.MAC )
    print("Your Secret =   " + args.Secret )

    sys.stdout.write("Erase Flash at 0x78000 len 4 KB ... ... ")
    sys.stdout.flush()

    if not telink_flash_erase(_port, 0x78000, 1):
        print("\033[3;31mFail!\033[0m")
        return
    print("\033[3;32mOK!\033[0m")

    sys.stdout.write("Burn Triad to 0x78000 ... ... ")
    sys.stdout.flush()

    if not telink_flash_write(_port, 0x78000, data):
        print("\033[3;31mFail!\033[0m")
        return
    print("\033[3;32mOK!\033[0m")

def dump_chip_info(_port):
    info = get_chip_info(_port)

    if len(info) != 27:
        print("Get Chip Info Fail!!!")
        return
    
    loaderVersion = info[6:10]
    chipVersionId =  info[11:13]
    chipProdId =  info[14:18]
    if chipProdId == "5562":
        chipProdId += " (825x ?)"
    jedecId = info[19:25]
    flashsizeKB = ((1<<int(jedecId[4:6], 16))>>10)
    
    print("Loader version: " + loaderVersion +
        " - Chip version: " + chipVersionId +
        " - Chip product: " + chipProdId +
        " - Flash ID: " + jedecId +
        " - Flash size: " + str(flashsizeKB) + " KB"
    )
    print("")

def main(custom_commandline=None):

    parser = argparse.ArgumentParser(description='Telink_Tools.py v%s - Telink Zigbee serial flash tool - edit by Suxsem' % __version__)

    parser.add_argument('--port','-p', help='Serial port device', default='ttyUSB0')

    subparsers = parser.add_subparsers(dest='operation', help='Run Telink_Tools.py -h for additional help')
        
    write_flash = subparsers.add_parser('write_flash', help='Write data to flash')
    write_flash.add_argument('addr', help='write start addr')
    write_flash.add_argument('filename', help='source binary file')

    read_flash = subparsers.add_parser('read_flash', help='Read flash')
    read_flash.add_argument('addr',  help='read start addr')
    read_flash.add_argument('len',  help='len to read')
    read_flash.add_argument('filename', help='destination binary file')

    erase_flash = subparsers.add_parser('erase_flash', help='erase 4K (a sector)')
    erase_flash.add_argument('addr', help='erase start addr')
    erase_flash.add_argument('len',  help='number of sectors to erase')

    args = parser.parse_args(custom_commandline)

    print('Telink_Tools.py v%s' % __version__)
    
    if args.operation is None:
        parser.print_help()
        sys.exit(1)

    operation_func = globals()[args.operation]

    sys.stdout.write("Open " + args.port + " ... ... ")
    sys.stdout.flush()
    
    try:
        _port = tl_open_port(args.port)
    except Exception:
        print("\033[3;31mFail!\033[0m")
        return

    sys.stdout.write('\033[3;32mSuccess!\033[0m\r\nConnect Board ... ...')
    sys.stdout.flush()

    if connect_chip(_port):
        print("\033[3;32mSuccess!\033[0m")
        dump_chip_info(_port)
        operation_func(_port,args)
    else:
        print("\033[3;31mFail!\033[0m")

        print("\r\n**********************************")
        print("\033[3;31m***\033[3;32mPlease check the connection!\033[3;31m***\033[0m\r\n")
        
        print("USB-TTL   <-------->     TB Moudle")
        print("                                  ")
        print("              / ------470------SWS")
        print("Tx ----------+                    ")
        print("              \\ ------470------Rx ")
        print("Rx ----------------------------Tx ")
        print("RTS----------------------------RST")


    _port.close()

def _main():

    main()

if __name__ == '__main__':
    _main()