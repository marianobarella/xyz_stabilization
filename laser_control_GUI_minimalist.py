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
import daq_board_toolbox as daq_toolbox # for shutters control

# set initial paramters
initial_blue_power = 30 # in mW

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):
    
    shutterTrappingSignal = pyqtSignal(bool) 
    shutterSafetySignal = pyqtSignal(bool) 
    shutterWhiteSignal = pyqtSignal(bool) 
    shutter488_signal = pyqtSignal(bool)
    shutter532_signal = pyqtSignal(bool)
    emission532_signal = pyqtSignal(bool)
    LED_signal = pyqtSignal(bool)
    flipper_apd_signal = pyqtSignal(bool)
    flipper_spectrometer_path_signal = pyqtSignal(bool)
    flipper_trapping_laser_signal = pyqtSignal(bool)
    powerChangedSignal = pyqtSignal(float)
    updateParams_signal = pyqtSignal()
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

        self.shutterWhiteLaserButton = QtGui.QCheckBox('White laser')
        self.shutterWhiteLaserButton.clicked.connect(self.control_white_laser_button_check)
        self.shutterWhiteLaserButton.setStyleSheet("color: black; ")
        self.shutterWhiteLaserButton.setToolTip('Open/close white laser shutter')

        self.shutterSafetyLaserButton = QtGui.QCheckBox('Safety shutter')
        self.shutterSafetyLaserButton.clicked.connect(self.control_safety_shutter_button_check)
        self.shutterSafetyLaserButton.setChecked(False)
        self.shutterSafetyLaserButton.setStyleSheet("color: darkred; ")
        self.shutterSafetyLaserButton.setToolTip('Open/close NIR laser second shutter')

        self.shutter488button = QtGui.QCheckBox('488 nm')
        self.shutter488button.clicked.connect(self.control_488_button_check)
        self.shutter488button.setStyleSheet("color: blue; ")
        self.shutter488button.setToolTip('Open/close 488 laser shutter')

        self.shutter532button = QtGui.QCheckBox('532 nm')
        self.shutter532button.clicked.connect(self.control_532_button_check)
        self.shutter532button.setStyleSheet("color: green; ")
        self.shutter532button.setToolTip('Open/close 532 laser shutter')

        self.emission532button = QtGui.QCheckBox('532 emission ON/OFF')
        self.emission532button.setStyleSheet("color: black; ")
        self.emission532button.setChecked(True)
        self.emission532button.clicked.connect(self.control_emission_532_toggle_check)   
        self.emission532button.setToolTip('Turns ON/OFF 532 laser emission')     

        self.updateParamsButton = QtGui.QPushButton('Update lasers\' parameters')
        self.updateParamsButton.setCheckable(False)
        self.updateParamsButton.clicked.connect(self.update_params_button)
        self.updateParamsButton.setStyleSheet(
                "QPushButton::pressed { background-color: lightcyan; }")
        
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
        self.flipperSpectrometerButton.setChecked(True)
        self.flipperSpectrometerButton.clicked.connect(self.flipperSpectrometerButton_check)
        self.flipperSpectrometerButton.setToolTip('Up/Down flipper to select the spectromter collection path')

        # 488 power
        power488_label = QtGui.QLabel('Power 488 (mW):')
        self.power488_edit = QtGui.QLineEdit(str(initial_blue_power))
        self.power488_edit.setFixedWidth(50)
        self.power488_edit_previous = float(self.power488_edit.text())
        self.power488_edit.editingFinished.connect(self.power488_changed_check)
        self.power488_edit.setValidator(QtGui.QDoubleValidator(0.00, 200.00, 2))
        
        # LED
        self.LEDbutton = QtGui.QCheckBox('LED')
        self.LEDbutton.setStyleSheet("color: black; ")
        self.LEDbutton.setChecked(True)
        self.LEDbutton.clicked.connect(self.control_LED_check)   
        self.LEDbutton.setToolTip('Turns ON/OFF LED illumination')     

        # LAYOUT
        # Minimalist
        self.minimalist_box = QtGui.QWidget()
        minimalist_box_layout = QtGui.QGridLayout()
        minimalist_box_layout.setSpacing(0)
        self.minimalist_box.setLayout(minimalist_box_layout)
        minimalist_box_layout.addWidget(self.shutterTrappingLaserButton, 0, 0)
        minimalist_box_layout.addWidget(self.flipperTrappingLaserButton, 0, 1, 1, 21)
        minimalist_box_layout.addWidget(self.shutterSafetyLaserButton, 1, 0)
        minimalist_box_layout.addWidget(self.LEDbutton, 1, 1)
        minimalist_box_layout.addWidget(self.shutter488button, 2, 0)
        minimalist_box_layout.addWidget(power488_label, 2, 1)
        minimalist_box_layout.addWidget(self.power488_edit, 2, 2)
        minimalist_box_layout.addWidget(self.shutter532button, 3, 0)
        minimalist_box_layout.addWidget(self.emission532button, 3, 1)
        minimalist_box_layout.addWidget(self.flipperAPDButton, 4, 0)
        minimalist_box_layout.addWidget(self.flipperSpectrometerButton, 4, 1)
        minimalist_box_layout.addWidget(self.shutterWhiteLaserButton, 5, 1)
        minimalist_box_layout.addWidget(self.updateParamsButton, 6, 0, 1, 2)

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
    
    def control_safety_shutter_button_check(self):
        if self.shutterSafetyLaserButton.isChecked():
            self.shutterSafetySignal.emit(True)
        else:
            self.shutterSafetySignal.emit(False)
        return

    def control_white_laser_button_check(self):
        if self.shutterWhiteLaserButton.isChecked():
            if not self.flipperSpectrometerButton.isChecked():
                # dialog box
                reply = QtGui.QMessageBox.question(self, 'Warning!', 'APD path is selected! \nAre you sure you want to open the white laser shutter?',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
                if reply == QtGui.QMessageBox.Yes:
                    self.shutterWhiteSignal.emit(True)
                    return
                else:
                    self.shutterWhiteSignal.emit(False)
                    self.shutterWhiteLaserButton.setChecked(False)
                    return
            else:
                self.shutterWhiteSignal.emit(True)
                return
        else:
            self.shutterWhiteSignal.emit(False)
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
    
    def flipperAPDButton_check(self):
        if self.flipperAPDButton.isChecked():
            self.flipper_apd_signal.emit(True)
        else:
            self.flipper_apd_signal.emit(False)
        return

    def flipperSpectrometerButton_check(self):
        if self.flipperSpectrometerButton.isChecked():
            # check if trapping laser is ON and close the shutter to protect the spectrometer
            if self.shutterTrappingLaserButton.isChecked():
                self.shutterTrappingSignal.emit(False)
                # change the button state
                self.shutterTrappingLaserButton.setChecked(False)
            # close safety shutter
            self.shutterSafetySignal.emit(False)
            self.shutterSafetyLaserButton.setChecked(False)
            # send flipper signal
            self.flipper_spectrometer_path_signal.emit(True)
            # disable trapping laser while the spectrometer path is selected
            self.shutterTrappingLaserButton.setEnabled(False)
        else:
            self.flipper_spectrometer_path_signal.emit(False)
            # restore the trapping laser checkbox
            self.shutterTrappingLaserButton.setEnabled(True)
            # open safety shutter
            self.shutterSafetySignal.emit(True)
            self.shutterSafetyLaserButton.setChecked(True)
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

    def control_emission_532_toggle_check(self):
        if self.emission532button.isChecked():
            self.emission532_signal.emit(True)
        else:
            self.emission532_signal.emit(False)
        return

    def control_LED_check(self):
        if self.LEDbutton.isChecked():
            self.LED_signal.emit(True)
        else:
            self.LED_signal.emit(False)
        return

    def update_params_button(self):
        self.updateParams_signal.emit()
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
        
    def __init__(self, daq_board, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print('\nLooking for serial ports...')
        list_of_serial_ports = laserToolbox.serial_ports()
        print('Ports available:', list_of_serial_ports)   
        # build laser objects 
        self.laser488 = laserToolbox.toptica_laser(debug_mode = False)
        self.laser532 = laserToolbox.oxxius_laser(debug_mode = False)
        self.shuttersObject = laserToolbox.shutters(daq_board) # initialize shutter and closes them all
        self.flippersObject = laserToolbox.flippers(daq_board) # initialize flippers and closes them all
        # build flippers objects
        # self.flipperAPDFilter = laserToolbox.motorized_flipper(debug_mode = False, \
        #                                                   serial_port = laserToolbox.COM_port_flipper_apd_Thorlabs)
        # self.flipperSpectrometerPath = laserToolbox.motorized_flipper(debug_mode = False, \
        #                                                   serial_port = laserToolbox.COM_port_flipper_spectrometer)
        # self.flipperTrappingLaserFilter = laserToolbox.motorized_flipper(debug_mode = False, \
                                                          # serial_port = laserToolbox.COM_port_flipper_trapping_laser_Thorlabs)
        tm.sleep(0.5)
        # set blue laser power
        self.change_power(initial_blue_power)
        # close shutters at the beggining
        self.shutter488(False) # close shutter
        self.shutter532(False) # close shutter
        self.flipper_trapping_laser_attenuation(True) # set filters IN
        # self.flipper_apd_attenuation(True) # set filters IN
        # self.flipper_select_spectrometer(False) # set filters OUT
        return

    @pyqtSlot(bool)
    def shutterTrappingLaser(self, shutterbool):
        if shutterbool:
            self.shuttersObject.open_shutter('NIR')
        else:
            self.shuttersObject.close_shutter('NIR')
        return
    
    @pyqtSlot(bool)
    def shutterWhiteLaser(self, shutterbool):
        if shutterbool:
            self.shuttersObject.open_shutter('white')
        else:
            self.shuttersObject.close_shutter('white')
        return

    @pyqtSlot(bool)
    def shutterSafetyLaser(self, shutterbool):
        if shutterbool:
            self.shuttersObject.open_shutter('safety')
        else:
            self.shuttersObject.close_shutter('safety')
        return 

    @pyqtSlot(bool)
    def shutter488(self, shutterbool):
        if shutterbool:
            self.laser488.shutter('open')
        else:
            self.laser488.shutter('close')
        return
    
    @pyqtSlot(bool)
    def shutter532(self, shutterbool):
        if shutterbool:
            self.laser532.shutter('open')
        else:
            self.laser532.shutter('close')
        return
            
    @pyqtSlot(bool)
    def emission532(self, emissionbool):
        if emissionbool:
            self.laser532.emission('on')
        else:
            self.laser532.emission('off')
        return

    @pyqtSlot(bool)
    def LEDlight(self, lightbool):
        if lightbool:
            print('LED switched ON')
            # self.LED.switch('on')
        else:
            print('LED switched OFF')
            # self.LED.switch('off')
        return

    @pyqtSlot(bool)
    def flipper_apd_attenuation(self, flipperbool):
        if flipperbool:
            self.flippersObject.close_flipper('apd_attenuation') # filter IN
        else:
            self.flippersObject.open_flipper('apd_attenuation') # filter OUT
        return
    
    @pyqtSlot(bool)
    def flipper_select_spectrometer(self, flipperbool):
        if flipperbool:
            self.flippersObject.close_flipper('spectrometer_selector') # filter IN
        else:
            self.flippersObject.open_flipper('spectrometer_selector') # filter OUT
        return

    @pyqtSlot(bool)
    def flipper_trapping_laser_attenuation(self, flipperbool):
        if flipperbool:
            self.flippersObject.close_flipper('laser_attenuation') # filter IN
        else:
            self.flippersObject.open_flipper('laser_attenuation') # filter OUT
        return
    
    @pyqtSlot(float)    
    def change_power(self, power488_mW):
        self.power488_mW = power488_mW # in mW, is float
        self.laser488.set_power(self.power488_mW)
        return

    @pyqtSlot()
    def update_params(self):
        # Parameters of 488 nm laser
        status488 = self.laser488.status()
        temp488 = self.laser488.base_temp()
        hours488 = self.laser488.hours()
        temp_alarm488 = self.laser488.temp_status()
        
        # Parameters of 532 nm laser
        status532 = self.laser532.status()
        temp532 = self.laser532.base_temp()
        hours532 = self.laser532.hours()
        alarm532 = self.laser532.alarm()
    
        # 488 Parameteres
        print('\n488 laser', \
              '\nStatus:', status488, \
              '\nTemp.:', temp488, \
              '\nHours:', hours488, \
              '\nTemp. alarm:', temp_alarm488)
        # 532 parameters
        print('\n532 laser', \
              '\nStatus:', status532, \
              '\nTemp.:', temp532, \
              '\nHours:', hours532, \
              '\nAlarm:', alarm532)
        return

    @pyqtSlot()
    def close_backend(self):
        print('Disconnecting lasers...')
        self.laser488.close()
        self.laser532.close()
        print('\nClosing all shutters...')
        # self.shutterTrappingLaser(False)
        self.shuttersObject.shutdown()
        print('Closing flippers...')
        self.flippersObject.shutdown()
        print('Exiting thread...')
        workerThread.exit()
        return
       
    def make_connections(self, frontend):
        frontend.shutterTrappingSignal.connect(self.shutterTrappingLaser)
        frontend.shutterSafetySignal.connect(self.shutterSafetyLaser)
        frontend.shutterWhiteSignal.connect(self.shutterWhiteLaser)
        frontend.shutter488_signal.connect(self.shutter488)
        frontend.shutter532_signal.connect(self.shutter532)
        frontend.emission532_signal.connect(self.emission532)
        frontend.LED_signal.connect(self.LEDlight)
        frontend.flipper_apd_signal.connect(self.flipper_apd_attenuation)
        frontend.flipper_spectrometer_path_signal.connect(self.flipper_select_spectrometer)
        frontend.flipper_trapping_laser_signal.connect(self.flipper_trapping_laser_attenuation)
        frontend.powerChangedSignal.connect(self.change_power)
        frontend.updateParams_signal.connect(self.update_params)
        frontend.closeSignal.connect(self.close_backend)
        return
    
#=====================================

#  Main program

#=====================================

if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])

    print('\nDAQ board initialization...')
    daq_board = daq_toolbox.init_daq()

    # create both classes
    gui = Frontend()
    worker = Backend(daq_board)
    
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
    