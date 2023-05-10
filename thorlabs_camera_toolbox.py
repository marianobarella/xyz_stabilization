# -*- coding: utf-8 -*-
"""
Created on Tue March 1, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import os
import sys
import time
from PIL import Image as pil
import numpy as np

# add DLLs folder to environment
absolute_path_to_file_directory = os.path.dirname(os.path.abspath(__file__))
absolute_path_to_dlls = os.path.join(absolute_path_to_file_directory, 'Thorlabs_SDK_dlls\\64_lib')
os.environ['PATH'] = absolute_path_to_dlls + os.pathsep + os.environ['PATH']

# serial number of the cameras we have
mono_serial_number_str = '16433'
color_serial_number_str = '16263'

# import Thorlabs SDK dll
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, TLCamera
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE
from thorlabs_tsi_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK

#=====================================

# Function Definitions

#=====================================

def load_Thorlabs_SDK_cameras():
    # create SDK object. Important: only call it once!
    camera_constructor = TLCameraSDK()
    return camera_constructor

def init_Thorlabs_color_camera(camera_constructor):
    # initialize Thorlabs color cameras
    # get Thorlabs camera parameters
    list_of_cameras = list_cameras(camera_constructor)
    if not list_of_cameras == None:
        color_cam, color_cam_flag = open_color_camera(camera_constructor, list_of_cameras)
        color_cam_sensor_width_pixels, color_cam_sensor_height_pixels, \
        color_cam_sensor_pixel_width_um, color_cam_sensor_pixel_height_um = get_camera_param(color_cam)
        # create SDK object. Important: only call it once!
        mono_to_color_constructor = MonoToColorProcessorSDK()
        mono_to_color_processor = mono_to_color_constructor.create_mono_to_color_processor(
            SENSOR_TYPE.BAYER, 
            color_cam.color_filter_array_phase, 
            color_cam.get_color_correction_matrix(),
            color_cam.get_default_white_balance_matrix(),
            color_cam.bit_depth)
    return color_cam, \
        color_cam_flag, \
        color_cam_sensor_width_pixels, \
        color_cam_sensor_height_pixels, \
        color_cam_sensor_pixel_width_um, \
        color_cam_sensor_pixel_height_um, \
        mono_to_color_constructor, \
        mono_to_color_processor
        
def init_Thorlabs_mono_camera(camera_constructor):
    # initialize Thorlabs mono cameras
    # get Thorlabs camera parameters
    list_of_cameras = list_cameras(camera_constructor)
    if not list_of_cameras == None:
        mono_cam, mono_cam_flag = open_mono_camera(camera_constructor, list_of_cameras)
        mono_cam_sensor_width_pixels, mono_cam_sensor_height_pixels, \
        mono_cam_sensor_pixel_width_um, mono_cam_sensor_pixel_height_um = get_camera_param(mono_cam)
    return mono_cam, \
        mono_cam_flag, \
        mono_cam_sensor_width_pixels, \
        mono_cam_sensor_height_pixels, \
        mono_cam_sensor_pixel_width_um, \
        mono_cam_sensor_pixel_height_um

def list_cameras(camera_constructor):
    # list available cameras
    list_of_cameras = camera_constructor.discover_available_cameras()
    if len(list_of_cameras) < 1:
        print("\nNo cameras detected.")
        list_of_cameras = None
    return list_of_cameras

def open_mono_camera(camera_constructor, list_of_cameras):
    if mono_serial_number_str in list_of_cameras: 
        print('\nMonochrome Zelux camera found. S/N %s' % mono_serial_number_str) 
        mono_cam = camera_constructor.open_camera(mono_serial_number_str)
        mono_cam_flag = True
        print('Object created.')
        print('Model', mono_cam.model)
    else:
        mono_cam_flag = False
        mono_cam = None
        print('\nMonochrome Zelux camera was NOT found. \nObject NOT created.') 
    return mono_cam, mono_cam_flag

def open_color_camera(camera_constructor, list_of_cameras):
    if color_serial_number_str in list_of_cameras: 
        print('\nColor Zelux camera found. S/N %s' % color_serial_number_str) 
        color_cam = camera_constructor.open_camera(color_serial_number_str)
        color_cam_flag = True
        print('Object created.')
        print('Model', color_cam.model)
    else:
        color_cam_flag = False
        color_cam = None
        print('\nColor Zelux camera was NOT found. \nObject NOT created.')
    return color_cam, color_cam_flag

def set_camera_continuous_mode(camera):
    print('Setting camera continuous mode...')
    camera.frames_per_trigger_zero_for_unlimited = 0
    camera.arm(2)
    camera.issue_software_trigger()
    time.sleep(0.4) # waiting time needed before setting exposure time
    return

def stop_camera(camera):
    print('Disarming camera... Clearing queue...')
    # first call disables the camera, second call clears the queue
    camera.disarm()
    camera.disarm()
    time.sleep(0.4) # waiting time needed before setting exposure time
    return

def set_camera_one_picture_mode(camera):
    print('Setting camera to single picture mode...')
    # first call disables the camera, second call clears the queue
    camera.frames_per_trigger_zero_for_unlimited = 1
    camera.arm(1)
    camera.issue_software_trigger()
    time.sleep(0.4) # waiting time needed before setting exposure time
    return

def set_exp_time(camera, exposure_time_ms):
    print('Setting camera parameters...')
    exposure_time_us = int(exposure_time_ms*1000)
    camera.exposure_time_us = exposure_time_us # has to be an int type variable
    frame_time = camera.frame_time_us/1e3
    print('Exposure time set to', (exposure_time_us/1000), 'ms')
    print('Frame time is', frame_time, 'ms')
    # set polling time to a little bit higher than frame time
    # if set below the frame time it will not be possible to retrieve an image
    # you don't want to block the camera for long periods of time
    camera.image_poll_timeout_ms = round(frame_time*1.0)
    return frame_time

def get_camera_param(camera):
    return camera.sensor_width_pixels, camera.sensor_height_pixels, \
       camera.sensor_pixel_width_um, camera.sensor_pixel_height_um

def get_mono_image(camera):
    frame = camera.get_pending_frame_or_null()
    if frame is not None:
        # print("Frame #{} received.".format(frame.frame_count))
        # NOTE: image_buffer is a temporary memory buffer that may be overwritten during the next call
        # to get_pending_frame_or_null. The following line makes a deep copy of the image data to a PIL
        # image object:
        mono_image = np.copy(frame.image_buffer)
        mono_image_pil = pil.fromarray(mono_image)
    else:
        print("Timeout reached during polling. Program exiting...")
        stop_camera(camera)
        mono_image = None
        mono_image_pil = None
    return mono_image, mono_image_pil

def get_color_image(camera, mono_to_color_processor):
    color_cam_sensor_width_pixels, color_cam_sensor_height_pixels, \
       sensor_pixel_width_um, sensor_pixel_height_um = get_camera_param(camera)
    frame = camera.get_pending_frame_or_null()
    if frame is not None:
        color_image_data = mono_to_color_processor.transform_to_24(frame.image_buffer,
                                                                         color_cam_sensor_width_pixels,
                                                                         color_cam_sensor_height_pixels)
        color_image_data = color_image_data.reshape(color_cam_sensor_height_pixels, \
                                                    color_cam_sensor_width_pixels, \
                                                    3)
        color_image_pil = pil.fromarray(color_image_data, mode='RGB')
    else:
        print("Timeout reached during polling. Program exiting...")
        stop_camera(camera)
        color_image_data = None
        color_image_pil = None
    return color_image_data, color_image_pil

def get_image(camera, mono_to_color_processor, mono_color_string):
    if mono_color_string == 'mono':
        image_data, image_pil = get_mono_image(camera)
    elif mono_color_string == 'color':
        image_data, image_pil = get_color_image(camera, mono_to_color_processor)
    else:
        print('\nWARNING! Select properly mono_color_string.')
        print('mono_color_string is:', mono_color_string)
        print('Allowed values are: mono OR color')
        image_data = None
        image_pil = None
    return image_data, image_pil

def dispose_cam(camera_object):
    print('Closing camera...')
    # clean up cameras instance
    TLCamera.dispose(camera_object)
    return

def dispose_color_processor(mono_to_color_processor):
    print('Closing color processsor...')
    # clean up color processor instance
    MonoToColorProcessorSDK.dispose(mono_to_color_processor)
    return

def dispose_color_sdk(mono_to_color_constructor):
    print('Closing color SDK instance...')
    # clean up color SDK instance
    MonoToColorProcessorSDK.dispose(mono_to_color_constructor)
    return

def dispose_sdk(camera_constructor):
    print('Closing SDK instance...')
    # clean up Thorlabs SDK instance
    TLCameraSDK.dispose(camera_constructor)
    return

def dispose_all(mono_cam_flag, mono_cam, color_cam_flag, color_cam, \
                mono_to_color_processor, mono_to_color_constructor, \
                camera_constructor):
    if mono_cam_flag:
        dispose_cam(mono_cam)
    if color_cam_flag:
        dispose_cam(color_cam)
        dispose_color_processor(mono_to_color_processor)
        dispose_color_sdk(mono_to_color_constructor)
    dispose_sdk(camera_constructor)
    return

#=====================================

# Main program

#=====================================

if __name__ == '__main__':
        
    camera_constructor = load_Thorlabs_SDK_cameras()
    mono_cam, mono_cam_flag, color_cam, color_cam_flag = list_cameras(camera_constructor)
    if mono_cam_flag:
        mono_cam_sensor_width_pixels, mono_cam_sensor_height_pixels, \
        mono_cam_sensor_pixel_width_um, mono_cam_sensor_pixel_height_um = get_camera_param(mono_cam)
        mono_to_color_processor = None
        mono_to_color_constructor = None
        camera = mono_cam
    if color_cam_flag:
        color_cam_sensor_width_pixels, color_cam_sensor_height_pixels, \
        color_cam_sensor_pixel_width_um, color_cam_sensor_pixel_height_um = get_camera_param(color_cam)
        mono_to_color_constructor, mono_to_color_processor = init_Thorlabs_color_cameras(color_cam)
        camera = color_cam
    
    if not (color_cam_flag or mono_cam_flag):
        print('\nNo cameras detected. Closing program...')
        dispose_sdk(camera_constructor)
        sys.exit()
        
    exposure_time_ms = 53.05 # in ms   
    number_of_frames = 10 

    # print(mono_cam.roi_range)
    print('\nGetting images...')

    if mono_cam_flag:
        print('\nTaking pictures with MONO camera')
        set_camera_continuous_mode(mono_cam)
        frame_time = set_exp_time(mono_cam, exposure_time_ms)
        for i in range(number_of_frames):
            mono_image, _ = get_image(mono_cam, mono_to_color_processor, 'mono')

    if color_cam_flag:
        print('\nTaking pictures with COLOR camera')
        set_camera_continuous_mode(color_cam)
        frame_time = set_exp_time(color_cam, exposure_time_ms)
        for i in range(number_of_frames):
            color_image_np, _ = get_image(color_cam, mono_to_color_processor, 'color')

    stop_camera(camera)
    # camera.roi = old_roi  # reset the roi back to the original roi
    
    dispose_all(mono_cam_flag, mono_cam, color_cam_flag, color_cam, \
                mono_to_color_processor, mono_to_color_constructor, \
                camera_constructor)

