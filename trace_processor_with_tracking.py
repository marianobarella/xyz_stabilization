# -*- coding: utf-8 -*-
"""
Created on Mon Jun 12 10:24:54 2023

@author: BarellaM
"""

import numpy as np
import matplotlib.pyplot as plt
import os
import re
import tkinter as tk
import tkinter.filedialog as fd
import json
import pandas as pd
import datetime
import ast

##############################################################################

def moving_average_conv(x, w):
    # not so effective for large x size
    return np.convolve(x, np.ones(w), 'valid') / w

def moving_average_sum(x, w) :
    # more effective than convolution for large x size
    ret = np.cumsum(x)
    ret[w:] = ret[w:] - ret[:-w]
    return ret[w - 1:] / w

def get_number_from_headerline(filepath, line_number):
    header_line_string = pd.read_csv(filepath, header=line_number).columns.tolist()[0]
    number = re.findall("[-+]?[.]?[\d]+(?:,\d\d\d)*[\.]?\d*(?:[eE][-+]?\d+)?", header_line_string)[0]
    return float(number)

##############################################################################

# INPUTS
# base data's folder

base_folder = 'C:\\datos_mariano\\posdoc\\unifr\\plasmonic_optical_trapping\\transmission_signal_stability\\aperture\\5um'
# average filtering window
window_avg = 5

##############################################################################
# clear all plots
plt.ioff() # do not plot unless show is executed
plt.close('all')

##############################################################################+
# CONCATENATE FILES

# Prompt window to select any file (it will use the selected folder actually)
root = tk.Tk()
dat_files = fd.askopenfilenames(initialdir = base_folder, 
                                filetypes=(("", "*.npy"), ("", "*.")))
root.withdraw()
working_folder = os.path.dirname(dat_files[0])
# create list of files
list_of_files = os.listdir(working_folder)
list_of_files.sort()
parameters_file = [f for f in list_of_files if re.search('_params.txt',f)][0]
list_of_files_transmission = [f for f in list_of_files if re.search('_transmission.npy',f)]
list_of_files_monitor = [f for f in list_of_files if re.search('_monitor.npy',f)]
L_tra = len(list_of_files_transmission)
L_mon = len(list_of_files_monitor)

# check if there're missing files
if not L_tra == L_mon:
    print('Warning! Number of tranmission and monitor files differ')
else:
    number_of_files = L_tra

# get length of trace
full_filepath_tra = os.path.join(working_folder, list_of_files_transmission[0])
# load files
temporary_data = np.load(full_filepath_tra)
# length
length_of_trace = len(temporary_data)

# allocate
single_trace_tra = np.zeros((number_of_files, length_of_trace), dtype='float32')
single_trace_mon = np.zeros((number_of_files, length_of_trace), dtype='float32')

# create single trace in a loop
for i in range(number_of_files):
    # generate filepath
    full_filepath_tra = os.path.join(working_folder, list_of_files_transmission[i])
    full_filepath_mon = os.path.join(working_folder, list_of_files_monitor[i])
    # load files
    single_trace_tra[i,:] = np.load(full_filepath_tra)
    single_trace_mon[i,:] = np.load(full_filepath_mon)

# reshape into a Nx1 array
number_of_points = number_of_files*length_of_trace
single_trace_tra = np.reshape(single_trace_tra, (number_of_points, -1))
single_trace_mon = np.reshape(single_trace_mon, (number_of_points, -1))

# save data
new_filename_tra = 'single_transmission_file.npy'
new_filename_mon = 'single_monitor_file.npy'
full_new_file_path_tra = os.path.join(working_folder, new_filename_tra)
full_new_file_path_mon = os.path.join(working_folder, new_filename_mon)
np.save(full_new_file_path_tra, single_trace_tra)
np.save(full_new_file_path_mon, single_trace_mon)   

##############################################################################
# FILTERING
# apply averaging filter
single_trace_tra_avg = moving_average_sum(single_trace_tra, window_avg)
single_trace_mon_avg = moving_average_sum(single_trace_mon, window_avg)

# apply gaussian filtering
#TODO

##############################################################################
# BUILD TIME AXIS
# retrieve parameters
# reading the data from the file
parameters_filepath = os.path.join(working_folder, parameters_file)
with open(parameters_filepath) as f:
    data = f.read()
parameters = ast.literal_eval(data)
sampling_frequency = parameters['Sampling rate (S/s)']
# build time axis
delta_time = 1/sampling_frequency
time_data = np.arange(0, number_of_points*delta_time, delta_time, dtype='float32')
# get epoch time
time_since_epoch_data = parameters['Time since epoch (s)']

##############################################################################
# GET XYZ TRACKING DATA
# get files and load data
xy_drift_file = [f for f in list_of_files if re.search('drift_curve_xy',f)][0]
z_drift_file = [f for f in list_of_files if re.search('drift_curve_z',f)][0]
xy_drift_filepath = os.path.join(working_folder, xy_drift_file)
z_drift_filepath = os.path.join(working_folder, z_drift_file)
# data for xy drift
time_xy, x_error, y_error = np.loadtxt(xy_drift_filepath, unpack=True, dtype='float32')
time_since_epoch_xy = get_number_from_headerline(xy_drift_filepath, 0) # in s
tracking_period_xy = get_number_from_headerline(xy_drift_filepath, 1) # in ms
# data for z drift
time_z, z_error, column_not_used = np.loadtxt(z_drift_filepath, unpack=True, dtype='float32')
time_since_epoch_z = get_number_from_headerline(z_drift_filepath, 0) # in s
tracking_period_z = get_number_from_headerline(z_drift_filepath, 1) # in ms

##############################################################################
# SYNCHRONIZE
# find the proces that started the last
time_since_epoch_array = np.array([time_since_epoch_data, time_since_epoch_xy, time_since_epoch_z])
index_max = np.argmax(time_since_epoch_array)
t0 = time_since_epoch_array[index_max]
diff_t0 = t0 - time_since_epoch_array
# crop all data to start after t0

index_ok = np.array(np.where(time_data >= diff_t0[0])[0], dtype='i4')
time_data = time_data[index_ok]
single_trace_tra = single_trace_tra[index_ok]
single_trace_mon = single_trace_mon[index_ok]

# xy drift
time_xy = np.where(time_xy >= diff_t0[1], time_xy, 0)
x_error = np.where(time_xy >= diff_t0[1], x_error, 0)
y_error = np.where(time_xy >= diff_t0[1], y_error, 0)
# z drift
time_z = np.where(time_z >= diff_t0[2], time_z, 0)
z_error = np.where(time_z >= diff_t0[2], z_error, 0)

##############################################################################
# STATISTICS
apd_mean = np.mean(single_trace_tra)
apd_std = np.std(single_trace_tra)
apd_cv = apd_std/apd_mean
print('APD mean %.6f V' % apd_mean)
print('APD std dev %.6f V' % apd_std)
print('APD Coef. of Variation %.3f %%' % (apd_cv*100))

monitor_mean = np.mean(single_trace_mon)
monitor_std = np.std(single_trace_mon)
monitor_cv = monitor_std/monitor_mean
print('Monitor mean %.6f V' % monitor_mean)
print('Monitor std dev %.6f V' % monitor_std)
print('Monitor Coef. of Variation %.3f %%' % (monitor_cv*100))

##############################################################################
# PLOT
fig, (ax1, ax2, ax3) = plt.subplots(3, 1)
fig.subplots_adjust(hspace=0.5) # extra space between the subplots
ax1.plot(time_data, single_trace_tra, label='APD')
ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Signal (V)')
ax1.legend(loc='best')
ax1.grid(True)
ax2.plot(time_data, single_trace_mon, label='Monitor')
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('Signal (V)')
ax2.legend(loc='best')
ax2.grid(True)
ax3.plot(time_xy, x_error, label='x drift')
ax3.plot(time_xy, y_error, label='y drift')
ax3.plot(time_z, z_error, label='z drift')
ax3.set_xlabel('Time (s)')
ax3.set_ylabel(r'Drift ($\mu$m)')
ax3.legend(loc='best')
ax3.grid(True)
plt.show()

plt.figure(2)
ax = plt.gca()
ax.scatter(single_trace_tra, single_trace_mon, s=2)
# ax.set_aspect('equal')
plt.ylabel('Monitor signal (V)')
plt.xlabel('APD signal (V)')
ax.set_axisbelow(True)
ax.grid(True)
plt.show()
    
    
    
    
    
    
    