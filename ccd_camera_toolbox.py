import pylablib
pylablib.par["devices/dlls/andor_sdk2"] = "C:\\Program Files\\Andor SOLIS"
from pylablib.devices import Andor

print(Andor.AndorSDK2.get_cameras_number())
cam = Andor.AndorSDK2Camera()
# cam = Andor.AndorSDK2Camera(idx = 0, temperature=-50, fan_mode="full")

cam.open()

print(cam.is_opened())

print(cam.get_device_info())
# print(cam.get_detector_size()) # 1024x256
# print(cam.get_roi())
print(cam.get_status())

print(cam.get_temperature())

# print(cam.get_all_amp_modes())

# print(cam.get_max_vsspeed())

print(cam.get_temperature())

print('acq in progress', cam.acquisition_in_progress())

print('cooler',cam.is_cooler_on())
# print(cam.set_cooler(on=False))
# print('cooler',cam.is_cooler_on())
# print(cam.set_cooler(on=True))
# print('cooler',cam.is_cooler_on())
fan_mode = 'full'
cam.set_fan_mode(fan_mode)


print(cam.get_temperature_range()) # min -120 max -10 °C

print(cam.get_amp_mode(full=True)) # current

# hsspeed can be 0, 1 or 2 corresponding to hsspeed of 3.0, 1.0 and 0.05 MHz
# preamp can be 0, 1 or 2 corresponding to a preamp gain of 1.0, 2.0 or 4.0
# print(cam.set_amp_mode(channel = 0, oamp = 0, hsspeed = hsspeed_index, preamp = preamp_index))

# set_fan_mode(mode)
# set_cooler(on=True)

# set_temperature(temperature, enable_cooler=True)

# print(cam.get_attribute_value("CameraAcquiring"))  # check if the camera is acquiring

# print(cam.set_attribute_value("ExposureTime", 0.3))



cam.set_exposure(1000e-3)  # set 10ms exposure
print(cam.get_exposure())
print(cam.get_frame_timings())



print(cam.get_temperature())

cam.set_read_mode('fvb')
cam.set_read_mode('image')

# setup_acquisition(mode=None, nframes=None)
# cam.start_acquisition()  # start acquisition (automatically sets it up as well)
#     while True: # acquisition loop
#         cam.wait_for_frame()  # wait for the next available frame
#         frame = cam.read_oldest_image()  # get the oldest image which hasn't been read yet
#         # ... process frame ...
# stop_acquisition()
# get_acquisition_progress()

img = cam.snap()  # grab a single frame
print(img)
# images = cam.grab(10)  # grab 10 frames (return a list of frames)

# pylablib.devices.Andor.AndorSDK2.TAcqProgress

cam.close()


