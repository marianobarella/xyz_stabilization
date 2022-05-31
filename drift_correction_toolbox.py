# -*- coding: utf-8 -*-
"""
Created on Tue May 24, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt
import os
# import warnings
# from scipy.optimize import OptimizeWarning
# warnings.filterwarnings("ignore", message = 'Covariance not estimated', category = OptimizeWarning)

DEBUG = False
plt.ioff()

#=====================================

# Functions definition

#=====================================

def gaussian_2D(xy_tuple, amplitude, xo, yo, w0_x, w0_y, offset):
    (x, y) = xy_tuple
    g = offset + amplitude*np.exp( -2*( ((x-xo)/w0_x)**2 + ((y-yo)/w0_y)**2 ) )
    return g.ravel()

def fit_with_gaussian(frame_intensity, frame_coordinates, pixel_size_x_nm, pixel_size_y_nm):
    # pixel_size should be in um
    pixel_size_x = pixel_size_x_nm/1000
    pixel_size_y = pixel_size_y_nm/1000
    # image parameters
    number_of_pixels_x, number_of_pixels_y = frame_intensity.shape
    x = frame_coordinates[0, :, :]
    y = frame_coordinates[1, :, :]
    # normalize
    frame_min = np.min(frame_intensity)
    frame_max = np.max(frame_intensity)
    frame_norm = ( frame_intensity - frame_min ) / ( frame_max - frame_min )
    # reshape
    data = frame_norm.reshape(number_of_pixels_x*number_of_pixels_y)
    # perform fitting
    # initial paramters to fit amplitude, xo, yo, wx, wy, offset
    x_coord_max, y_coord_max = np.unravel_index(np.argmax(frame_intensity, axis=None), \
                                                frame_intensity.shape)
    print(x_coord_max, y_coord_max)
    initial_guess = [1, x_coord_max, y_coord_max, 0.350/pixel_size_x, 0.350/pixel_size_y, 0.2]
    popt, pcov = opt.curve_fit(gaussian_2D, (x, y), data, p0 = initial_guess, verbose = 1)
    # retrieve parameters
    amplitude_fitted, \
        x_fitted, \
        y_fitted, \
        w0x_fitted, \
        w0y_fitted, \
        offset_fitted = popt
    print(popt)
    # map to sample size
    x_fitted = x_fitted*pixel_size_x
    y_fitted = y_fitted*pixel_size_y
    w0x_fitted = w0x_fitted*pixel_size_x
    w0y_fitted = w0y_fitted*pixel_size_y
    
    if DEBUG:
        plt.figure()
        ax = plt.gca()
        image_size_x = number_of_pixels_x*pixel_size_x
        image_size_y = number_of_pixels_y*pixel_size_y
        ax.imshow(frame_norm, origin = 'lower', extent=(0, image_size_x, 0, image_size_y))
        ax.plot(y_fitted, x_fitted, 'o', markersize = 6, markerfacecolor = 'w', markeredgecolor = 'k')
        plt.xlabel('Distance (µm)')
        plt.ylabel('Distance (µm)')
        data_folder = 'D:\\daily_data'
        saving_filename = 'fiducial_2D_gaussian_fit.png'
        save_path = os.path.join(data_folder, saving_filename)
        plt.savefig(save_path)
        plt.close()
    
    return x_fitted, y_fitted, w0x_fitted, w0y_fitted