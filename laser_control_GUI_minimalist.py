# -*- coding: utf-8 -*-
"""
Created on Tue March 17, 2025

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import Dock, DockArea
import lasers_and_serial_toolbox as laserToolbox
import time as tm

#=====================================

# Initialize lasers

#=====================================

print('\nLooking for serial ports...')
list_of_serial_ports = laserToolbox.serial_ports()
print('Ports available:', list_of_serial_ports)   
# build laser objects 
laser488 = laserToolbox.toptica_laser(debug_mode = False)
shutterTrappingLaserObject = laserToolbox.Thorlabs_shutter(debug_mode = False)
# build flippers objects
flipperAPDFilter = laserToolbox.motorized_flipper(debug_mode = False, \
                                                  serial_port = laserToolbox.COM_port_flipper_apd_Thorlabs)
flipperSpectrometerPath = laserToolbox.motorized_flipper(debug_mode = False, \
                                                  serial_port = laserToolbox.COM_port_flipper_spectrometer)
flipperTrappingLaserFilter = laserToolbox.motorized_flipper(debug_mode = False, \
                                                  serial_port = laserToolbox.COM_port_flipper_trapping_laser_Thorlabs)
# set initial paramters
initial_blue_power = 15 # in mW

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):
    
    shutterTrappingSignal = pyqtSignal(bool) 
    shutter488_signal = pyqtSignal(bool)
    flipper_apd_signal = pyqtSignal(bool)
    flipper_spectrometer_path_signal = pyqtSignal(bool)
    flipper_trapping_laser_signal = pyqtSignal(bool)
    powerChangedSignal = pyqtSignal(float)
    closeSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Lasers control module"
        self.setWindowTitle(title)
        self.setGeometry(5, 30, 250, 100) # x pos, y pos, width, height
        return
    
    def setUpGUI(self):       
 
        # Shutters
        self.shutterTrappingLaserButton = QtGui.QCheckBox('Trapping laser')
        self.shutterTrappingLaserButton.clicked.connect(self.control_trapping_laser_button_check)
        self.shutterTrappingLaserButton.setStyleSheet("color: darkMagenta; ")
        self.shutterTrappingLaserButton.setToolTip('Open/close NIR laser shutter')

        self.shutter488button = QtGui.QCheckBox('488 nm')
        self.shutter488button.clicked.connect(self.control_488_button_check)
        self.shutter488button.setStyleSheet("color: blue; ")
        self.shutter488button.setToolTip('Open/close 488 laser shutter')
        
        # Flippers      
        # apd attenuation
        self.flipperAPDButton = QtGui.QCheckBox('APD attenuation')
        self.flipperAPDButton.setChecked(True)
        self.flipperAPDButton.clicked.connect(self.flipperAPDButton_check)
        self.flipperAPDButton.setToolTip('Up/Down flipper APD')

        # Trapping laser attenuation
        self.flipperTrappingLaserButton = QtGui.QCheckBox('Trapping laser attenuation (10x)')
        self.flipperTrappingLaserButton.setChecked(True)
        self.flipperTrappingLaserButton.clicked.connect(self.flipperTrappingLaserButton_check)
        self.flipperTrappingLaserButton.setToolTip('Up/Down flipper trapping laser')     
        
        # Spectrometer/APD path selector
        self.flipperSpectrometerButton = QtGui.QCheckBox('Spectrometer path')
        self.flipperSpectrometerButton.setChecked(False)
        self.flipperSpectrometerButton.clicked.connect(self.flipperSpectrometerButton_check)
        self.flipperSpectrometerButton.setToolTip('Up/Down flipper to select the spectromter collection path')

        # 488 power
        power488_label = QtGui.QLabel('Power 488 (mW):')
        self.power488_edit = QtGui.QLineEdit(str(initial_blue_power))
        self.power488_edit.setFixedWidth(50)
        self.power488_edit_previous = float(self.power488_edit.text())
        self.power488_edit.editingFinished.connect(self.power488_changed_check)
        self.power488_edit.setValidator(QtGui.QDoubleValidator(0.00, 200.00, 2))
        
        # LAYOUT
        # Minimalist
        self.minimalist_box = QtGui.QWidget()
        minimalist_box_layout = QtGui.QGridLayout()
        minimalist_box_layout.setSpacing(0)
        self.minimalist_box.setLayout(minimalist_box_layout)
        minimalist_box_layout.addWidget(self.shutterTrappingLaserButton, 0, 0)
        minimalist_box_layout.addWidget(self.flipperTrappingLaserButton, 0, 1)
        minimalist_box_layout.addWidget(self.shutter488button, 1, 0)
        minimalist_box_layout.addWidget(power488_label, 1, 1)
        minimalist_box_layout.addWidget(self.power488_edit, 1, 2)
        minimalist_box_layout.addWidget(self.flipperAPDButton, 2, 0)
        minimalist_box_layout.addWidget(self.flipperSpectrometerButton, 2, 1)

        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        control_Dock = Dock('Lasers and shutters control', size = (20, 2000))
        control_Dock.addWidget(self.minimalist_box)
        dockArea.addDock(control_Dock)
        control_Dock.hideTitleBar()

        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
    
    def control_trapping_laser_button_check(self):
        if self.shutterTrappingLaserButton.isChecked():
           self.shutterTrappingSignal.emit(True)
        else:
           self.shutterTrappingSignal.emit(False)
        return
    
    def control_488_button_check(self):
        if self.shutter488button.isChecked():
           self.shutter488_signal.emit(True)
        else:
           self.shutter488_signal.emit(False)
        return
    
    def flipperAPDButton_check(self):
        if self.flipperAPDButton.isChecked():
            self.flipper_apd_signal.emit(True)
        else:
            self.flipper_apd_signal.emit(False)
        return

    def flipperSpectrometerButton_check(self):
        if self.flipperSpectrometerButton.isChecked():
            self.flipper_spectrometer_path_signal.emit(True)
        else:
            self.flipper_spectrometer_path_signal.emit(False)
        return

    def flipperTrappingLaserButton_check(self):
        if self.flipperTrappingLaserButton.isChecked():
            self.flipper_trapping_laser_signal.emit(True)
        else:
            self.flipper_trapping_laser_signal.emit(False)
        return

    def power488_changed_check(self):
        power488_mW = float(self.power488_edit.text()) # in mW
        if power488_mW != self.power488_edit_previous:
            self.power488_edit_previous = power488_mW
            self.powerChangedSignal.emit(power488_mW)
        return
    
    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super(QtGui.QFrame, self).closeEvent(event, *args, **kwargs)
        # dialog box
        reply = QtGui.QMessageBox.question(self, 'Exit', 'Are you sure you want to exit the program?',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
        if reply == QtGui.QMessageBox.Yes:
            event.accept()
            print('Closing GUI...')
            self.close()
            self.closeSignal.emit()
            tm.sleep(3) # needed to close all flippers
            app.quit()
        else:
            event.ignore()
            print('Back in business...')
        return
    
    def make_connections(self, backend):
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.change_power(initial_blue_power)
        self.shutter488(False) # close shutter
        self.flipper_trapping_laser_attenuation(True) # set filters IN
        self.flipper_apd_attenuation(True) # set filters IN
        self.flipper_select_spectrometer(False) # set filters OUT
        return

    @pyqtSlot(bool)
    def shutterTrappingLaser(self, shutterbool):
        if shutterbool:
            shutterTrappingLaserObject.shutter('open')
        else:
            shutterTrappingLaserObject.shutter('close')
        return
    
    @pyqtSlot(bool)
    def shutter488(self, shutterbool):
        if shutterbool:
            laser488.shutter('open')
        else:
            laser488.shutter('close')
        return
    
    @pyqtSlot(bool)
    def flipper_apd_attenuation(self, flipperbool):
        if flipperbool:
            flipperAPDFilter.set_flipper_down() # filter IN
        else:
            flipperAPDFilter.set_flipper_up() # filter OUT
        print('Flipper APD attenuation status:', flipperAPDFilter.get_state())
        return
    
    @pyqtSlot(bool)
    def flipper_select_spectrometer(self, flipperbool):
        if flipperbool:
            flipperSpectrometerPath.set_flipper_down() # filter IN
        else:
            flipperSpectrometerPath.set_flipper_up() # filter OUT
        print('Flipper Spectrometer path status:', flipperSpectrometerPath.get_state())
        return

    @pyqtSlot(bool)
    def flipper_trapping_laser_attenuation(self, flipperbool):
        if flipperbool:
            flipperTrappingLaserFilter.set_flipper_down() # filter IN
        else:
            flipperTrappingLaserFilter.set_flipper_up() # filter OUT
        print('Flipper Trapping laser attenuation status:', flipperTrappingLaserFilter.get_state())
        return
    
    @pyqtSlot(float)    
    def change_power(self, power488_mW):
        self.power488_mW = power488_mW # in mW, is float
        laser488.set_power(self.power488_mW)
        return

    @pyqtSlot()
    def close_backend(self):
        print('Disconnecting lasers...')
        laser488.close()
        print('\nClosing Trapping laser shutter...')
        self.shutterTrappingLaser(False)
        print('Closing flippers...')
        flipperAPDFilter.close()
        flipperSpectrometerPath.close()
        flipperTrappingLaserFilter.close() # TODO check if it is working
        print('Exiting thread...')
        workerThread.exit()
        return
       
    def make_connections(self, frontend):
        frontend.shutterTrappingSignal.connect(self.shutterTrappingLaser)
        frontend.shutter488_signal.connect(self.shutter488)
        frontend.flipper_apd_signal.connect(self.flipper_apd_attenuation)
        frontend.flipper_spectrometer_path_signal.connect(self.flipper_select_spectrometer)
        frontend.flipper_trapping_laser_signal.connect(self.flipper_trapping_laser_attenuation)
        frontend.powerChangedSignal.connect(self.change_power)
        frontend.closeSignal.connect(self.close_backend)
        return
    
#=====================================

#  Main program

#=====================================

if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])

    # create both classes
    gui = Frontend()
    worker = Backend()
    
    # thread that run in background
    workerThread = QtCore.QThread()
    worker.moveToThread(workerThread)

    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()

    gui.show()
    app.exec()
    