# -*- coding: utf-8 -*-
"""
Created on Thu April 7, 2022

Toolbox for PCIe-6361

Observations and drawbacks of the PCIe-6361:
- All AI are DC coupled
- Input impedance is 10 GOhm when connected
- Coupling and Input impedance cannot be changed in this model
- An Averaging window cannot be set
- Range can be selected but is always simmetrical, i.e. +5 V / -5 V

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import nidaqmx
from nidaqmx.stream_readers import AnalogSingleChannelReader as single_ch_st_reader
from nidaqmx.stream_readers import AnalogMultiChannelReader as multi_ch_st_reader
import nidaqmx.constants as ctes
import numpy as np
from timeit import default_timer as timer
import os.path as path
from tempfile import mkdtemp
import matplotlib.pyplot as plt
# import time

#=====================================

# Parameters definitions

#=====================================

apd_ch = 0 # analog input (ai) for apd, where it's connected
power_pd_ch = 1 # analog input (ai) for amplified pd to monitor power, where it's connected
plt.ioff()

#=====================================

# Functions definition

#=====================================

def init_daq():
    daq_board = nidaqmx.system.device.Device('Dev1')
    print('DAQ board model: {}'.format(daq_board.product_type))
    print('DAQ board serial number: {}'.format(daq_board.dev_serial_num))
    return daq_board

# configure APD channels
def set_task(number_of_channels, sampling_rate, samples_per_ch, min_rng, max_rng, mode, debug = False):
    # define the task object
    APD_task = nidaqmx.task.Task(new_task_name = 'APD_task')
    # prepare task to read the APD channel
    # set voltage channel for "APD_task"
    APD_task.ai_channels.add_ai_voltage_chan(
        physical_channel = 'Dev1/ai{}'.format(apd_ch), \
        name_to_assign_to_channel = 'APD_ch{}'.format(apd_ch), \
        min_val = min_rng, \
        max_val = max_rng)
    if number_of_channels > 1:
        # add Monitor laser power task
        APD_task.ai_channels.add_ai_voltage_chan(
            physical_channel = 'Dev1/ai{}'.format(power_pd_ch), \
            name_to_assign_to_channel = 'monitor_ch{}'.format(power_pd_ch), \
            min_val = min_rng, \
            max_val = max_rng)
    # estimate timeout (time_to_finish) for the task
    time_to_finish = samples_per_ch/sampling_rate # in s
    if debug:
        print('Acquiring {} points at {} MS/s sampling rate would take:'.format(samples_per_ch, \
                                                                            sampling_rate*1e-6))
        print('{} ms'.format(time_to_finish*1e3))
    # determine acquisition mode
    if mode == 'continuous':
        acq_mode = ctes.AcquisitionType.CONTINUOUS
        if debug:
            print('Acquisition mode set to "continuous".')
    elif mode == 'finite':
        acq_mode = ctes.AcquisitionType.FINITE
        if debug:
            print('Acquisition mode set to "finite".')
    else:
        print('\nError in sampling mode. Select "finite" or "continuous".')
        print('Acquisition mode set to "continuous".')
        acq_mode = ctes.AcquisitionType.CONTINUOUS
    # set task timing characteristics
    APD_task.timing.cfg_samp_clk_timing(
        rate = sampling_rate, \
        sample_mode = acq_mode, \
        samps_per_chan = samples_per_ch)
    return APD_task, time_to_finish

def check_voltage_range(device, rng):
    if rng not in device.ai_voltage_rngs:
        print('Error! Voltage range can only be one of the following:')
        print(device.ai_voltage_rngs)
    else:
        print('Range OK.')
    return

def ask_range(channel):
    print('High: {}'.format(channel.ai_rng_high))
    print('Low: {}'.format(channel.ai_rng_low))
    return

# NIDAQmx driver version
def driver_version():
    system = nidaqmx.system.System.local()
    return system.driver_version

# find installed NI devices
def installed_devices():
    system = nidaqmx.system.System.local()
    for i in system.devices:
        print(i)
    return

def measure_data_n_times(task, number_of_points, max_num_of_meas, timeout, debug = False):
    '''Measure a finite number of samples several times
    max_num_of_meas = how many measurement runs are going to be made
    number_of_points = how many points are going to be measured each run
    timeout = time to wait until a single measurement run is performed'''
    # pre-allocate data array
    data_array = np.zeros((max_num_of_meas, number_of_points), dtype = 'float')
    data_array[:] = -1000 # set data array to an impossible output
    # define an array to check how much time each run will take
    delta_time = np.zeros(max_num_of_meas)
    i = 0
    total_start_time = timer()
    while i < max_num_of_meas:
        # start time for each run
        start_time = timer()
        # start the task
        task.start()
        task.wait_until_done(timeout = timeout)
        if task.is_task_done():
            # read
            data_array[i,:] = task.read(number_of_points)
            task.stop()
            # estimate time difference
            delta_time[i] = timer() - start_time
            i += 1
    total_end_time = timer() - total_start_time
    # finish condition
    if i == max_num_of_meas:
        task.stop()
        print('{} finite measurement/s performed.'.format(i))
        # print time the measurement took
        if debug:
            # for i in range(len(delta_time)):
                # print('Run {} took {:.9f} s'.format(i + 1, delta_time[i]))
            print('Mean run time {:.9f} ms'.format(np.mean(delta_time)*1e3))
            print('Std dev run time {:.9f} ms'.format(np.std(delta_time, ddof = 1)*1e3))
            print('Sum of times {:.9f} ms'.format(np.sum(delta_time)*1e3))
            print('Total time {:.9f} ms'.format(total_end_time*1e3))
        print('Task {} has been stopped.'.format(task.name))
        print('Done.')
    return data_array

def allocate_datafile(number_of_points):
    # pre-allocate array in a temporary file
    dummy_file_path = path.join(mkdtemp(), 'allocated_datafile.dat')    
    array = np.memmap(dummy_file_path, dtype = 'float32', mode = 'w+', \
                           shape = (number_of_points) )
    array[:] = -1000 # set data array to an impossible output
    return dummy_file_path, array

def arm_measurement_in_loop(task, number_of_channels):
    '''Prepare task to measure in loop continuosly'''
    # initiate the stream reader object and pass the in_stream object of the Task
    if number_of_channels > 1:
        task_st_reader = multi_ch_st_reader(task.in_stream)
    else:
        task_st_reader = single_ch_st_reader(task.in_stream)
    return task_st_reader

def measure_in_loop_continuously(task, task_stream_reader, number_of_points, \
                                 time_base, time_array, data_array):
    '''Measure continusouly and update data
    number_of_points = how many points are going to be measured in total'''
    i = 0
    while ( not task.is_task_done() and i < number_of_points ):
        # read a short stream
        n_available, data = measure_one_loop(task_stream_reader, number_of_points, i)
        data_array[i:i + n_available] = data
        time_array[i:i + n_available] = np.arange(i, i + n_available)*time_base
        i += n_available
    data_array.flush()
    # check if all data has been written correctly
    assert np.all(data_array > -1000)
    return data_array

def measure_one_loop(task_stream_reader, number_of_channels, number_of_points_per_ch, read_samples):
    n_available = samples_available(task_stream_reader)
    if n_available == 0: 
        return n_available, np.array([])
    # prevent reading too many samples
    n_to_read = min(n_available, number_of_points_per_ch - read_samples) 
    # read directly
    data = np.empty((number_of_channels, n_to_read))
    task_stream_reader.read_many_sample(data, number_of_samples_per_channel = n_to_read)
    return n_to_read, data

def samples_available(task_stream_reader):
    return task_stream_reader._in_stream.avail_samp_per_chan

#=====================================

# Main program

#=====================================

if __name__ == '__main__':

    print('\nDAQ board toolbox test')
    number_of_channels = 1
    daq_board = init_daq()
    
    # set measurement range
    min_range = -2.0
    check_voltage_range(daq_board, min_range)
    max_range = +5.0
    check_voltage_range(daq_board, max_range)
    
    # set sampling rate
    sampling_rate = daq_board.ai_max_single_chan_rate # set to maximum, here 2 MS/s    
    # sampling_rate = 1000e3 # in S/s
    
    ########################################################
    
    # measure a finite number of samples several times
    
    ########################################################
    mode = 'finite'
    number_of_points_per_run = 100
    APD_task, time_to_finish = set_task(number_of_channels, sampling_rate, number_of_points_per_run, \
                                          min_range, max_range, mode)
    # APD_ch = APD_task.ai_channels[0]
    # ask_range(APD_ch)
    
    # perform the measurements
    max_num_of_meas = 2000
    meas_finite_array = measure_data_n_times(APD_task, number_of_points_per_run, max_num_of_meas, \
                                      time_to_finish, debug = True)
    APD_task.close()
    print('Task closed.') 
    
    # fig, ax = plt.subplots(5, 2, sharex = 'col', sharey = 'row')
    # for i in range(max_num_of_meas):
    #     plt.subplot(5, 2, i+1)
    #     plt.plot(meas_finite_array[i,:])
    # plt.show()
    
    ########################################################
    
    # measure continuosly number of samples several times
    # with a different code structure
    
    ########################################################
    mode = 'continuous'
    number_of_points = max_num_of_meas*number_of_points_per_run
    time_base = 1/sampling_rate
    APD_task, time_to_finish = set_task(number_of_channels, sampling_rate, number_of_points, \
                                          min_range, max_range, mode)
    
    # allocate array
    data_array_filepath, data_array = allocate_datafile(number_of_points)
    time_array_filepath, time_array = allocate_datafile(number_of_points)
    # perform the measurement
    APD_stream_reader = arm_measurement_in_loop(APD_task)
    APD_task.start()
    meas_cont_array = measure_in_loop_continuously(APD_task, \
                                                        APD_stream_reader, \
                                                        number_of_points, \
                                                        time_base, \
                                                        time_array, \
                                                        data_array)

    APD_task.close()
    print('Task closed.')   

    # plt.close('all')
