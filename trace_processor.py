# -*- coding: utf-8 -*-
"""
Created on Tue Oct 3, 2023

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import numpy as np
import matplotlib.pyplot as plt
import os
import re
import tkinter as tk
import tkinter.filedialog as fd
# import json
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

base_folder = 'C:\\datos_mariano\\posdoc\\unifr\\plasmonic_optical_trapping'
experiment_folder = '\\measurements_2024\\power_stabilization_test_new_Setup_20250124\\20240124'
base_folder = os.path.join(base_folder, experiment_folder)
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
# # PLOT
# fig, (ax1, ax2) = plt.subplots(2, 1)
# fig.subplots_adjust(hspace=0.5) # extra space between the subplots
# ax1.plot(time_data, single_trace_tra, label='APD')
# ax1.set_xlabel('Time (s)')
# ax1.set_ylabel('Signal (V)')
# ax1.legend(loc='best')
# ax1.grid(True)
# ax2.plot(time_data, single_trace_mon, label='Monitor')
# ax2.set_xlabel('Time (s)')
# ax2.set_ylabel('Signal (V)')
# ax2.legend(loc='best')
# ax2.grid(True)
# plt.show()
    
    
    
    
    
    
    