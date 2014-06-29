# Copyright 2014 Mark Chilenski
# This program is distributed under the terms of the GNU General Purpose License (GPL).
# Refer to http://www.gnu.org/licenses/gpl.txt

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
# 
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
# 
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time

SERIAL_TRUE = chr(49)  # ASCII "1"
SERIAL_FALSE = chr(48)  # ASCII "0"
SERIAL_ESC = chr(27)  # ASCII "ESC"
VERB_TERMINATOR = '\r'  # terminator used after verbs sent TO the unit

# This dictionary maps between the line the programmer returns upon entering
# automation mode and the name of the programmer:
AUTOMATION_MODE_LINES = {
    'Automation Mode (ESC to exit)\r\n': '2801Prog',
    '2801Prog Automation Mode (ESC to exit)\r\n': '2801Prog',
    '2006Prog Automation Mode (ESC to exit)\r\n': '2006Prog'
}

# This dictionary maps the name of the programmer to the number of bytes:
NUM_BYTES = {
    '2801Prog': 32,
    '2006Prog': 64,
}
NUM_BYTES[None] = max(NUM_BYTES.values())

# This dictionary is the character that each nibble is set to when the chip is
# "erased":
ERASE_CHAR = {
    '2801Prog': '0',
    '2006Prog': '0'
}

# These are the supporting classes and functions:
class InvalidResponseError(Exception):
    """Exception class for invalid responses from the programmer unit."""
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return repr(self.value)

def check_boolean(result, verb='???'):
    """Converts serial logic values to Python values, throws an
    InvalidResponseError if value is not SERIAL_TRUE or SERIAL_FALSE. Takes
    extra argument verb to format error message properly."""
    if result == SERIAL_FALSE:
        return False
    elif result == SERIAL_TRUE:
        return True
    else:
        raise InvalidResponseError('attempt to ' \
                                   + verb +
                                   ' returned invalid value: 0x' + result.encode('hex'))

def ask(port, command):
    """Writes command + VERB_TERMINATOR to port, then reads a line and returns
    the result with the \\r\\n stripped."""
    port.write(command + VERB_TERMINATOR)
    # strip trailing \r\n -- don't use .strip, as it could mess up with raw hex data
    return port.readline()[0:-2]

# These are the backend commands governing what the hardware does.
# Only use these if you know what you are doing with the hardware!
def read_chip_into_buffer(port):
    """Command to read the contents of the chip into the hardware buffer.
    Returns True if operation was successful, False if not."""
    return check_boolean(ask(port, 'r'), verb='read into HW buffer')

def verify_chip_against_buffer(port):
    """Command to verify that the contents of the hardware buffer match the
    contents of the chip. Returns True if hardware buffer matches chip, False
    if hardware buffer and chip differ."""
    return check_boolean(ask(port, 'v'), verb='verify')

def program_chip_from_buffer(port):
    """Command to program the chip using the contents of the hardware buffer.
    Returns True if successful, False otherwise."""
    return check_boolean(ask(port, 'p'), verb='program')

def erase_chip_send(port):
    """Command to erase the chip. Returns True if acknowledged successful,
    False otherwise. A return of True simply means the device attempted to
    erase the chip, a bad chip could still not be zeroed."""
    return check_boolean(ask(port, 'e'), verb='erase')

def fetch_buffer(port, num_bytes):
    """Command to fetch the contents of the hardware buffer. Gets fetched as a
    string representation of the hexadecimal, terminated with \\r\\n. Returns
    the string representation with terminator stripped."""
    port.write('d' + VERB_TERMINATOR)
    value = port.read(size=num_bytes * 2 + 2)  # account for termination
    value = value[0:-2]
    if len(value) != num_bytes * 2:
        raise InvalidResponseError('value read from hardware buffer is of incorrect length. Value read is: ' + value)
    return value

def send_to_buffer(port, inpt):
    """Command to send inpt into the hardware buffer. Puts chip into load mode,
    then sends one nibble at a time. The hardware parrots back the nibbles,
    which are verified."""
    if check_boolean(ask(port, 'l'), 'send to buffer'):
        for char in inpt:
            port.write(char)
            response = port.read(size=1)
            if response != char:
                raise InvalidResponseError('Hardware echoed wrong value during send to buffer!')
    else:
        raise InvalidResponseError("Could not send information to the hardware, " \
                                   "return value for command 'l' incorrect.")

def clear_buffer(port):
    """Command to clear the hardware buffer. Returns True if success,
    False otherwise."""
    return check_boolean(ask('c'), 'clear')

# These are the general-use commands:
def enter_automation_mode(port):
    """Command to put programmer into automation mode. Needs special handling
    to clear the serial buffer properly independent of what was done before.
    Looks for the automation mode usage information to proceed."""
    port.write(SERIAL_ESC)  # reset microcontroller
    time.sleep(0.5)  # wait for serial to catch up
    port.flushInput()  # flush whatever junk was waiting in the input buffer from previous actions
    time.sleep(0.1)
    port.write('a' + VERB_TERMINATOR)  # send command for automation mode
    time.sleep(0.2)
    port.readline()  # read and discard parroted response
    time.sleep(0.2)
    line = port.readline()  # read (what should be) usage prompt
    
    # check usage prompt -- if it doesn't print this, it didn't go into
    # automation mode properly, or the buffer is out of sync.
    if line not in AUTOMATION_MODE_LINES:
        raise InvalidResponseError('Never got automation handshake from unit!')
    else:
        return AUTOMATION_MODE_LINES[line]

def exit_automation_mode(port):
    """Command to exit automation mode by sending ESC."""
    port.write(SERIAL_ESC)

def read_chip(port, num_bytes):
    """Command to read what is in the chip. Behind the scenes it reads the
    chip into the hardware buffer, then fetches and returns the hardware buffer."""
    read_chip_into_buffer(port)
    return fetch_buffer(port, num_bytes)

def verify_chip(port, inpt):
    """Command to verify what is in the chip against the given input. Behind
    the scenes it sends the input to the hardware buffer, then verifies the
    chip against the hardware buffer."""
    send_to_buffer(port, inpt.upper())
    return verify_chip_against_buffer(port)

def program_chip(port, inpt):
    """Command to program the chip with the given input. Behind the scenes it
    sends the input into the hardware buffer, programs the chip from the
    hardware buffer then returns the result of verifying the chip against the
    hardware buffer.
    
    Returns True if the final content of the chip matches the input value,
    False otherwise (indicating a failed write/broken chip)."""
    send_to_buffer(port, inpt.upper())
    program_chip_from_buffer(port)
    return verify_chip_against_buffer(port)

def erase_chip(port, num_bytes):
    """Erases the chip. Returns what is read from the chip (in case the erase
    failed and this is in fact non-zero)."""
    erase_success = erase_chip_send(port)
    if not erase_success:
        raise InvalidResponseError("Command 'e' returned false.")
    return read_chip(port, num_bytes)
