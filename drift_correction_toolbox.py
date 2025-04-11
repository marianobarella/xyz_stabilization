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
from scipy import ndimage
import matplotlib.pyplot as plt
import os
from PIL import Image
from timeit import default_timer as timer

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
    # pixel_size should be in nm
    # now, convert to um
    pixel_size_x_um = pixel_size_x_nm/1000
    pixel_size_y_um = pixel_size_y_nm/1000
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
    ############ perform fitting ############
    # spatial coordinates are in term of pixels at this point
    # initial parameters to fit amplitude, xo, yo, wx, wy, offset
    x_coord_max, y_coord_max = np.unravel_index(np.argmax(frame_intensity, axis = None), \
                                                frame_intensity.shape)
    x_coord_max += np.min(x)
    y_coord_max += np.min(y)
    initial_guess = [0.9, x_coord_max, y_coord_max, 5, 5, 0.1]
    # set bounds
    all_bounds = ([0, np.min(x), np.min(y), 0, 0, 0], [1, np.max(x), np.max(y), 100, 100, 1])
    # start_time = timer()
    popt, pcov = opt.curve_fit(gaussian_2D, (x, y), data, p0 = initial_guess, bounds = all_bounds)
    # end_time = timer()
    # print(end_time - start_time)
    # retrieve parameters
    amplitude_fitted, \
        x_fitted, \
        y_fitted, \
        w0x_fitted, \
        w0y_fitted, \
        offset_fitted = popt
    # map to sample size
    x_fitted = x_fitted*pixel_size_x_um
    y_fitted = y_fitted*pixel_size_y_um
    w0x_fitted = w0x_fitted*pixel_size_x_um
    w0y_fitted = w0y_fitted*pixel_size_y_um
    
    if DEBUG:
        plt.figure()
        ax = plt.gca()
        image_size_x = number_of_pixels_x*pixel_size_x_um
        image_size_y = number_of_pixels_y*pixel_size_y_um
        ax.imshow(frame_norm, origin = 'lower', extent=(0, image_size_x, 0, image_size_y))
        ax.plot(y_fitted, x_fitted, 'o', markersize = 6, markerfacecolor = 'w', markeredgecolor = 'k')
        plt.xlabel('Distance (µm)')
        plt.ylabel('Distance (µm)')
        data_folder = 'D:\\daily_data'
        saving_filename = 'fiducial_2D_gaussian_fit.png'
        save_path = os.path.join(data_folder, saving_filename)
        plt.savefig(save_path)
        plt.close()
    # returning in um as it was multiplied by the pixel size
    return x_fitted, y_fitted, w0x_fitted, w0y_fitted

def fit_with_gaussian_confocal(confocal_image, x, y, threshold):
    # normalize image
    image_min = np.min(confocal_image)
    image_max = np.max(confocal_image)
    image_norm = ( confocal_image - image_min ) / ( image_max - image_min )
    # filter image
    image_norm_filtered = np.where(image_norm > threshold, image_norm, 0)
    # reshape
    image_raveled = image_norm_filtered.ravel()
    ############ perform fitting ############
    # spatial coordinates are in term of pixels at this point
    # initial parameters to fit amplitude, xo, yo, wx, wy, offset
    x_coord_max, y_coord_max = np.unravel_index(np.argmax(confocal_image, axis = None), \
                                                confocal_image.shape)
    initial_guess = [1, x_coord_max, y_coord_max, 1, 1, 0]
    # set bounds
    all_bounds = ([0, np.min(x), np.min(y), 0, 0, 0], [1, np.max(x), np.max(y), 100, 100, 1])
    xv, yv = np.meshgrid(x, y)
    xy_grid = np.vstack((xv.ravel(), yv.ravel()))
    popt, pcov = opt.curve_fit(gaussian_2D, xy_grid, image_raveled, p0 = initial_guess, bounds = all_bounds)
    # retrieve parameters
    amplitude_fitted, \
        x_fitted, \
        y_fitted, \
        w0x_fitted, \
        w0y_fitted, \
        offset_fitted = popt
    return x_fitted, y_fitted

def meas_center_of_mass_confocal(confocal_image, threshold):
    # normalize image
    image_min = np.min(confocal_image)
    image_max = np.max(confocal_image)
    image_norm = ( confocal_image - image_min ) / ( image_max - image_min )
    # filter image
    image_norm_filtered = np.where(image_norm > threshold, image_norm, 0)
    cm_coords = ndimage.measurements.center_of_mass(image_norm_filtered)
    x_cm = cm_coords[1] # in pixels
    y_cm = cm_coords[0] # in pixels
    return x_cm, y_cm

if __name__ == '__main__':

    filepath = 'D:\\daily_data\\image_pco_test2022-05-31_14-08-33.tiff'
    img = Image.open(filepath)
    imarray = np.array(img)
    crop = imarray[640:670, 945:975]
    number_of_pixels_x, number_of_pixels_y = crop.shape
    x = np.arange(number_of_pixels_x)
    y = np.arange(number_of_pixels_y)
    xy_grid = np.array(np.meshgrid(x, y))
    
    fit_with_gaussian(crop, xy_grid, 65, 65)
    
    plt.figure()
    plt.imshow(crop)
    plt.show()
    