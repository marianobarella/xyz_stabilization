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
from qtwidgets import Toggle
import lasers_and_serial_toolbox as laserTool
import time as tm

#=====================================

# Initialize lasers

#=====================================

print('\nLooking for serial ports...')
list_of_serial_ports = laserTool.serial_ports()
print('Ports available:', list_of_serial_ports)   
laser532 = laserTool.oxxius_laser(debug_mode = False)
laser488 = laserTool.toptica_laser(debug_mode = False)
shutterTisa = laserTool.Thorlabs_shutter(debug_mode = False)
flipperMirror = laserTool.motorized_flipper(debug_mode = False)
# updateParams_period = 2000 # in ms
initial_blue_power = 1.4 # in mW
initial_wavelength = 852.00 # in nm
starting_wavelength = 700.00 # in nm
ending_wavelength = 1000.00 # in nm
step_wavelength = 10 # in nm

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):
    
    shutterTisa_signal = pyqtSignal(bool)
    shutter488_signal = pyqtSignal(bool)
    shutter532_signal = pyqtSignal(bool)
    emission532_signal = pyqtSignal(bool)
    flipper_signal = pyqtSignal(bool)
    powerChangedSignal = pyqtSignal(float)
    wavelengthChangedSignal = pyqtSignal(float)
    startingWavelengthChangedSignal = pyqtSignal(float)
    endingWavelengthChangedSignal = pyqtSignal(float)
    stepWavelengthChangedSignal = pyqtSignal(float)
    scan_signal = pyqtSignal(bool)
    closeSignal = pyqtSignal()
    updateParams_signal = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Lasers control module"
        self.setWindowTitle(title)
        self.setGeometry(5, 30, 600, 300)
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
        self.updateParamsButton.clicked.connect(self.update_params_button_check)
        self.updateParamsButton.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::pressed { background-color: lightcyan; }")
        
        self.shutter488button.setToolTip('Open/close 488 shutter')
        self.shutter532button.setToolTip('Open/close 532 shutter')
        
        # Flippers 
        self.flipper_label = QtGui.QLabel('Camera selector  | ')
        self.flipperButton_label = QtGui.QLabel('INSPECTION cam')
        self.flipperButton = Toggle(bar_color=QtGui.QColor(42,81,156), 
                                        handle_color=QtGui.QColor(14,73,150), 
                                        checked_color="#bd1e1e")
        self.flipperButton.clicked.connect(self.flipperButton_check)
        self.flipperButton.setToolTip('Up/Down flipper mirror')              
        
        # Ti:Sa wavelength management
        target_wavelength_label = QtGui.QLabel('Target wavelength (nm):')
        self.target_wavelength_edit = QtGui.QLineEdit(str(initial_wavelength))
        self.target_wavelength_edit_previous = float(self.target_wavelength_edit.text())
        self.target_wavelength_edit.editingFinished.connect(self.wavelength_changed_check)
        self.target_wavelength_edit.setValidator(QtGui.QDoubleValidator(698.00, 1002.00, 2))
        current_wavelength_label = QtGui.QLabel('Current wavelength (nm):')
        self.current_wavelength = QtGui.QLabel(str(initial_wavelength))
        
        # wavelength scan
        starting_wavelength_label = QtGui.QLabel('Starting wavelength (nm):')
        self.starting_wavelength_edit = QtGui.QLineEdit(str(starting_wavelength))
        self.starting_wavelength_edit_previous = float(self.starting_wavelength_edit.text())
        self.starting_wavelength_edit.editingFinished.connect(self.starting_wavelength_changed_check)
        self.starting_wavelength_edit.setValidator(QtGui.QDoubleValidator(698.00, 1002.00, 2))
        ending_wavelength_label = QtGui.QLabel('Ending wavelength (nm):')
        self.ending_wavelength_edit = QtGui.QLineEdit(str(ending_wavelength))
        self.ending_wavelength_edit_previous = float(self.ending_wavelength_edit.text())
        self.ending_wavelength_edit.editingFinished.connect(self.ending_wavelength_changed_check)
        self.ending_wavelength_edit.setValidator(QtGui.QDoubleValidator(698.00, 1002.00, 2))
        step_wavelength_label = QtGui.QLabel('Step (nm):')
        self.step_wavelength_edit = QtGui.QLineEdit(str(step_wavelength))
        self.step_wavelength_edit_previous = float(self.step_wavelength_edit.text())
        self.step_wavelength_edit.editingFinished.connect(self.step_wavelength_changed_check)
        self.step_wavelength_edit.setValidator(QtGui.QDoubleValidator(0.00, 100.00, 2))
        
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
        param_list = ['', 'Status', 'Temperature', 'On time', 'Alarms']
        self.no_text488 = '\n'.join(param_list488)
        self.no_text532 = '\n'.join(param_list532)
        self.tab_text = '\n'.join(param_list)
        self.statusBlock488 = QtGui.QLabel(self.no_text488)
        self.statusBlock532 = QtGui.QLabel(self.no_text532)
        self.statusBlockDefinitions = QtGui.QLabel(self.tab_text)
        
        self.grid_shutters = QtGui.QWidget()
        grid_shutters_layout = QtGui.QGridLayout()
        self.grid_shutters.setLayout(grid_shutters_layout)
        
        # Ti:Sa box
        grid_shutters_layout.addWidget(self.shutterTisaButton, 0, 0)
        grid_shutters_layout.addWidget(target_wavelength_label, 1, 0)
        grid_shutters_layout.addWidget(self.target_wavelength_edit, 1, 1)
        grid_shutters_layout.addWidget(current_wavelength_label, 1, 2)
        grid_shutters_layout.addWidget(self.current_wavelength, 1, 3)
        grid_shutters_layout.addWidget(starting_wavelength_label, 2, 0)
        grid_shutters_layout.addWidget(self.starting_wavelength_edit, 2, 1)
        grid_shutters_layout.addWidget(ending_wavelength_label, 2, 2)
        grid_shutters_layout.addWidget(self.ending_wavelength_edit, 2, 3)
        grid_shutters_layout.addWidget(step_wavelength_label, 2, 4)
        grid_shutters_layout.addWidget(self.step_wavelength_edit, 2, 5)
        
        grid_shutters_layout.addWidget(self.scanButton, 3, 0, 1, 6)
        
        # 488 box
        grid_shutters_layout.addWidget(self.shutter488button, 4, 0)
        grid_shutters_layout.addWidget(power488_label, 4, 1)
        grid_shutters_layout.addWidget(self.power488_edit, 4, 2)
        
        # 532 box
        grid_shutters_layout.addWidget(self.shutter532button, 5, 0)
        grid_shutters_layout.addWidget(self.emission532button, 5, 1)
        
        # cameras box
        grid_shutters_layout.addWidget(self.flipper_label, 6, 0)
        grid_shutters_layout.addWidget(self.flipperButton_label, 6, 1)
        grid_shutters_layout.addWidget(self.flipperButton, 6, 2, 1, 2)
        
        # Status box
        grid_shutters_layout.addWidget(self.updateParamsButton, 7, 0, 1, 3)
        grid_shutters_layout.addWidget(self.statusBlockDefinitions, 8, 0)
        grid_shutters_layout.addWidget(self.statusBlock488, 8, 1)
        grid_shutters_layout.addWidget(self.statusBlock532, 8, 2)

        # GUI layout    
        grid = QtGui.QGridLayout()
        self.setLayout(grid)    
        grid.addWidget(self.grid_shutters)
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

    def flipperButton_check(self):
        if self.flipperButton.handle_position == 1:
            self.flipperButton_label.setText('INSPECTION cam')
            self.flipper_signal.emit(True)
        else:
            self.flipperButton_label.setText('XY STABILIZATION cam')
            self.flipper_signal.emit(False)
        return

    def power488_changed_check(self):
        power488_mW = float(self.power488_edit.text()) # in mW
        if power488_mW != self.power488_edit_previous:
            self.power488_edit_previous = power488_mW
            self.powerChangedSignal.emit(power488_mW)
        return
    
    def wavelength_changed_check(self):
        target_wavelength = float(self.target_wavelength_edit.text()) # in mW
        if target_wavelength != self.target_wavelength_edit_previous:
            self.target_wavelength_edit_previous = target_wavelength
            self.wavelengthChangedSignal.emit(target_wavelength)
        return
    
    def starting_wavelength_changed_check(self):
        starting_wavelength = float(self.starting_wavelength_edit.text()) # in mW
        if starting_wavelength != self.starting_wavelength_edit_previous:
            self.starting_wavelength_edit_previous = starting_wavelength
            self.startingWavelengthChangedSignal.emit(starting_wavelength)
        return
    
    def ending_wavelength_changed_check(self):
        ending_wavelength = float(self.ending_wavelength_edit.text()) # in mW
        if ending_wavelength != self.ending_wavelength_edit_previous:
            self.ending_wavelength_edit_previous = ending_wavelength
            self.endingWavelengthChangedSignal.emit(ending_wavelength)
        return
    
    def step_wavelength_changed_check(self):
        step_wavelength = float(self.step_wavelength_edit.text()) # in mW
        if step_wavelength != self.step_wavelength_edit_previous:
            self.step_wavelength_edit_previous = step_wavelength
            self.stepWavelengthChangedSignal.emit(step_wavelength)
        return

    def scan_button_check(self):
        if self.scanButton.isChecked():
            self.scan_signal.emit(True)
        else:
            self.scan_signal.emit(False)
        return
    
    def update_params_button_check(self):
        self.updateParams_signal.emit(True)
        return
    
    @pyqtSlot(list, list)
    def display_params(self, list_of_params488, list_of_params532):
        text_to_display488 = '\n'.join(list_of_params488)
        text_to_display532 = '\n'.join(list_of_params532)
        self.statusBlock488.setText(text_to_display488)
        self.statusBlock532.setText(text_to_display532)
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
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')
        return
    
    def make_connections(self, backend):
        backend.paramSignal.connect(self.display_params)
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):
    
    paramSignal = pyqtSignal(list, list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # set timer to update lasers status
        # self.updateTimer = QtCore.QTimer()
        # self.updateTimer.timeout.connect(self.update_params) 
        # self.updateTimer.setInterval(updateParams_period) # in ms
        self.change_power(initial_blue_power)
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
            flipperMirror.set_inspect_cam_down() # inspection camera ON
        else:
            flipperMirror.set_inspect_cam_up() # inspection camera OFF
        print('Flipper status:', flipperMirror.get_state())
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
        
    def change_wavelength(self, target_wavelength):
        print('\nTarget_wavelength set to %.2f nm' % target_wavelength)
        # self.power488_mW = power488_mW # in mW, is float
        # laser488.set_power(self.power488_mW)
        return
    
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
        
        param_list488 = ['488 laser', status488, temp488, hours488, temp_alarm488]
        param_list532 = ['532 laser', status532, temp532, hours532, alarm532]
        
        # send parameters to GUI
        self.paramSignal.emit(param_list488, param_list532)
        return

    @pyqtSlot()
    def closeBackend(self):
        laser488.close()
        laser532.close()
        flipperMirror.close()
        # print('Stopping updater (QtTimer)...')
        # self.updateTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
       
    def make_connections(self, frontend):
        frontend.shutterTisa_signal.connect(self.shutterTisa)
        frontend.shutter488_signal.connect(self.shutter488)
        frontend.shutter532_signal.connect(self.shutter532)
        frontend.emission532_signal.connect(self.emission532)
        frontend.flipper_signal.connect(self.flipper_inspec_cam)
        frontend.powerChangedSignal.connect(self.change_power)
        frontend.wavelengthChangedSignal.connect(self.change_wavelength)
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
    # worker.updateTimer.moveToThread(workerThread)

    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()

    gui.show()
    app.exec()
    