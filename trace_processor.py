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

##############################################################################

def moving_average_conv(x, w):
    return np.convolve(x, np.ones(w), 'valid') / w

def moving_average_sum(x, w) :
    ret = np.cumsum(x)
    ret[w:] = ret[w:] - ret[:-w]
    return ret[w - 1:] / w

##############################################################################

# INPUTS
# base data's folder

base_folder = 'C:\\datos_mariano\\posdoc\\unifr\\plasmonic_optical_trapping\\second_try_after_integration\\apd_traces'

##############################################################################
# clear all plots
plt.ioff() # do not plot unless show is executed
plt.close('all')
# Prompt window to select any file (it will use the selected folder actually)
root = tk.Tk()
dat_files = fd.askopenfilenames(initialdir = base_folder, 
                                filetypes=(("", "*.npy"), ("", "*.")))
root.withdraw()
working_folder = os.path.dirname(dat_files[0])
# create list of files
list_of_files = os.listdir(working_folder)
list_of_files.sort()
list_of_files = [f for f in list_of_files if re.search('.npy',f)]
list_of_files_transmission = [f for f in list_of_files if re.search('_transmission',f)]
list_of_files_monitor = [f for f in list_of_files if re.search('_monitor',f)]
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
data_tra = np.load(full_filepath_tra)
# length
length_of_trace = len(data_tra)

# allocate
single_trace_tra = np.zeros((number_of_files, length_of_trace))
single_trace_mon = np.zeros((number_of_files, length_of_trace))

# create single trace in a loop
for i in range(number_of_files):
    # generate filepath
    full_filepath_tra = os.path.join(working_folder, list_of_files_transmission[i])
    full_filepath_mon = os.path.join(working_folder, list_of_files_monitor[i])
    # load files
    single_trace_tra[i,:] = np.load(full_filepath_tra)
    single_trace_mon[i,:] = np.load(full_filepath_mon)

single_trace_tra = np.reshape(single_trace_tra, (number_of_files*length_of_trace, -1))
single_trace_mon = np.reshape(single_trace_mon, (number_of_files*length_of_trace, -1))

# save data
new_filename_tra = 'single_transmission_file.npy'
new_filename_mon = 'single_monitor_file.npy'
full_new_file_path_tra = os.path.join(working_folder, new_filename_tra)
full_new_file_path_mon = os.path.join(working_folder, new_filename_mon)
np.save(full_new_file_path_tra, single_trace_tra)
np.save(full_new_file_path_mon, single_trace_mon)   

# apply gaussian filtering


# apply averaging filter
window = 5
single_trace_tra_avg = moving_average_sum(single_trace_tra, window)

#TODO build time axis
#TODO get epoch time

# plot
plt.figure()
plt.plot(single_trace_tra)
plt.plot(single_trace_tra_avg)
plt.show()

plt.figure()
plt.plot(single_trace_mon)
# plt.plot(single_trace_tra_avg)
plt.show()

    
    
    
    
    
    
    
    