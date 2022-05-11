# -*- coding: utf-8 -*-
"""
Created on Wed May 11, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import pco
import numpy as np

#=====================================

# Other functions Definition

#=====================================

def fancy_print(dictionary):
    for key in dictionary.keys():
        print('{}: {}'.format(key, dictionary[key]))
    return

#=====================================

# pco Camera Class Definition

#=====================================

class pco_camera(object):
    def __init__(self, debug = 'off', timestamp_flag = 'off'):
        self.timestamp_flag = timestamp_flag
        self.debug_mode = debug
        print('Connecting to pco.panda camera...')
        self.camera = pco.Camera(debuglevel = self.debug_mode, timestamp = self.timestamp_flag)
        self.get_info()
        self.get_pixel_correction_mode()
        self.get_filter_noise_mode()
        self.recorder_set = False
        return

    def get_info(self):
        info = self.camera.sdk.get_camera_type()
        health = self.camera.sdk.get_camera_health_status()
        fancy_print(info)
        fancy_print(health)
        return
    
    def is_cam_busy(self):
        if not self.camera.sdk.get_camera_busy_status()['busy status'] == 'ready':
            status = True
        else:
            status = False
        return status        
    
    def get_camera_temp(self):
        dict_temp = self.camera.sdk.get_temperature()
        fancy_print(dict_temp)
        self.sensor_temp = dict_temp['sensor temperature']
        self.cam_temp = dict_temp['camera temperature']
        self.power_temp = dict_temp['power temperature']
        return self.sensor_temp, self.cam_temp, self.power_temp

    def get_pixel_correction_mode(self):
        self.pixel_correction_mode = self.camera.sdk.get_hot_pixel_correction_mode()['hot pixel correction mode']
        if self.pixel_correction_mode == 'on':
            self.pixel_correction_on = True
        else:
            self.pixel_correction_on = False
        fancy_print(self.camera.sdk.get_hot_pixel_correction_mode())
        return

    def toggle_pixel_correction_mode(self):
        if self.pixel_correction_on:
            self.camera.sdk.set_hot_pixel_correction_mode('off')
            self.get_pixel_correction_mode()
        else:
            self.camera.sdk.set_hot_pixel_correction_mode('on')
            self.get_pixel_correction_mode()
        return
    
    def get_filter_noise_mode(self):
        self.filter_noise_mode = self.camera.sdk.get_noise_filter_mode()['noise filter mode']
        if self.filter_noise_mode == 'on':
            self.filter_noise_on = True
        else:
            self.filter_noise_on = False
        fancy_print(self.camera.sdk.get_noise_filter_mode())
        return

    def toggle_filter_noise_mode(self):
        if self.filter_noise_on:
            self.camera.sdk.set_noise_filter_mode('off')
            self.get_filter_noise_mode()
        else:
            self.camera.sdk.set_noise_filter_mode('on')
            self.get_filter_noise_mode()
        return    
    
    def set_exp_time(self, exp_time_ms):
        print('Setting camera exposure time...')
        if exp_time_ms < 0.01:
            print('{} ms exceeds the minimum possible value.'.format(exp_time_ms))
            return
        if exp_time_ms > 5000:
            print('{} ms exceeds the maximum possible value.'.format(exp_time_ms))
            return
        self.exp_time = float(exp_time_ms/1000)
        self.camera.set_exposure_time(self.exp_time) # in s
        print('Exposure time set to', exp_time_ms, 'ms')
        return
    
    def set_binning(self, n):
        print('Setting squared binning to {}x{} pixels...'.format(n, n))
        self.camera.configuration = {'binning': (n, n)}
        print(self.camera.sdk.get_binning())
        return
    
    def set_roi(self, starting_row, starting_col, final_row, final_col):
        self.roi_height = final_row - starting_row
        self.roi_width = final_col - starting_col
        if self.roi_height < 64:
            print('Minimum possible ROI height is 64. ROI has not been set.')
            return
        if self.roi_width < 16:
            print('Minimum possible ROI width is 16. ROI has not been set.')
            return
        if not np.mod(self.roi_height, 32) == 0:
            print('ROI height must be multiple of 32. ROI has not been set.')
            return
        if not np.mod(self.roi_height, 8) == 0:
            print('ROI width must be multiple of 8. ROI has not been set.')
            return
        print('Setting roi to {}x{} pixels...'.format(self.roi_height, self.roi_width))
        self.camera.sdk.set_roi(starting_row, starting_col, final_row, final_col)
        self.get_roi()
        return
    
    def get_roi(self):
        self.roi_shape = self.camera.sdk.get_roi()
        fancy_print(self.roi_shape)
        return
    
    def get_image(self):
        if self.recorder_set:
            image, metadata = self.camera.image()
        else:
            print('Recorder has to be configured. Run config_recorder first.')
        return image, metadata

    def config_recorder(self, num_of_images = 4, rec_mode = 'ring buffer'):
        # minimum number of images that can be set when in ring buffer mode is 4
        print('Setting recorder parameters...')
        self.camera.record(number_of_images = num_of_images, mode = rec_mode)
        self.recorder_set = True
        return

    def reboot(self):
        print('Rebooting camera...')
        self.camera.sdk.reboot_camera()
        return

    def stop(self):
        print('Stopping camera...')
        self.camera.stop()
        if not self.is_cam_busy():
            self.recorder_set = False
            print('Recording succesfully stopped.')
        return

#=====================================

# Main program

#=====================================

if __name__ == '__main__':
        
    # cam = pco_camera(debug = 'verbose', timestamp_flag = 'on')
    cam = pco_camera()
