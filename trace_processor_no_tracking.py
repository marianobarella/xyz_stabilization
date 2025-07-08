# -*- coding: utf-8 -*-
"""
Created on Mon Jun 12, 2023

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
import json
import pandas as pd
import datetime
import ast
import gaussian_filter as gf
from matplotlib.gridspec import GridSpec

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

# filtering parameters
# average filter window
window_avg = 5
# gaussian filter parameters
sample_rate = 100000  # 100 kHz

figure_name = 'test1'

##############################################################################
# clear all plots
plt.ioff() # do not plot unless show is executed
plt.close('all')

##############################################################################+
# CONCATENATE FILES if the trace was long

# Prompt window to select any file (it will use the selected folder actually)
root = tk.Tk()
dat_files = fd.askopenfilenames(initialdir = base_folder, 
                                filetypes=(("", "*.npy"), ("", "*.")))
root.withdraw()
working_folder = os.path.dirname(dat_files[0])
save_folder = os.path.join(working_folder, 'figures') 
if not os.path.exists(save_folder):
    os.makedirs(save_folder)

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
print('Length of each trace: %d points' % length_of_trace)
# sampling period
sampling_period = 1/sample_rate
trace_time = length_of_trace*sampling_period
print('Length of each trace in time: %.1f ' % trace_time)
# print number of files
print('Number of files: %d' % number_of_files)
total_time = L_tra*trace_time
total_time_min = total_time/60  # in minutes   
print('Total time of all traces: %d s' % total_time)
print('Total time of all traces: %d min' % total_time_min)
total_number_of_points = number_of_files*length_of_trace/1e6 # in millions
print('Total number of points in (millions): %.1f ' % total_number_of_points)

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
# np.save(full_new_file_path_mon, single_trace_mon)   

##############################################################################
# FILTERING
# apply averaging filter
# single_trace_tra_avg = moving_average_sum(single_trace_tra, window_avg)
# single_trace_mon_avg = moving_average_sum(single_trace_mon, window_avg)

# apply gaussian filtering
# Process the signal
cutoff_freq = 10e3  # 10 kHz
original, filtered = gf.process_signal_file(full_new_file_path_tra, \
                                            sample_rate, cutoff_freq, plot=False)
# Save filtered signal if needed
filtered_filename = 'filtered_signal_{:.1f}kHz.npy'.format(cutoff_freq)
filtered_data_filepath = os.path.join(working_folder, filtered_filename)
# np.save(filtered_data_filepath, filtered)
original, filtered1k = gf.process_signal_file(full_new_file_path_tra, \
                                            sample_rate, 1e3, plot=False)
original, filtered01k = gf.process_signal_file(full_new_file_path_tra, \
                                            sample_rate, 0.1e3, plot=False) 

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

time_data = time_data/60 # to min

##############################################################################
# STATISTICS
tra_mean = np.mean(single_trace_tra)
tra_std = np.std(single_trace_tra)
tra_cv = tra_std/tra_mean
print('Trans mean %.6f V' % tra_mean)
print('Trans std dev %.6f V' % tra_std)
print('Trans Coef. of Variation %.3f %%' % (tra_cv*100))

monitor_mean = np.mean(single_trace_mon)
monitor_std = np.std(single_trace_mon)
monitor_cv = monitor_std/monitor_mean
print('Monitor mean %.6f V' % monitor_mean)
print('Monitor std dev %.6f V' % monitor_std)
print('Monitor Coef. of Variation %.3f %%' % (monitor_cv*100))

laser_power_trace = single_trace_mon*42.5 # in mW
normalized_trans = single_trace_tra/tra_mean
filtered1k_norm = filtered1k/tra_mean

##############################################################################
# PLOT
plt.rcParams.update({'font.size': 18})
[t_min, t_max] = [time_data[0], time_data[-1]]  # min and max time for x-axis
# First figure - Transmission
fig1 = plt.figure(figsize=(20, 5))
ax1 = fig1.add_subplot(111)
ax1.set_axisbelow(True)
ax1.tick_params(axis='both', which='major', labelsize=18)
ax1.plot(time_data, normalized_trans, color='C0', alpha=0.5, label='Original')
ax1.plot(time_data, filtered1k_norm, color='C3', alpha=1, label='1 kHz')
ax1.set_xlim([t_min, t_max])
ax1.set_xlabel('Time (min)', fontsize=18)
ax1.set_ylabel('T/T$_{0}$', fontsize=18)
ax1.grid(True, alpha=0.3)
ax1.legend(loc='upper right', fontsize=18)
figure_path = os.path.join(save_folder, '%s_transmission_vs_time.png' % figure_name)
plt.savefig(figure_path, dpi=300, bbox_inches='tight')

# Second figure - Laser Power
fig2 = plt.figure(figsize=(20, 5))
ax2 = fig2.add_subplot(111)
ax2.set_axisbelow(True)
ax2.tick_params(axis='both', which='major', labelsize=18)
ax2.plot(time_data, laser_power_trace)
ax2.set_xlim([t_min, t_max])
ax2.set_xlabel('Time (min)', fontsize=18)
ax2.set_ylabel('Laser power (mW)', fontsize=18)
ax2.grid(True, alpha=0.3)
figure_path = os.path.join(save_folder, '%s_laser_power_vs_time.png' % figure_name)
plt.savefig(figure_path, dpi=300, bbox_inches='tight')

plt.show()
# plt.close()

