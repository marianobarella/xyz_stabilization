# -*- coding: utf-8 -*-
"""
Created on Tue March 21, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import sys
import glob
import serial
import re
import time
from pylablib.devices.Thorlabs.kinesis import MFF as motoFlipper

#=====================================

#  Serial Communication Function Definitions

#=====================================
# after sending the instruction, number of bytes
# to read during serial communication (max length message received)
# modify if it's not enoough
bytesToRead = 200
# COM ports
COM_port_oxxius = 'COM4'
COM_port_flipper_Thorlas = 'COM1'
COM_port_toptica = 'COM6'

def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (IOError, serial.SerialException):
            pass
    return result

def sendCommand(command, serialInstace, debug_mode):
    waitingForReply = False

    if waitingForReply == False:
        # add carriage return and line feed
        full_command = command
        # send command, binary encoded
        serialInstace.write(full_command.encode())
        if debug_mode:
            print("Command sent:", command)
        waitingForReply = True
        
    if waitingForReply == True:
        # if IN buffer empty, pass
        # if there's something, read
        while serialInstace.inWaiting() == 0:
            pass
        reply = serialInstace.read(bytesToRead)
        reply_utf8 = reply.decode('utf-8')
        if debug_mode:
            print("Reply: ", reply_utf8)
        waitingForReply = False
        # serialInstace.flush() # clear channel
        # serialInstace.reset_input_buffer() # clear channel
    return reply_utf8

def initSerial(port, baudRate):
    ser = serial.Serial(port, baudRate, timeout = 0.1) # timeout in s
    if ser.is_open:
        print('Serial port ' + port + ' opened. Baud rate: ' + str(baudRate))
    else:
        print('Serial port ' + port + ' has NOT been opened')
    return ser

def closeSerial(serialInstance):
    print('Closing serial communication...')
    serialInstance.close()
    time.sleep(0.2) # wait until serial comm is closed
    return

#=====================================

# Laser Class Definitions

#=====================================

class oxxius_laser(object):
    def __init__(self, debug_mode):
        # Parameters for Oxxis 532 green laser
        # Warning: laser has to be configured to communicate trhough serial port
        # for this, mode "CDC 1" has to be set from Oxxius software. 
        # This has been done for the first time probably. Read User manual page 44.
        self.baudRate = 38400
        self.serialPort = COM_port_oxxius
        self.serialInstance = initSerial(self.serialPort, self.baudRate)
        self.debug_mode = debug_mode

    def ask_model(self):
        command = 'INF?\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def base_temp(self):
        command = 'BT?\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def voltage(self):
        command = 'VA?\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def alarm(self):
        command = 'AL?\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def hours(self):
        command = '?HH\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n') + ' h'
        return reply_clean_string
    
    def status(self):
        command = 'DL?\n'
        replyDL = sendCommand(command, self.serialInstance, self.debug_mode)
        replyDL_clean_string = replyDL.rstrip('\r\n')
        command = '?STA\n'
        replySTA = sendCommand(command, self.serialInstance, self.debug_mode)
        replySTA_clean_string = replySTA.rstrip('\r\n')
        if replySTA_clean_string == '1':
            replySTA_text = 'Warming-up'
        elif replySTA_clean_string == '2':
            replySTA_text = 'Standing-by'
        elif replySTA_clean_string == '3':
            replySTA_text = 'Emmision on'
        elif replySTA_clean_string == '5':
            replySTA_text = 'Alarm present'
        elif replySTA_clean_string == '7':
            replySTA_text = 'Searching for SLM point'
        else:
            replySTA_text = 'Error. Unknown status. ?STA command output unknown.'
        return replyDL_clean_string + ', ' + replySTA_text
    
    def temp_regulation(self):
        command = 'T?\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n')
        if reply_clean_string == '1':
            print('Temp regulation active')
        else:
            print('Temp regulation inactive')
        return reply_clean_string
    
    def ask_power(self):
        command = 'IP?\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def shutter(self, action):
        if action == 'close':
            command = 'SH 0\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('532 OFF')
        elif action == 'open':
            command = 'SH 1\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('532 ON')
        else:
            print('Action was not determined. For precaution: shutter has been closed.')
            command = 'SH 0\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)    
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def check_comm(self):
        flag_open = self.serialInstance.is_open
        if flag_open:
            print('Serial instance is open')
        else:
            print('Serial instance is NOT open')
        return flag_open
    
    def close(self):
        time.sleep(0.1)
        print('Closing 532 laser communication. Clearing serial buffer...')
        self.serialInstance.flush() # empty serial buffer
        self.shutter('close')
        closeSerial(self.serialInstance)

class toptica_laser(object):
    def __init__(self, debug_mode):
        # Parameters for Toptica 488 blue laser
        self.baudRate = 115200
        self.serialPort = COM_port_toptica
        self.serialInstance = initSerial(self.serialPort, self.baudRate)
        self.debug_mode = debug_mode
        self.initialize()
        
    def initialize(self):
        command = 'ini la\n\r'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        return reply

    def ask_model(self):
        command = 'id\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.rstrip('\r\nCMD>')
        return reply_clean_string
    
    def base_temp(self):
        command = 'sh temp\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        where = re.search('TEMP = \d\d\d.\d  C', reply)
        reply_clean_string = reply[where.start():where.end()]
        temp = reply_clean_string[7:12] + ' C'
        return temp
    
    def hours(self):
        command = 'sta up\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        where = re.search('LaserON: \d\d\d\d\d h \+ \d\d\d\d s', reply)
        reply_clean_string = reply[where.start():where.end()]
        hours = reply_clean_string[9:14] + ' h'
        return hours   
    
    def current(self):
        command = 'sh cur\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        where = re.search('LDC  = \d\d\d.\d mA', reply)
        reply_clean_string = reply[where.start():where.end()]
        return reply_clean_string
    
    def reset_clip(self):
        command = 'reset clip\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        return reply
    
    def reset_system(self):
        command1 = 'reset sys\r\n'
        command2 = '\r\n'
        reply1 = sendCommand(command1, self.serialInstance, self.debug_mode)
        reply2 = sendCommand(command2, self.serialInstance, self.debug_mode)
        return reply1 + reply2
    
    def status(self):
        command = 'sta la\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply = reply.rstrip('CMD\> ')
        reply = reply.strip('\r\n')
        return reply

    def temp_status(self):
        command = 'sta temp\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply = reply.rstrip('CMD\> ')
        reply = reply.strip('\r\n')
        if not re.search('PASS', reply):
            print('Temp ERROR. Returned message:')
            print(reply)
        return reply
    
    def set_power(self, power_mW):
        command = 'ch 1 pow %.3f\r\n' % power_mW
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        if reply == '\r\nCMD> ':
            print('Power has been set OK.')
        elif re.search('power maximum', reply):
            print('Power has NOT been set. Value exceeds max power.')            
        else:
            print('Unexpected reply. Returned message:')
            print(reply)
        return reply
    
    def ask_power(self):
        command = 'sh pow\r\n'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        where = re.search('PIC  = \d\d\d\d\d\d uW', reply)
        reply_clean_string = reply[where.start():where.end()]
        return reply_clean_string
    
    def shutter(self, action):
        if action == 'close':
            command = 'la off\r\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('488 OFF')
        elif action == 'open':
            command = 'la on\r\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('488 ON')
        else:
            print('Action was not determined. For precaution: shutter has been closed.')
            command = 'la off\r\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)    
        return reply
    
    def check_comm(self):
        flag_open = self.serialInstance.is_open
        if flag_open:
            print('Serial instance is open')
        else:
            print('Serial instance is NOT open')
        return flag_open
    
    def close(self):
        time.sleep(0.1)
        print('Closing 488 laser communication. Clearing serial buffer...')
        self.serialInstance.flush() # empty serial buffer
        self.shutter('close')
        closeSerial(self.serialInstance)

#=====================================

# Motorized Flipper Mount Class Definitions

#=====================================

class motorized_flipper(object):
    def __init__(self, debug_mode):
        # Parameters for Motorized Flipper
        self.baudRate = 9600
        self.serialPort = COM_port_flipper_Thorlas
        self.debug_mode = debug_mode
        self.initialize()
        
    def initialize(self):
        self.serialInstance = motoFlipper(self.serialPort)
        if self.serialInstance.is_opened:
            print('Serial port ' + self.serialPort + ' opened.')
        else:
            print('Serial port ' + self.serialPort + ' has NOT been opened.')
        
    def get_state(self):
        reply = self.serialInstance.get_state()
        if reply == 0:
            state = 'down'
        else:
            state = 'up'
        if self.debug_mode:
            print("State: ", state)
        return state

    def set_inspect_cam_up(self):
        self.serialInstance.move_to_state(1)
        
    def set_inspect_cam_down(self):
        self.serialInstance.move_to_state(0)
        
    def close(self):
        print('Closing motorized flipper serial communication...')
        self.set_inspect_cam_down()
        self.serialInstance.close()
        time.sleep(0.2)
        return

#======================================
    
if __name__ == '__main__':
    
    print('\nLooking for serial ports...')
    list_of_serial_ports = serial_ports()
    print('Ports available:', list_of_serial_ports)   
    
    # laser532 = oxxius_laser(debug_mode = False)
    
    # laser488 = toptica_laser(debug_mode = False)
    
    # mff = motorized_flipper(debug_mode = False)
    
    # laser532.close()

    # laser488.close()
    

