# -*- coding: utf-8 -*-
""" This module contains the BPC303 class and its related functions, which
implement simultaneous initialization and control of the 3 channels of a
Thorlabs BPC 303 Benchtop Piezo Controller.

Classes, Exceptions and Functions:
class BPC303 --     initialization and control of the 3 channels of a
                    Thorlabs BPC 303 Benchtop Piezo Controller

@author: 
    (created by) Thibaud Ruelle, PhD student, Poggio Lab, Basel University
    (modified by) Mariano Barella, Adolphe Merkle Institute, University of Fribourg
    Fribourg, Switzerland
    mariano.barella@unifr.ch


===== NanoMax311D =====

++ Piezos specs:
Theoretical Resolution: 5 nm
Bidirectional Repeatability: 50 nm
Voltage Range: 0 - 75 V
Travel: 20 µm

++ Differential micrometer drives specs:
Travel Range: 8 mm Coarse, 300 µm Fine
Coarse Adjustment (with Vernier Scale): 500 µm/rev
Fine Adjustment (with Vernier Scale): 50 µm/rev

"""

import sys
from time import sleep
import numpy as np
import matplotlib.pyplot as plt
import clr
from timeit import default_timer as timer


clr.AddReference("System.Collections")
clr.AddReference("System.Linq")
from System.Collections.Generic import List #analysis:ignore
import System.Collections.Generic #analysis:ignore
from System import String, Decimal #analysis:ignore
import System.Linq #analysis:ignore
import System #analysis:ignore

sys.path.append(r"C:\Program Files\Thorlabs\Kinesis")
clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
clr.AddReference("Thorlabs.MotionControl.GenericPiezoCLI")
clr.AddReference("Thorlabs.MotionControl.Benchtop.PiezoCLI")
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI #analysis:ignore
from Thorlabs.MotionControl.DeviceManagerCLI import DeviceNotReadyException #analysis:ignore
import Thorlabs.MotionControl.GenericPiezoCLI.Piezo as Piezo #analysis:ignore
from Thorlabs.MotionControl.Benchtop.PiezoCLI import BenchtopPiezo #analysis:ignore

#=====================================

# Functions definition

#=====================================

# 37004922 deviceID is the flipper
# 71260444 deviceID is the benchtop controller 

def list_devices():
    """Return a list of Kinesis serial numbers"""
    DeviceManagerCLI.BuildDeviceList()
    return print(list(DeviceManagerCLI.GetDeviceList()))

#=====================================

# Piezo Stage class definition

#===================================== 

class BPC303:
    """
    Main class for the BPC303 3 channel Benchtop Piezo Controller. Wraps the
    .NET base class from Thorlabs providing channel by channel control.

    Attributes and methods:
    attribute deviceID -- stores the device ID of the physical instrument
    attribute axis_chan_mapping -- stores the direction (x, y or z) which
        each channel of the controller addresses
    attribute isconnected -- boolean representing the state of the connection
        to the physical instrument
    attribute controller -- controller instance (from Thorlabs .NET dll)
    attributes xchannel, ychannel and zchannel -- channel instances
        (from Thorlabs .NET dll)
    method __init__(self, deviceID, axis_chan_mappign) --
    method __enter__(self) -- special class, see doc
    method connect(self) -- initializes the physical instrument
    """
    def __init__(self, deviceID, axis_chan_mapping={'x': 1, 'y': 2, 'z': 3}):
        """
        Method creating a BPC303 instance and setting up the connection to the
        device with device ID. Also creates the attributes self.deviceID,
        self.isconnected and self.axis_chan_mapping
        """
        DeviceManagerCLI.BuildDeviceList()
        self.deviceID = deviceID
        self.isconnected = False
        self.axis_chan_mapping = axis_chan_mapping
        if (self.deviceID in DeviceManagerCLI.GetDeviceList().ToArray()):
            self.controller = BenchtopPiezo.CreateBenchtopPiezo(self.deviceID)
        else:
            raise DeviceNotReadyException
        for attrname in ("xchannel", "ychannel", "zchannel"):
            setattr(self, attrname, None)
        return 
    
    def __enter__(self):
        return self

    def __get_chan(self, axis):
        """
        Internal method returning the channel corresponding to axis
        """
        attrname = axis + "channel"
        channel = getattr(self, attrname)
        return channel

    def connect(self):
        """
        Method initializing the physical instrument, first the main controller
        unit and then each channel, which is linked to the corresponding axis
        as defined in self.axis_chan_mapping
        """
        print("Connecting to BPC303:")
        print("\t- connecting to controller %s -->" % self.deviceID, end="")
        self.controller.Connect(self.deviceID)
        self.isconnected = self.controller.IsConnected
        print(" done" if self.controller.IsConnected else "failed")
        for axis in ("x", "y", "z"):
            channelno = self.axis_chan_mapping[axis]
            attrname = axis + "channel"
            print("\t- connecting channel %d (%s axis) -->" % (channelno, axis), end="")
            setattr(self, attrname, self.controller.GetChannel(channelno))
            channel = getattr(self, attrname)
            if not channel.IsSettingsInitialized():
                try:
                    channel.WaitForSettingsInitialized(5000)
                except:
                    print('Timout: channel was not initialized.')
                    raise
            channel.StartPolling(100)
            channel.EnableDevice()
            print(" done" if channel.IsConnected else "failed")
        return
    
    def identify(self, axis):
        """
        Method identifying the channel corresponding to axis by making the
        controller blink.
        """
        if axis in ("x", "y", "z"):
            channelno = self.axis_chan_mapping[axis]
            print("Identifying BPC303 channel %d (%s axis) -->" % (channelno, axis), end="")
            channel = self.__get_chan(axis)
            channel.IdentifyDevice()
            sleep(5)
            print(" done")
        else:
            print("Cannot identify BPC303 channel (axis invalid)")
        return

    def set_close_loop(self, yes):
        """
        Method setting all channels to closed loop or open loop control mode
        """
        print("Setting control mode to %s loop\n" % ("closed" if yes else "open"))
        mode = Piezo.PiezoControlModeTypes.CloseLoop if yes else Piezo.PiezoControlModeTypes.OpenLoop
        print(mode, '\n')
        for axis in ("x", "y", "z"):
            channel = self.__get_chan(axis)
            channel.SetPositionControlMode(mode)
            sleep(0.3)
        return
    
    def zero(self, axis="all"):
        """
        Method performing a Set Zero operation on all channels or on a single
        one
        """
        print("Performing Set Zero:")
        if axis == "all":
            for ax in ("x", "y", "z"):
                self.__zero_axis(ax)
        elif axis in ("x", "y", "z"):
            self.__zero_axis(axis)
        else:
            print("\t- axis invalid)")
        # time needed to zeroing is around 24 s
        # avoid reading the position then
        sleep(25)
        print('Ready.')
        return
    
    def __zero_axis(self, axis):
        """
        Internal method performing a Set Zero operation on a single channel
        """
        if axis in ("x", "y", "z"):
            channelno = self.axis_chan_mapping[axis]
            print("\t- zeroing channel %d (%s axis) -->" % (channelno, axis), end="")
            channel = self.__get_chan(axis)
            channel.SetZero()
            print(" done")
        else:
            print("\t- axis invalid)")
        return
    
    def set_position(self, x=None, y=None, z=None):  # define
        """
        Method setting the position in um if the channel is in
        Closed Loop mode
        """
        print("Setting Position:")
        pos = {"x": x, "y": y, "z": z}
        for axis, pos in pos.items():
            if pos is None:
                pass
            else:
                self.__set_axis_position(axis, pos)
        return
        
    def __set_axis_position(self, axis, pos):  # define
        """
        Internal method setting the position in um if the channel is in
        Closed Loop mode
        """
        if axis in ("x", "y", "z"):
            print("\t- moving %s axis piezo to %f um -->" % (axis, pos), end="")
            channel = self.__get_chan(axis)
            channel.SetPosition(Decimal(pos))
            print(" done")
        else:
            print("\t- axis invalid)")
        return

    def get_axis_position(self, axis):
        """
        Method returning the position (float, in µm) of an specific axis/channel
        """
        if axis in ("x", "y", "z"):
            channel = self.__get_chan(axis)
            position = channel.GetPosition() # in um
            position_str = '{}'.format(position)
            position_float = float(position_str)
        else:
            print('Error! Axis {} doesn\'t exist. Axis can only be x, y or z.'.format(axis))
            position_float = None
        return position_float
    
    def move_relative(self, axis, step):
        """
        Method setting the relative position in µm if the channel is in
        Closed Loop mode
        """
        actual_position = self.get_axis_position(axis)
        new_position = actual_position + step
        self.__set_axis_position(axis, new_position)
        return 
    
    def get_info(self):
        """
        Method returning a string containing the info on the controller and
        channels
        """
        print("Getting info...")
        info = "Controller:\n%s\n" % self.controller.GetDeviceInfo().BuildDeviceDescription()
        # TODO: needs to be debugged
        # Warning! The following lines don't work
        # Error is: "Device configuration is not initialized".

        # sortedMap = sorted(self.axis_chan_mapping.items(), key=operator.itemgetter(1))
        # for axis, channelno in sortedMap:
            # channel = self.__get_chan(axis)
            # chaninfo = channel.GetDeviceInfo().BuildDeviceDescription()
            # piezoConfig = channel.GetPiezoConfiguration(self.deviceID)
            # curDevSet = channel.PiezoDeviceSettings
            # piezoInfo = "Piezo Configuration Name: %s, Piezo Max Voltage: %s" % (
            #     piezoConfig.DeviceSettingsName,
            #     curDevSet.OutputVoltageRange.MaxOutputVoltage.ToString())
            # info += "Channel %d (%s axis):\n%s%s\n\n" % (channelno,
            #                                              axis,
            #                                              chaninfo,
            #                                              piezoInfo)
        return info

    def estimate_precision(self, position_array, number_of_measurements = 100, delay = 0.5):
        """
        Method to estimate the position precision in a close loop operation 
        at a particular position. Method returns average position and standard 
        deviation for the number of measurements using delay as time interval
        """
        # set position
        x_pos, y_pos, z_pos = position_array
        self.set_position(x_pos, y_pos, z_pos)
        sleep(5) # for settling time
        # allocate
        x_read_pos = np.zeros(number_of_measurements)
        y_read_pos = np.zeros(number_of_measurements)
        z_read_pos = np.zeros(number_of_measurements)
        # read position several times
        print('Starting feedback close loop position precision routine...')
        for i in range(number_of_measurements):
            x_read_pos[i] = self.get_axis_position('x')
            y_read_pos[i] = self.get_axis_position('y')
            z_read_pos[i] = self.get_axis_position('z')
            # print(x_read_pos[i], y_read_pos[i], z_read_pos[i])
            sleep(delay)
        # calculate stats
        x_mean = np.mean(x_read_pos)
        y_mean = np.mean(y_read_pos)
        z_mean = np.mean(z_read_pos)
        x_std = np.std(x_read_pos, ddof = 1)
        y_std = np.std(y_read_pos, ddof = 1)
        z_std = np.std(z_read_pos, ddof = 1)
        print('Average position:\nx = {:.4f} µm\ny = {:.4f} µm\nz = {:.4f} µm'.format(x_mean, y_mean, z_mean))
        print('Std dev :\nσx = {:.6f} µm\nσy = {:.6f} µm\nσz = {:.6f} µm'.format(x_std, y_std, z_std))
        print('Done.')
        return x_mean, y_mean, z_mean, x_std, y_std, z_std

    def response_time(self, axis, step):
        """
        Method to estimate the settling time of the axis' piezo in a close loop 
        operation. The method plots position vs time.
        After testing all axis with different step sizes, 0.5 s seems a reasonable
        settling time for step by step operation.
        """
        number_of_measurements = 100
        # allocate
        read_pos = np.zeros(number_of_measurements)
        t = np.zeros(number_of_measurements)
        # read position several times
        print('Testing response time...')
        # set position
        start_time = timer()
        self.move_relative(axis, step)
        for i in range(number_of_measurements):
            t[i] = timer()
            read_pos[i] = self.get_axis_position(axis)
            sleep(0.0001)
        t = t - start_time
        plt.close('all')
        plt.figure()
        plt.plot(t, read_pos, 'o-')
        plt.xlabel('Time (s)')
        plt.ylabel('Position (µm)')
        plt.show()
        return

    def shutdown(self):
        """
        Method for shutting down the connection to the physical instrument
        cleanly. The polling of the connected channels is stopped and the
        controller is disconnected.
        """
        print("Shutting BPC303 down:")
        if self.controller.IsConnected:
            for axis in ("x", "y", "z"):
                channelno = self.axis_chan_mapping[axis]
                print("\t- disconnecting channel %d (%s axis) -->" % (channelno, axis), end="")
                channel = self.__get_chan(axis)
                channel.StopPolling()
                channel.DisableDevice()
                print(" done")
            print("\t- disconnecting controller %s -->" % self.deviceID, end="")
            self.controller.Disconnect()
            print(" done")
        print("\t- done\n")
        return
    
    def __del__(self):
        self.shutdown()
        return
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.shutdown()
        return True if exc_type is None else False

#=====================================

# Main program

#=====================================
#%%
if __name__ == "__main__":
    print("\n")
    # list IDs of Thorlabs Kinesis devices
    list_devices()
    # Id of the benchtop controller
    deviceID = '71260444'
    # assign device
    piezo_stage = BPC303(deviceID)
    piezo_stage.deviceID
    # initialize (connect)
    piezo_stage.connect()
    # method to check if it's connected
    piezo_stage.controller.IsConnected
    # get info
    print(piezo_stage.get_info())
    # set ON closed-loop operation
    piezo_stage.set_close_loop(True)
    # perform zero routine for all axis
    piezo_stage.zero('all')
    
    # piezo_stage.set_position(0, 0, 0)
    # piezo_stage.response_time('x', 1)
    
    # print(piezo_stage.get_axis_position('x'))

    start = timer()
    piezo_stage.estimate_precision([10,10,10])
    print(timer()-start)
    
    # piezo_stage.move_relative('x', 0.100)
    # pos = piezo_stage.get_axis_position('x')
    # print(pos)
    
        

#%%
    # identify each axis
    for axis in ("x", "y", "z"):
        piezo_stage.identify(axis)
    
#%%
    # disconnect        
    # piezo_stage.shutdown()
    
