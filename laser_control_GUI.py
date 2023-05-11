# -*- coding: utf-8 -*-
"""
Created on Tue March 22, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import Dock, DockArea
from qtwidgets import Toggle
import lasers_and_serial_toolbox as laserToolbox
import time as tm
import numpy as np

#=====================================

# Initialize lasers

#=====================================

print('\nLooking for serial ports...')
list_of_serial_ports = laserToolbox.serial_ports()
print('Ports available:', list_of_serial_ports)   
# build laser objects 
laser532 = laserToolbox.oxxius_laser(debug_mode = False)
laser488 = laserToolbox.toptica_laser(debug_mode = False)
laserTisa = laserToolbox.M2_laser(debug_mode = False)
shutterTisa = laserToolbox.Thorlabs_shutter(debug_mode = False)
# build flippers objects
COM_port_flipper_cam_Thorlabs = 'COM5' # Serial number: 37004922
COM_port_flipper_apd_Thorlabs = 'COM8' # Serial number: 37005240
COM_port_flipper_tisa_Thorlabs = 'COM9' # Serial number: 37005241
flipperMirror = laserToolbox.motorized_flipper(debug_mode = False, \
                                               serial_port = COM_port_flipper_cam_Thorlabs)
flipperAPDFilter = laserToolbox.motorized_flipper(debug_mode = False, \
                                                  serial_port = COM_port_flipper_apd_Thorlabs)
flipperTisaFilter = laserToolbox.motorized_flipper(debug_mode = False, \
                                                  serial_port = COM_port_flipper_tisa_Thorlabs)
# set initial paramters
# updateParams_period = 2000 # in ms
initial_blue_power = 1.4 # in mW
initial_wavelength = 780.00 # in nm
starting_wavelength = 700.00 # in nm
ending_wavelength = 800.00 # in nm
step_wavelength = 10.00 # in nm
initial_integration_time = 1.00 # in s

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):
    
    shutterTisa_signal = pyqtSignal(bool) 
    shutter488_signal = pyqtSignal(bool)
    shutter532_signal = pyqtSignal(bool)
    emission532_signal = pyqtSignal(bool)
    flipper_cam_signal = pyqtSignal(bool)
    flipper_apd_signal = pyqtSignal(bool)
    flipper_tisa_signal = pyqtSignal(bool)
    powerChangedSignal = pyqtSignal(float)
    wavelengthChangedSignal = pyqtSignal(float)
    read_wavelength_signal =  pyqtSignal()
    scanRangeChangedSignal = pyqtSignal(list)
    intTimeChangedSignal = pyqtSignal(bool, float)
    scan_signal = pyqtSignal(bool)
    closeSignal = pyqtSignal()
    updateParams_signal = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Lasers control module"
        self.setWindowTitle(title)
        self.setGeometry(5, 30, 600, 300)
        self.scan_params = [0,0,0]
        self.scan_params_previous = [self.starting_wavelength_edit_previous, \
                                     self.ending_wavelength_edit_previous, \
                                     self.step_wavelength_edit_previous   
                                     ]
        return
    
    def setUpGUI(self):       
 
        # Shutters
        self.shutterTisaButton = QtGui.QCheckBox('Ti:Sa shutter')
        self.shutterTisaButton.clicked.connect(self.control_tisa_button_check)
        self.shutterTisaButton.setStyleSheet("color: darkMagenta; ")
        
        self.shutter488button = QtGui.QCheckBox('488 nm shutter')
        self.shutter488button.clicked.connect(self.control_488_button_check)
        self.shutter488button.setStyleSheet("color: blue; ")

        self.shutter532button = QtGui.QCheckBox('532 nm shutter')
        self.shutter532button.clicked.connect(self.control_532_button_check)
        self.shutter532button.setStyleSheet("color: green; ")

        self.emission532button = QtGui.QCheckBox('532 emission ON/OFF')
        self.emission532button.setStyleSheet("color: black; ")
        self.emission532button.setChecked(True)
        self.emission532button.clicked.connect(self.control_emission_532_toggle_check)

        self.updateParamsButton = QtGui.QPushButton('Update lasers\' parameters')
        self.updateParamsButton.setCheckable(False)
        self.updateParamsButton.clicked.connect(self.update_params_button)
        self.updateParamsButton.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::pressed { background-color: lightcyan; }")
        
        self.shutter488button.setToolTip('Open/close 488 shutter')
        self.shutter532button.setToolTip('Open/close 532 shutter')
        
        # Flippers
        # camera selector
        self.flipper_cam_label = QtGui.QLabel('Camera selector  | ')
        self.flipperCamButton_label = QtGui.QLabel('INSPECTION cam')
        self.flipperCamButton = Toggle(bar_color=QtGui.QColor(42,81,156), 
                                        handle_color=QtGui.QColor(14,73,140), 
                                        checked_color="#bd1e1e")
        self.flipperCamButton.clicked.connect(self.flipperCamButton_check)
        self.flipperCamButton.setToolTip('Up/Down flipper mirror')              
        # apd attenuation
        self.flipper_apd_label = QtGui.QLabel('APD attenuation selector  | ')
        self.flipperAPDButton_label = QtGui.QLabel('Filter IN')
        self.flipperAPDButton = Toggle(bar_color=QtGui.QColor(186,186,186), 
                                        handle_color=QtGui.QColor(150,150,150), 
                                        checked_color=QtGui.QColor(50,50,50))
        self.flipperAPDButton.clicked.connect(self.flipperAPDButton_check)
        self.flipperAPDButton.setToolTip('Up/Down flipper APD')
        # tisa attenuation
        self.flipper_tisa_label = QtGui.QLabel('Ti:Sa attenuation selector  | ')
        self.flipperTisaButton_label = QtGui.QLabel('Filter IN')
        self.flipperTisaButton = Toggle(bar_color=QtGui.QColor(220,15,250), 
                                        handle_color=QtGui.QColor(200,20,210), 
                                        checked_color=QtGui.QColor(80,18,100))
        self.flipperTisaButton.clicked.connect(self.flipperTisaButton_check)
        self.flipperTisaButton.setToolTip('Up/Down flipper APD')     
        
        # Ti:Sa wavelength management
        target_wavelength_label = QtGui.QLabel('Target wavelength (nm):')
        self.target_wavelength_edit = QtGui.QLineEdit(str(initial_wavelength))
        self.target_wavelength_edit_previous = float(self.target_wavelength_edit.text())
        self.target_wavelength_edit.editingFinished.connect(self.wavelength_changed_check)
        self.target_wavelength_edit.setValidator(QtGui.QDoubleValidator(698.00, 1002.00, 2))
        current_wavelength_label = QtGui.QLabel('Current wavelength (nm):')
        self.current_wavelength_display = QtGui.QLabel(str(initial_wavelength))
        
        # read wavelength
        self.readWavelengthButton = QtGui.QPushButton('Read wavelength')
        self.readWavelengthButton.setCheckable(False)
        self.readWavelengthButton.clicked.connect(self.read_wavelength_button)
        self.readWavelengthButton.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::pressed { background-color: lightgreen; }")
        
        # wavelength scan
        starting_wavelength_label = QtGui.QLabel('Starting wavelength (nm):')
        self.starting_wavelength_edit = QtGui.QLineEdit(str(starting_wavelength))
        self.starting_wavelength_edit_previous = float(self.starting_wavelength_edit.text())
        self.starting_wavelength_edit.editingFinished.connect(self.wavelength_range_changed_check)
        self.starting_wavelength_edit.setValidator(QtGui.QDoubleValidator(698.00, 1002.00, 2))
        ending_wavelength_label = QtGui.QLabel('Ending wavelength (nm):')
        self.ending_wavelength_edit = QtGui.QLineEdit(str(ending_wavelength))
        self.ending_wavelength_edit_previous = float(self.ending_wavelength_edit.text())
        self.ending_wavelength_edit.editingFinished.connect(self.wavelength_range_changed_check)
        self.ending_wavelength_edit.setValidator(QtGui.QDoubleValidator(698.00, 1002.00, 2))
        step_wavelength_label = QtGui.QLabel('Step (nm):')
        self.step_wavelength_edit = QtGui.QLineEdit(str(step_wavelength))
        self.step_wavelength_edit_previous = float(self.step_wavelength_edit.text())
        self.step_wavelength_edit.editingFinished.connect(self.wavelength_range_changed_check)
        self.step_wavelength_edit.setValidator(QtGui.QDoubleValidator(0.00, 100.00, 2))
        integration_time_label = QtGui.QLabel('Integration time (s):')
        self.integration_time_edit = QtGui.QLineEdit(str(initial_integration_time))
        self.integration_time_edit_previous = float(self.integration_time_edit.text())
        self.integration_time_edit.editingFinished.connect(self.integration_time_changed_check)
        self.integration_time_edit.setValidator(QtGui.QDoubleValidator(0.00, 3600.00, 2))
        # start scan
        self.scanButton = QtGui.QPushButton('Run wavelength scan')
        self.scanButton.setCheckable(True)
        self.scanButton.clicked.connect(self.scan_button_check)
        self.scanButton.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::checked { background-color: lightcoral; }")
        
        # 488 power
        power488_label = QtGui.QLabel('Power 488 (mW):')
        self.power488_edit = QtGui.QLineEdit(str(initial_blue_power))
        self.power488_edit_previous = float(self.power488_edit.text())
        self.power488_edit.editingFinished.connect(self.power488_changed_check)
        self.power488_edit.setValidator(QtGui.QDoubleValidator(0.00, 200.00, 2))
        
        # LAYOUT
        # Status text list
        param_list488 = ['488 laser', '-', '-', '-', '-']
        param_list532 = ['532 laser', '-', '-', '-', '-']
        param_listTisa = ['Ti:Sa laser', '-', '-', '-', '-']
        param_list = ['', 'Status', 'Temperature', 'On time', 'Alarms']
        self.no_text488 = '\n'.join(param_list488)
        self.no_text532 = '\n'.join(param_list532)
        self.no_textTisa = '\n'.join(param_listTisa)
        self.tab_text = '\n'.join(param_list)
        self.statusBlock488 = QtGui.QLabel(self.no_text488)
        self.statusBlock532 = QtGui.QLabel(self.no_text532)
        self.statusBlockTisa = QtGui.QLabel(self.no_textTisa)
        self.statusBlockDefinitions = QtGui.QLabel(self.tab_text)
        
        
        # Ti:Sa box
        self.tisa_box = QtGui.QWidget()
        tisa_box_layout = QtGui.QGridLayout()
        self.tisa_box.setLayout(tisa_box_layout)
        tisa_box_layout.addWidget(self.shutterTisaButton, 0, 0)
        tisa_box_layout.addWidget(target_wavelength_label, 1, 0)
        tisa_box_layout.addWidget(self.target_wavelength_edit, 1, 1)
        tisa_box_layout.addWidget(current_wavelength_label, 1, 2)
        tisa_box_layout.addWidget(self.current_wavelength_display, 1, 3)
        tisa_box_layout.addWidget(self.readWavelengthButton, 1, 4)
        tisa_box_layout.addWidget(starting_wavelength_label, 2, 0)
        tisa_box_layout.addWidget(self.starting_wavelength_edit, 2, 1)
        tisa_box_layout.addWidget(ending_wavelength_label, 2, 2)
        tisa_box_layout.addWidget(self.ending_wavelength_edit, 2, 3)
        tisa_box_layout.addWidget(step_wavelength_label, 2, 4)
        tisa_box_layout.addWidget(self.step_wavelength_edit, 2, 5)
        tisa_box_layout.addWidget(integration_time_label, 3, 0)
        tisa_box_layout.addWidget(self.integration_time_edit, 3, 1)
        tisa_box_layout.addWidget(self.scanButton, 4, 0, 1, 6)
        
        # 488 box
        self.blue_laser_box = QtGui.QWidget()
        blue_laser_box_layout = QtGui.QGridLayout()
        self.blue_laser_box.setLayout(blue_laser_box_layout)
        blue_laser_box_layout.addWidget(self.shutter488button, 0, 0)
        blue_laser_box_layout.addWidget(power488_label, 0, 1)
        blue_laser_box_layout.addWidget(self.power488_edit, 0, 2)
        
        # 532 box
        self.green_laser_box = QtGui.QWidget()
        green_laser_box_layout = QtGui.QGridLayout()
        self.green_laser_box.setLayout(green_laser_box_layout)
        green_laser_box_layout.addWidget(self.shutter532button, 0, 0)
        green_laser_box_layout.addWidget(self.emission532button, 0, 1)
        
        # flippers box
        self.flippers_box = QtGui.QWidget()
        flippers_box_layout = QtGui.QGridLayout()
        self.flippers_box.setLayout(flippers_box_layout)
        flippers_box_layout.addWidget(self.flipper_cam_label, 0, 0)
        flippers_box_layout.addWidget(self.flipperCamButton_label, 0, 1)
        flippers_box_layout.addWidget(self.flipperCamButton, 0, 2)
        flippers_box_layout.addWidget(self.flipper_apd_label, 1, 0)
        flippers_box_layout.addWidget(self.flipperAPDButton_label, 1, 1)
        flippers_box_layout.addWidget(self.flipperAPDButton, 1, 2)
        flippers_box_layout.addWidget(self.flipper_tisa_label, 2, 0)
        flippers_box_layout.addWidget(self.flipperTisaButton_label, 2, 1)
        flippers_box_layout.addWidget(self.flipperTisaButton, 2, 2)
        
        # Status box
        self.status_box = QtGui.QWidget()
        status_box_layout = QtGui.QGridLayout()
        self.status_box.setLayout(status_box_layout)
        status_box_layout.addWidget(self.updateParamsButton, 0, 0, 1, 4)
        status_box_layout.addWidget(self.statusBlockDefinitions, 1, 0)
        status_box_layout.addWidget(self.statusBlock488, 1, 1)
        status_box_layout.addWidget(self.statusBlock532, 1, 2)
        status_box_layout.addWidget(self.statusBlockTisa, 1, 3)

        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        tisa_Dock = Dock('Ti:Sa control', size = (20, 200))
        tisa_Dock.addWidget(self.tisa_box)
        dockArea.addDock(tisa_Dock)
        
        blue_laser_Dock = Dock('488 laser', size = (20, 20))
        blue_laser_Dock.addWidget(self.blue_laser_box)
        dockArea.addDock(blue_laser_Dock, 'bottom', tisa_Dock)
        
        green_laser_Dock = Dock('532 laser', size = (20, 20))
        green_laser_Dock.addWidget(self.green_laser_box)
        dockArea.addDock(green_laser_Dock, 'bottom', blue_laser_Dock)

        flippers_Dock = Dock('Flippers', size = (1, 20))
        flippers_Dock.addWidget(self.flippers_box)
        dockArea.addDock(flippers_Dock, 'bottom', green_laser_Dock)
        
        status_Dock = Dock('Status', size = (20, 20))
        status_Dock.addWidget(self.status_box)
        dockArea.addDock(status_Dock, 'bottom', flippers_Dock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
    
    # Functions and signals 
    def control_tisa_button_check(self):
        if self.shutterTisaButton.isChecked():
           self.shutterTisa_signal.emit(True)
        else:
           self.shutterTisa_signal.emit(False)
        return
    
    def control_488_button_check(self):
        if self.shutter488button.isChecked():
           self.shutter488_signal.emit(True)
        else:
           self.shutter488_signal.emit(False)
        return
    
    def control_532_button_check(self):
        if self.shutter532button.isChecked():
           self.shutter532_signal.emit(True)
        else:
           self.shutter532_signal.emit(False)
        return

    def control_emission_532_toggle_check(self):
        if self.emission532button.isChecked():
            self.emission532_signal.emit(True)
        else:
            self.emission532_signal.emit(False)
        return

    def flipperCamButton_check(self):
        if self.flipperCamButton.handle_position == 1:
            self.flipperCamButton_label.setText('INSPECTION cam')
            self.flipper_cam_signal.emit(True)
        else:
            self.flipperCamButton_label.setText('XY STABILIZATION cam')
            self.flipper_cam_signal.emit(False)
        return
    
    def flipperAPDButton_check(self):
        if self.flipperAPDButton.handle_position == 1:
            self.flipperAPDButton_label.setText('Filter IN')
            self.flipper_apd_signal.emit(True)
        else:
            self.flipperAPDButton_label.setText('Filter OUT')
            self.flipper_apd_signal.emit(False)
        return

    def flipperTisaButton_check(self):
        if self.flipperTisaButton.handle_position == 1:
            self.flipperTisaButton_label.setText('Filter IN')
            self.flipper_tisa_signal.emit(True)
        else:
            self.flipperTisaButton_label.setText('Filter OUT')
            self.flipper_tisa_signal.emit(False)
        return

    def power488_changed_check(self):
        power488_mW = float(self.power488_edit.text()) # in mW
        if power488_mW != self.power488_edit_previous:
            self.power488_edit_previous = power488_mW
            self.powerChangedSignal.emit(power488_mW)
        return
    
    def wavelength_changed_check(self):
        target_wavelength = float(self.target_wavelength_edit.text()) # in nm
        if target_wavelength != self.target_wavelength_edit_previous:
            self.target_wavelength_edit_previous = target_wavelength
            self.wavelengthChangedSignal.emit(target_wavelength)
        return
    
    def integration_time_changed_check(self):
        integration_time = float(self.integration_time_edit.text()) # in nm
        if integration_time != self.integration_time_edit_previous:
            self.integration_time_edit_previous = integration_time
            self.intTimeChangedSignal.emit(self.scanButton.isChecked(), integration_time)
        return
    
    def wavelength_range_changed_check(self):
        starting_wavelength = float(self.starting_wavelength_edit.text()) # in nm
        ending_wavelength = float(self.ending_wavelength_edit.text()) # in nm
        step_wavelength = float(self.step_wavelength_edit.text()) # in nm
        self.scan_params = [starting_wavelength, ending_wavelength, step_wavelength]
        if self.scan_params != self.scan_params_previous:
            self.scan_params_previous = self.scan_params
            self.scanRangeChangedSignal.emit(self.scan_params)
        return

    def scan_button_check(self):
        if self.scanButton.isChecked():
            self.scan_signal.emit(True)
        else:
            self.scan_signal.emit(False)
        return
    
    def scan_finished(self):
        self.scanButton.setChecked(False)
        self.scan_signal.emit(False)
        return
    
    def read_wavelength_button(self):
        self.read_wavelength_signal.emit()           
        return
    
    @pyqtSlot(float)
    def update_wavelength(self, wavelength):
        self.current_wavelength_display.setText(str(round(wavelength, 2)))
        return
    
    def update_params_button(self):
        self.updateParams_signal.emit()
        return
    
    @pyqtSlot(list, list, list)
    def display_params(self, list_of_params488, list_of_params532, list_of_paramsTisa):
        text_to_display488 = '\n'.join(list_of_params488)
        text_to_display532 = '\n'.join(list_of_params532)
        text_to_displayTisa = '\n'.join(list_of_paramsTisa)
        self.statusBlock488.setText(text_to_display488)
        self.statusBlock532.setText(text_to_display532)
        self.statusBlockTisa.setText(text_to_displayTisa)
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
        backend.paramSignal.connect(self.display_params)
        backend.passWavelengthSignal.connect(self.update_wavelength)
        backend.scan_finished_signal.connect(self.scan_finished)
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):
    
    paramSignal = pyqtSignal(list, list, list)
    passWavelengthSignal = pyqtSignal(float)
    scan_finished_signal = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set timer to update lasers status
        self.integration_time_ms = int(initial_integration_time*1000) # in ms
        self.scanTimer = QtCore.QTimer()
        self.scanTimer.timeout.connect(self.scan) # funciton to connect after each interval
        self.scanTimer.setInterval(self.integration_time_ms) # in ms
        self.change_power(initial_blue_power)
        self.change_wavelength(initial_wavelength)
        self.starting_wavelength = starting_wavelength
        self.ending_wavelength = ending_wavelength
        self.step_wavelength = step_wavelength
        self.wavelength_scan_array = np.arange(self.starting_wavelength, \
                                               self.ending_wavelength + self.step_wavelength, \
                                               self.step_wavelength
                                               )
        self.counter = 0
        self.scan_flag = False
        return

    @pyqtSlot(bool)
    def shutterTisa(self, shutterbool):
        if shutterbool:
            shutterTisa.shutter('open')
        else:
            shutterTisa.shutter('close')
        return
    
    @pyqtSlot(bool)
    def shutter488(self, shutterbool):
        if shutterbool:
            laser488.shutter('open')
        else:
            laser488.shutter('close')
        return
        
    @pyqtSlot(bool)
    def shutter532(self, shutterbool):
        if shutterbool:
            laser532.shutter('open')
        else:
            laser532.shutter('close')
        return
            
    @pyqtSlot(bool)
    def emission532(self, emissionbool):
        if emissionbool:
            laser532.emission('on')
        else:
            laser532.emission('off')
        return
    
    @pyqtSlot(bool)
    def flipper_inspec_cam(self, flipperbool):
        if flipperbool:
            flipperMirror.set_flipper_down() # inspection camera ON
        else:
            flipperMirror.set_flipper_up() # inspection camera OFF
        print('Flipper status:', flipperMirror.get_state())
        return
    
    @pyqtSlot(bool)
    def flipper_apd_attenuation(self, flipperbool):
        if flipperbool:
            flipperAPDFilter.set_flipper_down() # filter IN
        else:
            flipperAPDFilter.set_flipper_up() # filter OUT
        print('Flipper status:', flipperAPDFilter.get_state())
        return
    
    @pyqtSlot(bool)
    def flipper_tisa_attenuation(self, flipperbool):
        if flipperbool:
            flipperTisaFilter.set_flipper_down() # filter IN
        else:
            flipperTisaFilter.set_flipper_up() # filter OUT
        print('Flipper status:', flipperTisaFilter.get_state())
        return
    
    @pyqtSlot(float)    
    def change_power(self, power488_mW):
        self.power488_mW = power488_mW # in mW, is float
        laser488.set_power(self.power488_mW)
        return
    
    # @pyqtSlot(bool)    
    # def start_updating_params(self, updatebool):
    #     if updatebool:
    #         print('Starting updater (QtTimer)... Update period: %.1f s' % (updateParams_period/1000))
    #         self.updateTimer.start()
    #     else:
    #         print('Stopping updater (QtTimer)...')
    #         self.updateTimer.stop()
    #     return
        
    @pyqtSlot(bool, float)
    def set_integration_time(self, run_scan_instruction, integration_time):
        print('\nIntegration time set to %.2f s ...' % integration_time)
        self.integration_time_ms = int(integration_time*1000) # in ms
        if run_scan_instruction:
            print('Stopping QtTimer...')
            self.scanTimer.stop()
        print('Changing QtTimer update interval...')
        self.scanTimer.setInterval(self.integration_time_ms) # in ms
        return  
    
    def change_wavelength(self, target_wavelength):
        print('\nSetting target wavelength to %.2f nm ...' % target_wavelength)
        target_wavelength_meters = target_wavelength*1e-9 # convert to meters
        laserTisa.set_wavelength(target_wavelength_meters)
        self.read_wavelength()
        return
    
    @pyqtSlot()
    def read_wavelength(self):
        # read the current wavelength property
        laserTisa.get_wavelength()
        self.current_wavelength = float(laserTisa.current_wavelength_nm)
        self.passWavelengthSignal.emit(self.current_wavelength)
        print('Current wavelength is %.2f nm' % self.current_wavelength)
        return 
    
    @pyqtSlot(list)
    def scan_parameters_changed(self, new_params):
        self.starting_wavelength = new_params[0]
        self.ending_wavelength = new_params[1]
        self.step_wavelength = new_params[2]
        self.wavelength_scan_array = np.arange(self.starting_wavelength, \
                                               self.ending_wavelength + self.step_wavelength, \
                                               self.step_wavelength
                                               )
        print('\nScanning range is now starting at %.2f nm and ending at %.2f nm\nwith a %.2f nm step' \
              % (self.starting_wavelength, self.ending_wavelength, self.step_wavelength))
        return 
    
    @pyqtSlot(bool)
    def run_stop_scan(self, run_scan_instruction):
        if run_scan_instruction:
            print('\nStarting QtTimer...')
            print('Starting scan...')
            self.scanTimer.start()
            self.counter = 0
            self.scan_flag = True
        else:
            print('\nStopping QtTimer...')
            self.scanTimer.stop()
            print('Stop wavelength tuning. Stop scanning...')
            # laserTisa.stop_coarse_tuning()
            self.counter = 0
            self.scan_flag = False
        return 
    
    def scan(self):
        status = laserTisa.get_tuning_status()
        if self.scan_flag:
            if status == 1:
                if self.counter < len(self.wavelength_scan_array):
                    wavelength = self.wavelength_scan_array[self.counter]
                    print('\nScan: wavelength set to %.2f nm' % wavelength)
                    self.change_wavelength(wavelength)
                    self.counter += 1
                else:
                    self.scan_flag = False
                    self.scan_finished_signal.emit()
            else:
                print('Ti:Sa status: ', status)
        return
    
    @pyqtSlot()
    def update_params(self):
        # Parameters of 488 nm laser
        status488 = laser488.status()
        temp488 = laser488.base_temp()
        hours488 = laser488.hours()
        temp_alarm488 = laser488.temp_status()
        
        # Parameters of 532 nm laser
        status532 = laser532.status()
        temp532 = laser532.base_temp()
        hours532 = laser532.hours()
        alarm532 = laser532.alarm()
        
        # Parameters of Ti:Sa laser
        status_list = laserTisa.status()
        statusTisa = status_list[0]
        tempTisa = status_list[1]
        hoursTisa = '-'
        alarmTisa = '-'
        
        param_list488 = ['488 laser', status488, temp488, hours488, temp_alarm488]
        param_list532 = ['532 laser', status532, temp532, hours532, alarm532]
        param_listTisa = ['Ti:Sa laser', statusTisa, tempTisa, hoursTisa, alarmTisa]
        
        # send parameters to GUI
        self.paramSignal.emit(param_list488, param_list532, param_listTisa)
        return

    @pyqtSlot()
    def closeBackend(self):
        laser488.close()
        laser532.close()
        laserTisa.close()
        flipperMirror.close()
        flipperAPDFilter.close()
        flipperTisaFilter.close()
        print('Stopping updater (QtTimer)...')
        self.scanTimer.stop()
        # self.updateTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
       
    def make_connections(self, frontend):
        frontend.shutterTisa_signal.connect(self.shutterTisa)
        frontend.shutter488_signal.connect(self.shutter488)
        frontend.shutter532_signal.connect(self.shutter532)
        frontend.emission532_signal.connect(self.emission532)
        frontend.flipper_cam_signal.connect(self.flipper_inspec_cam)
        frontend.flipper_apd_signal.connect(self.flipper_apd_attenuation)
        frontend.flipper_tisa_signal.connect(self.flipper_tisa_attenuation)
        frontend.powerChangedSignal.connect(self.change_power)
        frontend.wavelengthChangedSignal.connect(self.change_wavelength)
        frontend.scanRangeChangedSignal.connect(self.scan_parameters_changed)
        frontend.read_wavelength_signal.connect(self.read_wavelength)
        frontend.intTimeChangedSignal.connect(self.set_integration_time)
        frontend.scan_signal.connect(self.run_stop_scan)
        frontend.closeSignal.connect(self.closeBackend)
        frontend.updateParams_signal.connect(self.update_params)
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
    worker.scanTimer.moveToThread(workerThread)
    # worker.updateTimer.moveToThread(workerThread)

    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()

    gui.show()
    app.exec()
    