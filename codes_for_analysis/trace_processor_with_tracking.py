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
# import pandas as pd
# import datetime
import ast
import signal_filtering_functions as gf
from scipy.stats import norm
from matplotlib.gridspec import GridSpec

##############################################################################
# Clear all plots
plt.ioff() # do not plot unless show is executed
plt.close('all')
##############################################################################

# INPUTS
# Set data folder
base_folder = 'C:\\datos_mariano\\posdoc\\unifr\\plasmonic_optical_trapping'
experiment_folder = "\\measurements_2025\\20250924_DNH_transmission_stability_when_tracked_long"
data_folder = os.path.join(base_folder, experiment_folder)

# Do downsampling?
do_downsampling = True
# Downsampling factor
downsampling_factor = 100
# Filtering parameters
save_filtered_signal = False
# Average filter window
window_avg = 5
# Gaussian filter parameters
cutoff_freq = 10 # in Hz
# Plot?
plot_flag = True

step0, step1, step2 = 1, 0, 0
step0, step1, step2 = 0, 1, 0
# step0, step1, step2 = 0, 0, 0
# step0, step1, step2 = 1, 1, 0

##############################################################################
# START
##############################################################################
# Prompt window to select any file (it will use the selected folder actually)
root = tk.Tk()
dat_files = fd.askopenfilenames(initialdir = data_folder, title = "Select .npy files to process", \
                                filetypes=(("", "*.npy"), ("", "*.")))
root.withdraw()

# Get working folder
working_folder = os.path.dirname(dat_files[0])
# Create list of files
list_of_files = os.listdir(working_folder)
list_of_files.sort()
# Create folder to save figures
save_folder = os.path.join(working_folder, 'processed_data') 
if not os.path.exists(save_folder):
    os.makedirs(save_folder)

##############################################################################
# STEP 0: PROCESS TRACE FILES
##############################################################################
if step0:
    print('\n--------------------- STEP 0: PROCESS TRACE FILES ---------------------')
    # Concatenate files if the experiment was longer than single trace duration
    parameters_file = [f for f in list_of_files if re.search('_params.txt',f)][0]
    list_of_files_transmission = [f for f in list_of_files if re.search('_transmission.npy',f)]
    list_of_files_monitor = [f for f in list_of_files if re.search('_monitor.npy',f)]
    L_tra = len(list_of_files_transmission)
    L_mon = len(list_of_files_monitor)

    print('\nNumber of transmission files: %d' % L_tra)

    # Check if there're missing files
    if not L_tra == L_mon:
        print('Warning! Number of tranmission and monitor files differ')
    else:
        number_of_files = L_tra

    # Retrieve parameters
    # Get length of trace
    parameters_file_filepath = os.path.join(working_folder, parameters_file)
    # Load parameters' file
    with open(parameters_file_filepath, 'r') as file:
        content = file.read()
        parameters_dict = ast.literal_eval(content)
    length_of_trace = parameters_dict['Number of points']
    duration = parameters_dict['Duration (s)'] # in s
    print('\nSingle trace duration (s): %.1f' % duration)
    if do_downsampling: 
        length_of_trace = length_of_trace//downsampling_factor
    print('\nLength of trace: %d points' % length_of_trace)
    number_of_points = number_of_files*length_of_trace
    print('\nTotal number of points: %d points' % number_of_points)
    total_duration_min = duration*number_of_files/60
    total_duration_hours = duration*number_of_files/3600
    print('\nTotal duration (min): %.1f' % total_duration_min)
    print('\nTotal duration (hours): %.1f' % total_duration_hours)
    # BUILD TIME AXIS
    # Reading the data from the file
    sampling_rate = parameters_dict['Sampling rate (S/s)']
    if do_downsampling:
        sampling_rate = sampling_rate/downsampling_factor
    # Build time axis
    delta_time = 1/sampling_rate
    time_data = np.arange(0, number_of_points*delta_time, delta_time, dtype='float32')
    # Get epoch time
    time_since_epoch_data = parameters_dict['Time since epoch (s)']

    # Add to dictionary the new parameters
    parameters_dict['Downsampling?'] = do_downsampling
    parameters_dict['Downsampling factor'] = downsampling_factor
    parameters_dict['New sampling rate (S/s)'] = sampling_rate
    parameters_dict['Total number of points'] = number_of_points
    parameters_dict['Total duration (min)'] = total_duration_min
    parameters_dict['Total duration (hours)'] = total_duration_hours
    parameters_dict['Cut-off frequency (Hz)'] = cutoff_freq

    ##############################################################################
    # TRANSMISSION TRACE 
    ##############################################################################
    # Allocate
    single_trace_tra = np.zeros((number_of_files, length_of_trace), dtype='float32')
    # Create single trace in a loop
    for i in range(number_of_files):
        # Generate filepath
        full_filepath_tra = os.path.join(working_folder, list_of_files_transmission[i])
        # Load files
        data = np.load(full_filepath_tra)
        if do_downsampling:
            trace = data[::downsampling_factor]
        else:
            trace = data
        single_trace_tra[i,:] = trace
    # Reshape into a Nx1 array
    single_trace_tra = np.reshape(single_trace_tra, (number_of_points, -1))

    ##############################################################################
    # BASELINE CORRECTION
    ##############################################################################
    print('\nApplying baseline correction to transmission trace...')
    # Baseline calculation
    # For this example, the baseline lasts 0.1 min, then the laser is turned on
    index_baseline = np.array(np.where(time_data <= 0.1)[0], dtype='i4') # first 6 seconds
    # print(max(index_baseline), time_data[max(index_baseline)])
    baseline = np.mean(single_trace_tra[index_baseline]) # mean of first minute
    print('Baseline transmission (first 6 s) %.6f V' % baseline)
    # Subtract baseline
    single_trace_tra = single_trace_tra - baseline

    ##############################################################################
    # FILTERING
    ##############################################################################
    print('\nApplying filtering to transmission trace...')
    # Ensure it's a 1D array
    signal = single_trace_tra.flatten()  
    if signal.ndim > 1:
        raise ValueError("Signal must be a 1D array.")
    
    # Apply averaging filter
    # single_trace_tra_avg = moving_average_sum(single_trace_tra, window_avg)
    # single_trace_mon_avg = moving_average_sum(single_trace_mon, window_avg)
    
    # Apply gaussian filtering
    # Process the signal
    filtered = gf.gaussian_filter_time_domain(signal, sampling_rate, cutoff_freq)
    # Save filtered signal if needed
    filtered_filename = 'filtered_signal.npy'
    filtered_data_filepath = os.path.join(save_folder, filtered_filename)
    np.save(filtered_data_filepath, filtered)
    # filtered1k = gf.gaussian_filter_time_domain(signal, \
    #                                         new_sampling_rate, 1e3)
    # filtered01k = gf.gaussian_filter_time_domain(signal, \
    #                                         new_sampling_rate, 0.1e3)
    
    ##############################################################################
    # MONITOR TRACE 
    ##############################################################################
    # Allocate
    single_trace_mon = np.zeros((number_of_files, length_of_trace), dtype='float32')
    # Create single trace in a loop
    for i in range(number_of_files):
        # Generate filepath
        full_filepath_mon = os.path.join(working_folder, list_of_files_monitor[i])
        # Load files
        data = np.load(full_filepath_mon)
        if do_downsampling:
            trace = data[::downsampling_factor]
        else:
            trace = data
        single_trace_mon[i,:] = trace
    # Reshape into a Nx1 array
    single_trace_mon = np.reshape(single_trace_mon, (number_of_points, -1))

    # Save data
    new_filename_tra = 'single_transmission_file.npy'
    new_filename_mon = 'single_monitor_file.npy'
    full_new_file_path_tra = os.path.join(save_folder, new_filename_tra)
    full_new_file_path_mon = os.path.join(save_folder, new_filename_mon)
    full_new_file_path_time = os.path.join(save_folder, 'time_axis.npy')
    np.save(full_new_file_path_tra, single_trace_tra)
    np.save(full_new_file_path_mon, single_trace_mon)
    np.save(full_new_file_path_time, time_data)
    new_filename_parameteres = 'processed_parameters.txt'
    full_new_file_path_parameters = os.path.join(save_folder, new_filename_parameteres)
    with open(full_new_file_path_parameters, 'w') as file:
        file.write(str(parameters_dict)) # Convert dict to string

##############################################################################
# STEP 1: GET XYZ TRACKING DATA AND SYNCHRONIZE
##############################################################################
if step1:
    print('\n--------------------- STEP 1: GET XYZ TRACKING DATA AND SYNCHRONIZE ---------------------')
    # Load processed data
    single_transmission_filepath = os.path.join(save_folder, 'single_transmission_file.npy')
    single_trace_tra = np.load(single_transmission_filepath)
    single_monitor_filepath = os.path.join(save_folder, 'single_monitor_file.npy')
    single_trace_mon = np.load(single_monitor_filepath)    
    time_axis_filepath = os.path.join(save_folder, 'time_axis.npy')
    time_data = np.load(time_axis_filepath) 
    filtered_filepath = os.path.join(save_folder, 'filtered_signal.npy')
    filtered = np.load(filtered_filepath)
    new_filename_parameteres = 'processed_parameters.txt'
    full_new_file_path_parameters = os.path.join(save_folder, new_filename_parameteres)
    with open(full_new_file_path_parameters, 'r') as file:
        content = file.read()
        parameters_dict = ast.literal_eval(content)
    new_sampling_rate = parameters_dict['New sampling rate (S/s)']
    time_since_epoch_data = parameters_dict['Time since epoch (s)']

    ##############################################################################
    # GET XYZ TRACKING DATA
    # get files and load data
    xy_drift_file = [f for f in list_of_files if re.search('drift_curve_xy',f)][0]
    z_drift_file = [f for f in list_of_files if re.search('drift_curve_z',f)][0]
    xy_drift_filepath = os.path.join(working_folder, xy_drift_file)
    z_drift_filepath = os.path.join(working_folder, z_drift_file)
    # data for xy drift
    time_xy, x_error, y_error = np.loadtxt(xy_drift_filepath, unpack=True, dtype='float32')
    time_since_epoch_xy = gf.get_number_from_headerline(xy_drift_filepath, 0) # in s
    tracking_period_xy = gf.get_number_from_headerline(xy_drift_filepath, 1) # in ms
    # data for z drift
    time_z, z_error, column_not_used = np.loadtxt(z_drift_filepath, unpack=True, dtype='float32')
    time_since_epoch_z = gf.get_number_from_headerline(z_drift_filepath, 0) # in s
    tracking_period_z = gf.get_number_from_headerline(z_drift_filepath, 1) # in ms

    ##############################################################################
    # SYNCHRONIZE
    ##############################################################################
    # Find the proces that started the last
    time_since_epoch_array = 1e-9*np.array([time_since_epoch_data, time_since_epoch_xy, time_since_epoch_z])
    index_max = np.argmax(time_since_epoch_array)
    print('\nIndex = 0: transmission trace')
    print('Index = 1: xy trace')
    print('Index = 2: z trace')
    print('The process that started last is index: %d' % index_max)
    t0 = time_since_epoch_array[index_max]
    diff_t0 = t0 - time_since_epoch_array
    print('Time differences to synchronize (s): %s' % diff_t0)
    # Crop all data to start after t0

    index_ok = np.array(np.where(time_data >= diff_t0[0])[0], dtype='i4')
    # time_data = time_data/60 # to min
    time_data = time_data[index_ok]/60 # to min
    single_trace_tra = single_trace_tra[index_ok]
    single_trace_mon = single_trace_mon[index_ok]

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
    ##############################################################################

    print('\nCalculating statistics...')
    # SET TIME LIMITS FOR STATISTICS AND PLOTTING
    # Set time limits
    [t_min, t_max] = 0, 90 # in min

    index_time_limits = np.array(np.where((time_data >= t_min) & (time_data <= t_max))[0], dtype='i4')
    time_data = time_data[index_time_limits]
    single_trace_tra = single_trace_tra[index_time_limits]
    single_trace_mon = single_trace_mon[index_time_limits]
    filtered = filtered[index_time_limits]
    # Also crop drift data
    index_time_limits = np.array(np.where((time_xy >= t_min) & (time_xy <= t_max))[0], dtype='i4')
    time_xy = time_xy[index_time_limits]
    x_error = x_error[index_time_limits]
    y_error = y_error[index_time_limits]
    index_time_limits = np.array(np.where((time_z >= t_min) & (time_z <= t_max))[0], dtype='i4')
    time_z = time_z[index_time_limits]
    z_error = z_error[index_time_limits]

    # XY stats
    x_error_std_dev = np.std(x_error)
    x_error_mean = np.mean(x_error)
    y_error_std_dev = np.std(y_error)
    y_error_mean = np.mean(y_error)
    # Z stats
    z_error_std_dev = np.std(z_error)
    z_error_mean = np.mean(z_error)
    print('-------- XY DRIFT -------')
    print('X drift mean %.3f nm' % (x_error_mean*1000))
    print('X drift std dev %.3f nm' % (x_error_std_dev*1000))
    print('Y drift mean %.3f nm' % (y_error_mean*1000))
    print('Y drift std dev %.3f nm' % (y_error_std_dev*1000))
    print('-------- Z DRIFT -------')
    print('Z drift mean %.3f nm' % (z_error_mean*1000))
    print('Z drift std dev %.3f nm' % (z_error_std_dev*1000))

    # Transmission stats
    tra_mean = np.mean(single_trace_tra)
    tra_std = np.std(single_trace_tra)
    tra_cv = tra_std/tra_mean
    print('-------- Transmission -------')
    print('Trans mean %.6f V' % tra_mean)
    print('Trans std dev %.6f V' % tra_std)
    print('Trans Coef. of Variation %.3f %%' % (tra_cv*100))
    print
    monitor_mean = np.mean(single_trace_mon)
    monitor_std = np.std(single_trace_mon)
    monitor_cv = monitor_std/monitor_mean
    print('-------- Monitor -------')
    print('Monitor mean %.6f V' % monitor_mean)
    print('Monitor std dev %.6f V' % monitor_std)
    print('Monitor Coef. of Variation %.3f %%' % (monitor_cv*100))

    ##############################################################################
    # PREPARE DATA FOR PLOTTING
    # Load power calibration factor
    power_factor = parameters_dict['Power calibration factor (mW/V)']
    laser_power_trace = single_trace_mon*power_factor # in mW
    mean_power = np.mean(laser_power_trace)
    median_power = np.median(laser_power_trace)
    normalized_trans = single_trace_tra#/tra_mean
    filtered_norm = filtered#/tra_mean
    # filtered1k_norm = filtered1k#/tra_mean
    # filtered01k_norm = filtered01k#/tra_mean
    print('-------- Power -------')
    print('Power mean %.6f mW' % (mean_power))
    print('Power median %.6f mW' % (median_power))
    print('Power std dev %.6f mW' % (monitor_std*power_factor))
    print('Power Coef. of Variation %.3f %%' % (monitor_cv*100))

    ##############################################################################
    # PLOT
    # color_array = ['#B1B1B1', \
    #                '#EBBED3', \
    #                '#FFD4A8', \
    #                '#ADC1D8', \
    #                '#C1E672', \
    #                '#F2EF89']

    color_array = ["#9E9E9E", \
                   "#E795BB", \
                   "#FFB973", \
                   "#6599D4", \
                   "#B3D669", \
                   "#FFF949"]

    if plot_flag:
        print('\nPlotting results...')
        figures_folder = os.path.join(save_folder, 'figures')
        if not os.path.exists(figures_folder):
            os.makedirs(figures_folder)

        plt.rcParams.update({'font.size': 18})
        fig = plt.figure(figsize=(20, 11))
        gs = GridSpec(4, 2, figure=fig, width_ratios=[4, 1])
        gs.update(hspace=0.3, wspace=0.01)  # Adjust space between subplots

        # Main plots
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[1, 0])
        ax3 = fig.add_subplot(gs[2, 0])
        ax4 = fig.add_subplot(gs[3, 0])
        # Histogram plots
        ax1hist = fig.add_subplot(gs[0, 1])
        ax2hist = fig.add_subplot(gs[1, 1])
        ax3hist = fig.add_subplot(gs[2, 1])
        ax4hist = fig.add_subplot(gs[3, 1])

        # Set axis below plots for all axes
        axes_list = [ax1, ax2, ax3, ax4, ax1hist, ax2hist, ax3hist, ax4hist]
        for ax in axes_list:
            ax.set_axisbelow(True)
            ax.tick_params(axis='both', which='major', labelsize=18)
            
        # Plotting the data
        yaxis_transmission = [0.26, 0.30]
        ax1.plot(time_data, normalized_trans, color=color_array[0], alpha=1, label='Original (100 kHz)')
        ax1.plot(time_data, filtered, color='k', alpha=1, label='$f_{c}$=%d Hz' % cutoff_freq)
        ax1.set_xlim([t_min, t_max])
        ax1.set_ylim(yaxis_transmission)
        # ax1.set_ylabel('T/T$_{0}$', fontsize=18)
        ax1.set_ylabel('Transmission (V)', fontsize=18)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=18, ncol=2)
        # Add transmission histogram
        ax1hist.hist(normalized_trans, bins=20, range = yaxis_transmission, rwidth = 0.8, histtype='bar', \
                    alpha = 1, orientation='horizontal', density = True, linewidth=2, color=color_array[0])
        ax1hist.hist(filtered, bins=20, range = yaxis_transmission, rwidth = 0.8, histtype='bar', \
                    alpha = 1, orientation='horizontal', density = True, linewidth=2, color='k')
        ax1hist.set_ylim(yaxis_transmission)
        ax1hist.get_yaxis().set_visible(False)
        ax1hist.grid(True, alpha=0.3)

        yaxis_power = [21.25, 22.15]
        ax2.plot(time_data, laser_power_trace, color=color_array[0], label='Laser')
        ax2.axhline(median_power, color='k', linestyle='--', linewidth=2, label='Mean')
        ax2.set_xlim([t_min, t_max])
        ax2.set_ylim(yaxis_power)
        ax2.legend(loc='upper right', fontsize=18, ncol=2)
        ax2.set_ylabel('Power (mW)', fontsize=18)
        ax2.grid(True, alpha=0.3)
        # Add power histogram
        ax2hist.hist(laser_power_trace, bins=20, range = yaxis_power, rwidth = 0.8, histtype='bar', \
                    alpha = 1.0, orientation='horizontal', density = True, linewidth=2, color=color_array[0])
        ax2hist.set_ylim(yaxis_power)
        ax2hist.get_yaxis().set_visible(False)
        ax2hist.grid(True, alpha=0.3)
        # ax2hist.set_xscale('log')

        # Modified xy drift plot with histogram
        yaxis = [-0.02, 0.02]
        ax3.plot(time_xy, x_error, label='x', color=color_array[3])
        ax3.plot(time_xy, y_error, label='y', color=color_array[2])
        ax3.set_xlim([t_min, t_max])
        ax3.set_ylim(yaxis)
        ax3.set_ylabel(r'Drift ($\mu$m)', fontsize=18)
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper right', fontsize=18, ncol=2)
        # Add xy drift histogram
        ax3hist.hist(x_error, bins=20, range = yaxis, rwidth = 0.8, histtype='bar', \
                    alpha = 0.5, orientation='horizontal', density = True, linewidth=2, \
                    color=color_array[3])
        ax3hist.hist(y_error, bins=20, range = yaxis, rwidth = 0.8, histtype='bar', \
                    alpha = 0.5, orientation='horizontal', density = True, linewidth=2, \
                    color=color_array[2])
        yaxis_fit = np.arange(yaxis[0], yaxis[1], 0.0001)
        # Initialize a normal distribution with a given mean and std. dev.
        gauss_x = norm(loc = np.mean(x_error), scale = np.std(x_error))
        gauss_y = norm(loc = np.mean(y_error), scale = np.std(y_error))
        ax3hist.plot(gauss_x.pdf(yaxis_fit), yaxis_fit, color='k', 
                     linewidth=2, linestyle='--', label='x')
        ax3hist.plot(gauss_y.pdf(yaxis_fit), yaxis_fit, color=color_array[0], 
                     linewidth=2, linestyle='--', label='y')
        # ax3hist.set_xlabel('Counts', fontsize=18)
        # ax3hist.set_xlabel('Frequency', fontsize=18)
        ax3hist.set_ylim(yaxis)
        ax3hist.get_yaxis().set_visible(False)
        ax3hist.grid(True, alpha=0.3)
        ax3hist.legend(loc='upper right', fontsize=18, ncol=2)

        # Modified z drift plot with histogram
        yaxis = [-0.1, 0.1]
        ax4.plot(time_z, z_error, label='z', color=color_array[4])
        ax4.set_xlim([t_min, t_max])
        ax4.set_ylim(yaxis)
        ax4.set_xlabel('Time (min)', fontsize=18)
        ax4.set_ylabel(r'Drift ($\mu$m)', fontsize=18)
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc='upper right', fontsize=18)
        # Add z drift histogram
        ax4hist.hist(z_error, bins=20, range = yaxis, rwidth=0.8, histtype='bar', \
                    color=color_array[4], orientation='horizontal', density = True, \
                    alpha=1, linewidth=2)
        # Plot Gaussian fit
        yaxis_fit = np.arange(yaxis[0], yaxis[1], 0.0001)
        gauss_z = norm(loc = z_error_mean, scale = z_error_std_dev)
        ax4hist.plot(gauss_z.pdf(yaxis_fit), yaxis_fit, color='k', \
                     linewidth=2, linestyle='--')
        ax4hist.set_xlabel('Frequency', fontsize=18)
        ax4hist.set_ylim(yaxis)
        ax4hist.get_yaxis().set_visible(False)
        ax4hist.grid(True, alpha=0.3)

        figure_path = os.path.join(figures_folder, 'processed_trace_vs_time.png')
        plt.savefig(figure_path, dpi = 300, bbox_inches='tight')
        # # figure_path = os.path.join(save_folder, '%s_trace_vs_time.pdf' % figure_name)
        # # plt.savefig(figure_path, dpi = 300, bbox_inches='tight', format = 'pdf')

        ##########################################################################
        ############################## PLOT DETAILS ##############################
        ##########################################################################

        # plt.rcParams.update({'font.size': 18})
        # fig = plt.figure(figsize=(15, 11))
        # gs = GridSpec(4, 1, figure=fig)
        # gs.update(hspace=0.3)  # Adjust space between subplots

        # # Main plots
        # ax1 = fig.add_subplot(gs[0, 0])
        # ax2 = fig.add_subplot(gs[1, 0])
        # ax3 = fig.add_subplot(gs[2, 0])
        # ax4 = fig.add_subplot(gs[3, 0])

        # # Set axis below plots for all axes
        # axes_list = [ax1, ax2, ax3, ax4]
        # for ax in axes_list:
        #     ax.set_axisbelow(True)
        #     ax.tick_params(axis='both', which='major', labelsize=18)
            
        # # Plotting the data
        # yaxis_transmission = [-0.05, 0.35]
        # ax1.plot(time_data*60, normalized_trans, color=color_array[0], alpha=1, label='Original (100 kHz)')
        # ax1.plot(time_data*60, filtered, color='k', alpha=1, label='$f_{c}$=%d Hz' % cutoff_freq)
        # ax1.set_xlim([t_min*60, t_max*60])
        # ax1.set_ylim(yaxis_transmission)
        # # ax1.set_ylabel('T/T$_{0}$', fontsize=18)
        # ax1.set_ylabel('Transmission (V)', fontsize=18)
        # ax1.grid(True, alpha=0.3)
        # ax1.legend(loc='upper left', fontsize=18, ncol=1)

        # yaxis_power = [21.25, 22.15]
        # ax2.plot(time_data*60, laser_power_trace, color=color_array[0], label='Laser')
        # ax2.axhline(median_power, color='k', linestyle='--', linewidth=2, label='Mean')
        # ax2.set_xlim([t_min*60, t_max*60])
        # ax2.set_ylim(yaxis_power)
        # ax2.legend(loc='upper right', fontsize=18, ncol=2)
        # ax2.set_ylabel('Power (mW)', fontsize=18)
        # ax2.grid(True, alpha=0.3)

        # # Modified xy drift plot with histogram
        # yaxis = [-0.02, 0.02]
        # ax3.plot(time_xy*60, x_error, label='x', color=color_array[3])
        # ax3.plot(time_xy*60, y_error, label='y', color=color_array[2])
        # ax3.set_xlim([t_min*60, t_max*60])
        # ax3.set_ylim(yaxis)
        # ax3.set_ylabel(r'Drift ($\mu$m)', fontsize=18)
        # ax3.grid(True, alpha=0.3)
        # ax3.legend(loc='upper right', fontsize=18, ncol=2)

        # # Modified z drift plot with histogram
        # yaxis = [-0.1, 0.1]
        # ax4.plot(time_z*60, z_error, label='z', color=color_array[4])
        # ax4.set_xlim([t_min*60, t_max*60])
        # ax4.set_ylim(yaxis)
        # ax4.set_xlabel('Time (s)', fontsize=18)
        # ax4.set_ylabel(r'Drift ($\mu$m)', fontsize=18)
        # ax4.grid(True, alpha=0.3)
        # ax4.legend(loc='upper right', fontsize=18)

        # figure_path = os.path.join(figures_folder, 'processed_trace_vs_time_detail.png')
        # plt.savefig(figure_path, dpi = 300, bbox_inches='tight')
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

print('\n--------------------- END OF PROCESSING ---------------------\n')