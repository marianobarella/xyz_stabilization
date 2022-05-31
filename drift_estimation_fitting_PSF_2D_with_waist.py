#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Drift estimation
Fitting 2D gaussian in a time series

Fribourg, Switzerland, 18/02/2022

@author: Mariano Barella
"""

import numpy as np
import matplotlib.pyplot as plt
import scipy.optimize as opt
import os
from tifffile import imread
import time

##################################################################

def gaussian_2D(xy_tuple, amplitude, xo, yo, w0_x, w0_y, offset):
    (x, y) = xy_tuple
    g = offset + amplitude*np.exp( -2*( ((x-xo)/w0_x)**2 + ((y-yo)/w0_y)**2 ) )
    return g.ravel()

# definition of log-likelihood function (avoid using np.prod, could return 0.0)
def log_likelihood(theta_param, data):
    amplitude, xo, yo, w0_x, w0_y, offset = theta_param
    pdf_data = gaussian_2D(data, amplitude, xo, yo, w0_x, w0_y, offset)
    log_likelihood = -np.sum(np.log(pdf_data)) # use minus to minimize (instead of maximize)
    return log_likelihood

def find_best(sample, log_likelihood, init_params):
    # prepare function to store points the method pass through
    road_to_convergence = list()
    road_to_convergence.append(init_params)
    def callback_fun(X):
        road_to_convergence.append(list(X))
        return 
    out = opt.minimize(log_likelihood, 
                        init_params, 
                        args = (sample), 
                        method = 'Nelder-Mead',
                        callback = callback_fun,
                        options = {'maxiter':5000, 
                                    'xatol':1e-16,
                                    'fatol': 1e-16,
                                    'disp':True})
    return out

##################################################################

plt.ioff()

VERBOSITY = False
PLOT = False

data_folder = 'C:\datos_mariano\posdoc\drift_correction_proposal\drift_estimation'
filename = 'times_series_15sec_120frames_blue_ch_ROI.tif'

# working_folder = os.path.join(local_folder, data_folder)
filepath = os.path.join(data_folder, filename)
img = imread(filepath)

# image parameters
max_frame, number_of_pixels_x, number_of_pixels_y = img.shape
pixel_size_x = 0.0781 # in um
pixel_size_y = 0.0781 # in um
image_size_x = number_of_pixels_x*pixel_size_x
image_size_y = number_of_pixels_y*pixel_size_y

# Create x and y indices
x = np.arange(0, number_of_pixels_x)
y = np.arange(0, number_of_pixels_y)
x, y = np.meshgrid(x, y)

# amplitude, xo, yo, sigma_x, sigma_y, offset
initial_guess = [1, number_of_pixels_x/2, number_of_pixels_y/2, 0.5, 0.5, 0.05]

time_consumed_array = np.zeros(max_frame)
xy_drift = np.zeros((max_frame, 2))
w0_drift = np.zeros((max_frame, 2))
for i in range(max_frame):
    frame = img[i, :, :]
    frame_min = np.min(frame, axis = (0,1))
    frame_max = np.max(frame, axis = (0,1))
    frame_norm = ( frame - frame_min ) / ( frame_max - frame_min )
    start_time = time.time()
    # popt, pcov = opt.curve_fit(gaussian_2D, (x, y), frame_norm.reshape(number_of_pixels_x*number_of_pixels_y), p0 = initial_guess)
    popt = find_best(frame_norm.reshape(number_of_pixels_x*number_of_pixels_y), \
                    log_likelihood, initial_guess)
    
    end_time = time.time()
    print(popt)
    amplitude_fitted, x_fitted, y_fitted, \
        w0x_fitted, w0y_fitted, offset_fitted = popt
    x_fitted = x_fitted*pixel_size_x
    y_fitted = y_fitted*pixel_size_y
    w0x_fitted = w0x_fitted*pixel_size_x
    w0y_fitted = w0y_fitted*pixel_size_y

    time_consumed = end_time - start_time
    time_consumed_array[i] = time_consumed
    
    if VERBOSITY:
        print('x_0: %.3g um' % (x_fitted))
        print('y_0: %.3g um' % (y_fitted))
        print('wo_x: %.3g um' % (w0x_fitted))
        print('wo_y: %.3g um' % (w0y_fitted))
        print('amplitude: %.3g' % (amplitude_fitted))
        print('offset: %.3g' % (offset_fitted))
        print("--- %.3g seconds ---" % time_consumed)
    
    xy_drift[i, :] = [x_fitted, y_fitted]
    w0_drift[i, :] = [w0x_fitted, w0y_fitted]
    
    if PLOT:
        fig, ax = plt.subplots(1, 1)
        ax.imshow(frame_norm, origin = 'lower', extent=(0, image_size_x, 0, image_size_y))
        ax.plot(x_fitted, y_fitted, 'o', markersize = 6, markerfacecolor = 'w', markeredgecolor = 'k')
        plt.xlabel('Distance (µm)')
        plt.ylabel('Distance (µm)')
        saving_filename = 'loaded_image_with_2D_gaussian_fit_frame%03d.png' % i
        save_folder = os.path.join(data_folder, 'figures')
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        save_path = os.path.join(save_folder, saving_filename)
        plt.savefig(save_path)
        plt.close()

# plot drift
time = np.arange(0,max_frame)*15/60 # in s
xy_drift_shift = xy_drift - xy_drift[0,:]
plt.figure()
plt.plot(time, xy_drift_shift[:,0], 'o', color = 'C0', label = 'x')
plt.plot(time, xy_drift_shift[:,1], 's', color = 'C1', label = 'y')
plt.legend(loc = 2)
plt.xlabel('Time (min)')
plt.ylabel('Shift (µm)')
saving_filename = 'xy_drift_15sec_120frames.png'
save_path = os.path.join(data_folder, saving_filename)
plt.savefig(save_path)
plt.close()

time = np.arange(0,max_frame)*15/60 # in s
w0_drift_shift = (w0_drift - w0_drift[0,:])*1000 # to nm
plt.figure()
plt.plot(time, w0_drift_shift[:,0], 'o', color = 'C0', label = 'x')
plt.plot(time, w0_drift_shift[:,1], 's', color = 'C1', label = 'y')
plt.legend(loc = 2)
plt.xlabel('Time (min)')
plt.ylabel('$\Delta$w$_{0}$ (nm)')
saving_filename = 'w0_drift_15sec_120frames.png'
save_path = os.path.join(data_folder, saving_filename)
plt.savefig(save_path)
plt.close()

# time compsuption statistics
time_consumed_array = time_consumed_array*1e3 # to ms
avg = np.mean(time_consumed_array)
std = np.std(time_consumed_array, ddof = 1)
print('\nTime consumed (%.1f ± %.1f) ms' % (avg, std))
num_of_bins = 15
range_of_hist = [1,30]
bin_size = (range_of_hist[1] - range_of_hist[0])/num_of_bins
print('\nBin size', bin_size)

plt.figure()
ax = plt.gca()
out_hist = ax.hist(time_consumed_array, bins=num_of_bins, density=True, \
                    range=range_of_hist, rwidth = 1, \
                    align='mid',color='C1', alpha = 0.8, edgecolor='k', \
                    label = '(%.1f ± %.1f) ms' % (avg, std))
plt.legend(loc = 1)
plt.xlabel('Time consumed (ms)')
plt.ylabel('Frequency')
saving_filename = 'time_consumption_2D_gaussian_fitting.png'
save_path = os.path.join(data_folder, saving_filename)
plt.savefig(save_path)
plt.close()

print('Done.')

