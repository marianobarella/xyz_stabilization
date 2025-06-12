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
import time as tm
from pylablib.devices.Thorlabs.kinesis import MFF as motoFlipper # for flipper
from pylablib.devices import M2 # Ti:Sa laser module
from timeit import default_timer as timer
import daq_board_toolbox as daq_toolbox # for shutters control

#=====================================

#  Serial Communication Function Definitions

#=====================================
# after sending the instruction, number of bytes
# to read during serial communication (max length message received)
# modify if it's not enough
bytesToRead = 250
# COM ports
COM_port_oxxius = 'COMX' # 532 Oxxius Laser com port # NOT INSTALLED
COM_port_flipper_spectrometer = 'COM6' # APT USB Serial number: 37004922
COM_port_flipper_apd_Thorlabs = 'COM8' # APT USB Serial number: 37005240
COM_port_flipper_trapping_laser_Thorlabs = 'COM7' # APT USB Serial number: 37005241
# COM9 and COM10 are the Piezostages' controllers
COM_port_shutter_Thorlabs = 'COM3' # USB to Serial cable
COM_port_filter_wheel = 'COM12' # USB Serial Port (Thorlabs Filter Wheel FW102C)
COM_port_toptica = 'COM13' # 488 Toptica Laser using ATEN USB to Serial Bridge 
COM_valve = 'COM5' # microfluidics valve NOT USED HERE
COM_pump = 'COM4' # microfluidics pump NOT USED HERE

shutter_number_dict = {
    'NIR': 0, # Toptica NIR TA pro laser
    'white': 1, # NKT SuperK white laser
    'tisa': 2 # Ti:Sa laser
}

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
            print('Reply: ' + reply_utf8)
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
    tm.sleep(0.2) # wait until serial comm is closed
    return

#=====================================

# Laser Class Definitions

#=====================================

class oxxius_laser(object):
    def __init__(self, debug_mode):
        # Parameters for Oxxius 532 green laser
        # Warning: laser has to be configured to communicate trhough serial port
        # for this, mode "CDC 1" has to be set from Oxxius software. 
        # This has been done for the first time probably. Read User manual page 44.
        self.baudRate = 38400
        self.serialPort = COM_port_oxxius
        self.serialInstance = initSerial(self.serialPort, self.baudRate)
        self.debug_mode = debug_mode
        return
    
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
            print('532 shutter closed')
        elif action == 'open':
            command = 'SH 1\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('532 shutter opened')
        else:
            print('Action was not determined. For precaution: shutter has been closed.')
            command = 'SH 0\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)    
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def emission(self, action):
        if action == 'off':
            command = 'DL 0\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('532 emission OFF')
        elif action == 'on':
            command = 'DL 1\n'
            reply = sendCommand(command, self.serialInstance, self.debug_mode)
            print('532 emission ON')
        else:
            print('Action was not determined. Retry.')
            reply = ''
        reply_clean_string = reply.rstrip('\r\n')
        return reply_clean_string
    
    def close(self):
        tm.sleep(0.1)
        print('Closing 532 laser communication. Clearing serial buffer...')
        self.serialInstance.flush() # empty serial buffer
        self.shutter('close')
        closeSerial(self.serialInstance)
        return
    
#=====================================
#=====================================
#=====================================

class toptica_laser(object):
    def __init__(self, debug_mode):
        # Parameters for Toptica 488 blue laser
        self.baudRate = 115200
        self.serialPort = COM_port_toptica
        self.serialInstance = initSerial(self.serialPort, self.baudRate)
        self.debug_mode = debug_mode
        self.initialize()
        return
    
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
        if self.serialInstance.is_open:
            print('Serial instance is open')
        else:
            print('Serial instance is NOT open')
        return self.serialInstance.is_open
    
    def close(self):
        tm.sleep(0.1)
        print('Closing 488 laser communication. Clearing serial buffer...')
        self.serialInstance.flush() # empty serial buffer
        self.shutter('close')
        closeSerial(self.serialInstance)
        return
    
#=====================================
#=====================================
#=====================================

class M2_laser(object):
    def __init__(self, debug_mode, timeout = 5.0):
        # Parameters for Ti:Sa CW laser
        self.port = 9999 # Remote interface 1 port (set at the web interface)
        self.staticIP = '192.168.1.222'
        self.debug_mode = debug_mode
        self.timeout = timeout
        self.initialize()
        return
    
    def initialize(self):
        self.tisa_laser = M2.Solstis(self.staticIP, self.port, use_cavity=False, \
                                     timeout = self.timeout)
        if self.tisa_laser.is_opened():
            print('Ti:Sa laser connected succesfully.')
        else:
            print('It was not possible to connect Ti:Sa laser.')
        return
    
    def status(self):
        # full_status = self.tisa_laser.get_full_status()
        status_dict = self.tisa_laser.get_system_status()
        # print(status_dict)
        status_list = []
        status_list.append(str(status_dict['status']))
        status_list.append(str(round(status_dict['temperature'],1))+' K')
        return status_list
    
    def set_wavelength(self, target_wavelength):
        # if sync==True, wait until the operation is complete.
        if self.debug_mode:
            start_time = timer()
        self.tisa_laser.coarse_tune_wavelength(target_wavelength, sync=True)
        if self.debug_mode:
            delta_t = timer() - start_time # in s
            print('It took %.3f s to change the wavelength' % delta_t)
        return

    def wavelength_status(self):
        return self.tisa_laser.get_coarse_tuning_status()
    
    def get_wavelength(self):
        # in m
        self.current_wavelength = self.tisa_laser.get_coarse_wavelength()
        self.current_wavelength_nm = self.current_wavelength*1e9
        return 
    
    def stop_coarse_tuning(self):
        self.tisa_laser.stop_coarse_tuning()
        return
    
    def get_tuning_status(self):
        answer = self.tisa_laser.get_coarse_tuning_status()
        if answer == 'done':
            return 1
        elif answer == 'tuning':
            return 0
        elif answer == 'fail':
            print('ERROR! Wavelength tuning failed!')
            print('Stopping all operations...')
            self.tisa_laser.stop_all_operation()
            return -1
        else:
            print('Error: could not interpret the status of the Ti:Sa!')
            return -1
        return
    
    def close(self):
        tm.sleep(0.1)
        print('Closing Ti:Sa laser communication...')
        self.tisa_laser.stop_all_operation()
        self.tisa_laser.close()
        return
    
#=====================================

# Motorized Flipper Mount Class Definitions

#=====================================

class motorized_flipper(object):
    def __init__(self, debug_mode, serial_port):
        # Parameters for Motorized Flipper
        self.baudRate = 9600
        self.serialPort = serial_port
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

    def set_flipper_up(self):
        self.serialInstance.move_to_state(1)
        tm.sleep(0.5)
        return
        
    def set_flipper_down(self):
        self.serialInstance.move_to_state(0)
        tm.sleep(0.5)
        return
    
    def close(self):
        print('Closing motorized flipper serial communication...')
        self.set_flipper_down()
        self.serialInstance.close()
        tm.sleep(0.2)
        return

#=====================================

# Thorlabs Shutter Class Definitions 

# This class is used to control the Thorlabs shutter SC10
# Newwer setup configuration uses Trigger signals from the DAQ board
# to control the shutter, so this class is not used anymore

#=====================================

class Thorlabs_shutter(object):

    def __init__(self, debug_mode):
        # Parameters for SC10 controller
        self.baudRate = 9600 # default value for the SC10 unit
        self.serialPort = COM_port_shutter_Thorlabs
        self.debug_mode = debug_mode
        self.serialInstance = initSerial(self.serialPort, self.baudRate)
        self.initialize()
        return
    
    def initialize(self):
        self.set_mode()
        self.shutter('close')
        return
    
    def ask_model(self):
        command = 'id?\r'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.split('\r')[1]
        return reply_clean_string
    
    def set_mode(self):
        command = 'mode=1\r'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.split('\r')[1]
        return reply_clean_string
    
    def toggle(self):
        command = 'ens\r'
        sendCommand(command, self.serialInstance, self.debug_mode)
        return
    
    def get_state(self):
        command = 'closed?\r'
        reply = sendCommand(command, self.serialInstance, self.debug_mode)
        reply_clean_string = reply.split('\r')[1]
        state = int(reply_clean_string)
        if reply_clean_string == '1':
            if self.debug_mode:
                print('Shutter is closed.')
            # 1 means closed
        elif reply_clean_string == '0':
            if self.debug_mode:
                print('Shutter is opened.')
            # 0 means opened
        else:
            if self.debug_mode:
                print('Error! Shutter state cannot be determined.')
            # other numbers mean undefined state
        return state
    
    def shutter(self, action):
        # ask state
        state = self.get_state()
        if action == 'close' and state == 1:
            print('Shutter already closed')
        elif action == 'close' and state == 0:
            self.toggle()
            print('Shutter closed')
        elif action == 'open' and state == 1:
            self.toggle()
            print('Shutter opened')
        elif action == 'open' and state == 0:
            print('Shutter already opened')
        else:
            print('Action was not determined.')
        return 
    
    def close(self):
        tm.sleep(0.1)
        print('Closing shutter communication. Clearing serial buffer...')
        self.serialInstance.flush() # empty serial buffer
        self.shutter('close')
        closeSerial(self.serialInstance)
        return
    

#======================================

class shutters(object):

    def __init__(self, daq_board, debug_mode = False):
        self.debug_mode = debug_mode
        # initialize the shutter task
        self.shutter_task = daq_toolbox.init_shutters(daq_board)
        print('Shutter task created.')
        self.close_all_shutters()
        return

    def open_shutter(self, laser_name):
        """ Open a specific shutter. """
        print(f'Opening {laser_name} laser shutter...')
        shutter_number = shutter_number_dict[laser_name]
        daq_toolbox.open_shutter(self.shutter_task, shutter_number)
        return
    
    def close_shutter(self, laser_name):
        """ Close a specific shutter. """
        print(f'Closing {laser_name} laser shutter...')
        shutter_number = shutter_number_dict[laser_name]
        daq_toolbox.close_shutter(self.shutter_task, shutter_number)
        return
    
    def close_all_shutters(self):
        """ Close all shutters. """
        print('Closing all shutters...')
        daq_toolbox.close_all_shutters(self.shutter_task)
        return

    def shutdown(self):
        """ Close the shutter task and clean up resources. """
        # Close all shutters before stopping the task
        print('Closing shutters...')
        self.close_all_shutters()
        print('Stopping and closing the shutter task...')
        self.shutter_task.stop()
        self.shutter_task.close()
        return

#======================================
    
if __name__ == '__main__':
    
    print('\nLooking for serial ports...')
    list_of_serial_ports = serial_ports()
    print('Ports available:', list_of_serial_ports)   
    
    # laser532 = oxxius_laser(debug_mode = False)
    
    # laser488 = toptica_laser(debug_mode = False)
    
    # mff = motorized_flipper(debug_mode = False)
    
    # tisa_shutter = Thorlabs_shutter(debug_mode = False)
    
    print('\nDAQ board initialization...')
    daq_board = daq_toolbox.init_daq()
    shutters = shutters(daq_board)

    shutters.open_shutter('tisa') # NKT SuperK white laser
    tm.sleep(0.3)
    shutters.open_shutter('NIR') # Toptica NIR TA pro laser
    tm.sleep(5)
    shutters.close_shutter('tisa')
    tm.sleep(2)
    shutters.shutdown()

    # tisa = M2_laser(debug_mode = False)

    # laser532.close()

    # laser488.close()
    # mff.close()
    
    # print(Thorlabs.list_kinesis_devices() )
    # shutter = Thorlabs.KinesisDevice("68000970")
    # shutter = Thorlabs.BasicKinesisDevice("68000970")
    # shutter.open()
    # shutter.close()
    # shutter.get_device_info()

    
