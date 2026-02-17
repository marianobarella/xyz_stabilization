import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from src import elliptec

# Settings
port = 'COM3'
address = '0'
allowed_error = 0.02
debug = False # set to True if you want print communication messages

def connect(port, address, debug = False):
    # Create objects
    controller = elliptec.Controller(port, debug=debug)
    ro = elliptec.Rotator(controller, address=address, debug=debug)
    return controller, ro

def homing(ro):
    '''Homes the rotator to the home offset'''
    # Set home offset to zero
    ret = ro.set_home_offset(0)
    home_offset = ro.get_home_offset()
    print('Home offset angle:', home_offset)
    # Homing
    ro.home()
    time.sleep(0.1)
    # See if homing moved to home offset set
    reached_angle = ro.get_angle()
    # Check if homing was achieved
    if abs(reached_angle - home_offset) >= allowed_error:
        print('Reached angle:', reached_angle)
        print("ERROR: Reached home location should equal home offset.")
    return

def movement(ro):
    '''Moves the rotator to the desired positions.'''
    # Loop over a list of angles and acquire for each
    for angle in [0, 45, 90, 135, 359, 45]:
        ro.set_angle(angle)
        reached_angle = ro.get_angle()
        if abs(reached_angle - angle) >= allowed_error:
            print('Target angle:', angle)
            print('Reached angle:', reached_angle)
            print("ERROR: Reached angle should equal target.")
    return

def alternate(ro, pos_a=0, pos_b=359, N=1):
    '''Moves the rotator between positions a and b, N times.'''
    # Alternate N times
    for i in range(N):
        print('Round', i)
        ro.set_angle(pos_a)
        reached_angle = ro.get_angle()
        if abs(reached_angle - pos_a) >= allowed_error:
            print('Target angle:', pos_a)
            print('Reached angle:', reached_angle)
            print("ERROR: Reached angle should equal target.")
        # time.sleep(1)
        ro.set_angle(pos_b)
        reached_angle = ro.get_angle()
        if abs(reached_angle - pos_b) >= allowed_error:
            print('Target angle:', pos_b)
            print('Reached angle:', reached_angle)
            print("ERROR: Reached angle should equal target.")
        # time.sleep(1)
    return

def main():
    print('\n--- Main program starts ---\n')
    controller, ro = connect(port, address, debug)
    homing(ro)
    # movement(ro)
    print('=== Alternating!!!')
    alternate(ro, 0, 359, 3)
    # Close the connection
    controller.close_connection()    
    print('\n--- Main program ends ---\n')
    return

################################################################
################################################################
################################################################

if __name__ == '__main__':
    main()