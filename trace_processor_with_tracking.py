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
print('Length of trace: %d points' % length_of_trace)

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
np.save(filtered_data_filepath, filtered)
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
time_data = time_data/60 # to min
# time_data = time_data[index_ok]/60 # to min
# single_trace_tra = single_trace_tra[index_ok]
# single_trace_mon = single_trace_mon[index_ok]

# xy drift
index_ok = np.array(np.where(time_xy >= diff_t0[1])[0], dtype='i4')
time_xy = time_xy[index_ok]/60 # to min
x_error = x_error[index_ok]
y_error = y_error[index_ok]
msd = x_error**2 + y_error**2 # mean square displacement
# z drift
index_ok = np.array(np.where(time_z >= diff_t0[2])[0], dtype='i4')
time_z = time_z[index_ok]/60 # to min
z_error = z_error[index_ok]

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
fig = plt.figure(figsize=(20, 10))
gs = GridSpec(4, 2, figure=fig, width_ratios=[4, 1])
gs.update(hspace=0.3)

# Main plots
ax1 = fig.add_subplot(gs[0, 0])
ax2 = fig.add_subplot(gs[1, 0])
ax3 = fig.add_subplot(gs[2, 0])
ax4 = fig.add_subplot(gs[3, 0])

# Histogram plots
ax3hist = fig.add_subplot(gs[2, 1])
ax4hist = fig.add_subplot(gs[3, 1])
[t_min, t_max] = 0, 10 # in min

# Set axis below plots for all axes
axes_list = [ax1, ax2, ax3, ax4, ax3hist, ax4hist]
for ax in axes_list:
    ax.set_axisbelow(True)
    ax.tick_params(axis='both', which='major', labelsize=18)
    
# Plotting the data
ax1.plot(time_data, normalized_trans, color='C0', alpha=0.5, label='Original')
ax1.plot(time_data, filtered1k_norm, color='C3', alpha=1, label='1 kHz')
ax1.set_xlim([t_min, t_max])
ax1.set_ylim([0.925, 1.05])
ax1.set_ylabel('T/T$_{0}$', fontsize=18)
ax1.grid(True, alpha=0.3)
ax1.legend(loc='upper right', fontsize=18)

ax2.plot(time_data, laser_power_trace)
ax2.set_xlim([t_min, t_max])
ax2.set_ylabel('Laser power (mW)', fontsize=18)
ax2.grid(True, alpha=0.3)

# Modified xy drift plot with histogram
ax3.plot(time_xy, x_error, label='x')
ax3.plot(time_xy, y_error, label='y')
ax3.set_xlim([t_min, t_max])
ax3.set_ylabel(r'Drift ($\mu$m)', fontsize=18)
ax3.grid(True, alpha=0.3)
ax3.legend(loc='upper right', fontsize=18)

# Add xy drift histogram
ax3hist.hist([x_error, y_error], bins=10, orientation='horizontal')
# ax3hist.set_xlabel('Counts', fontsize=18)
ax3hist.grid(True, alpha=0.3)

# Modified z drift plot with histogram
ax4.plot(time_z, z_error, color='C2', label='z')
ax4.set_xlim([t_min, t_max])
ax4.set_xlabel('Time (min)', fontsize=18)
ax4.set_ylabel(r'Drift ($\mu$m)', fontsize=18)
ax4.grid(True, alpha=0.3)
ax4.legend(loc='upper right', fontsize=18)

# Add z drift histogram
ax4hist.hist(z_error, bins=10, rwidth=0.9, color='C2', orientation='horizontal')
ax4hist.set_xlabel('Counts', fontsize=18)
ax4hist.grid(True, alpha=0.3)

figure_path = os.path.join(save_folder, '%s_trace_vs_time.png' % figure_name)
plt.savefig(figure_path, dpi = 300, bbox_inches='tight')
# figure_path = os.path.join(save_folder, '%s_trace_vs_time.pdf' % figure_name)
# plt.savefig(figure_path, dpi = 300, bbox_inches='tight', format = 'pdf')

# plt.figure(2)
# ax = plt.gca()
# ax.scatter(laser_power_trace, single_trace_tra, s=1, c='C0', alpha=0.7)
# # ax.set_aspect('equal')
# plt.xlabel('Laser power (mW)')
# plt.ylabel('Transmission (V)')
# plt.title('Correlation between laser power and transmission')
# ax.set_axisbelow(True)
# ax.grid(True)
# figure_path = os.path.join(save_folder, '%s_power_transmission_correlation.png' % figure_name)
# plt.savefig(figure_path, dpi = 300, bbox_inches='tight')
# # figure_path = os.path.join(save_folder, '%s_correlation.pdf' % figure_name)
# # plt.savefig(figure_path, dpi = 300, bbox_inches='tight', format = 'pdf')



# plt.show()
plt.close()

