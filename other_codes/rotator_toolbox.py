# -*- coding: utf-8 -*-
"""
Created on Tue February 17, 2026

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland

This code uses Elliptec library developed by David Roesel (david@roesel.cz) for basic movements
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./elliptec-main/")))
import time
from src import elliptec

# Settings
port = 'COM7'
debug = False # set to True if you want print communication messages

class Rotation_mount(object):
    
    def __init__(self, port, address = '0', debug = False):
        """
        Method creating a controller and the rotator object
        This method also sets up the connection to the
        rotator at port:address
        """
        self.debug = debug
        self.controller = elliptec.Controller(port, debug=debug)
        self.ro = elliptec.Rotator(self.controller, address=address, debug=debug)
        self.allowed_error = 0.05 # in deg
        return 

    def homing(self):
        '''Homes the rotator to the home offset'''
        # Set home offset to zero
        ret = self.ro.set_home_offset(0)
        # Read offset
        self.home_offset = self.ro.get_home_offset()
        print('Home offset angle:', self.home_offset)
        # Homing
        self.ro.home()
        # See if homing moved to home offset set
        reached_angle = self.ro.get_angle()
        # Check if homing was achieved
        if abs(reached_angle - self.home_offset) >= self.allowed_error:
            print('Reached angle:', reached_angle)
            print("ERROR: Reached home location should equal home offset.")
        return

    def movement(self, angle):
        '''Moves the rotator to the desired angle.'''
        self.ro.set_angle(angle)
        reached_angle = self.ro.get_angle()
        if abs(reached_angle - angle) >= self.allowed_error:
            print('Target angle:', angle)
            print('Reached angle:', reached_angle)
            print("ERROR: Reached angle should equal target.")
        time.sleep(0.01)
        return

    def alternate(self, pos_a=0, pos_b=359, N=1):
        '''Moves the rotator between positions a and b, N times.'''
        # Alternate angles N times
        for i in range(N):
            # print('Round', i)
            self.movement(pos_a)
            self.movement(pos_b)
        return

    def close(self):
        self.controller.close_connection()
        return

################################################################
################################################################
################################################################

def main():
    print('\n--- Main program starts ---\n')
    ro = Rotation_mount(port, debug=debug)
    ro.homing()
    print('=== Alternating!!!')
    ro.alternate(0, 359, 10)
    # Close the connection
    ro.close()    
    print('\n--- Main program ends ---\n')
    return

################################################################
################################################################
################################################################

if __name__ == '__main__':
    main()