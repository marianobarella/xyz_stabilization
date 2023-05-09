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
updateParams_period = 5000 # in ms
initial_blue_power = 1.4 # in mW

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QFrame):

    shutter488_signal = pyqtSignal(bool)
    shutter532_signal = pyqtSignal(bool)
    shutterTisa_signal = pyqtSignal(bool)
    flipper_signal = pyqtSignal(bool)
    powerChangedSignal = pyqtSignal(float)
    closeSignal = pyqtSignal()
    updateParams_signal = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Lasers control module"
        self.setWindowTitle(title)
        return
    
    def setUpGUI(self):       
 
        # Shutters
        self.shutterTisaButton = QtGui.QCheckBox('Ti:Sa shutter')
        self.shutterTisaButton.clicked.connect(self.control_tisa_button_check)
        self.shutterTisaButton.setStyleSheet("color: darkMagenta; ")
        
        self.shutter488button = QtGui.QCheckBox('488 nm (blue)')
        self.shutter488button.clicked.connect(self.control_488_button_check)
        self.shutter488button.setStyleSheet("color: blue; ")

        self.shutter532button = QtGui.QCheckBox('532 nm (green)')
        self.shutter532button.clicked.connect(self.control_532_button_check)
        self.shutter532button.setStyleSheet("color: green; ")
        
        self.updateParamsButton = QtGui.QPushButton('Continuously update lasers\' parameters')
        self.updateParamsButton.setCheckable(True)
        self.updateParamsButton.clicked.connect(self.update_params_button_check)
        self.updateParamsButton.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::checked { background-color: lightgreen; }")
        
        self.shutter488button.setToolTip('Open/close 488 shutter')
        self.shutter532button.setToolTip('Open/close 532 shutter')
        self.updateParamsButton.setToolTip('Retrieve continuosly lasers\' parameters')
        
        # Flippers 
        self.flipperButton = QtGui.QCheckBox('Camera selector  | ')
        self.flipperButton.setStyleSheet("color: black; ")
        self.flipperButton.setChecked(True)
        self.flipperButton.clicked.connect(self.flipperButton_check)
        self.flipperButton_label = QtGui.QLabel('Inspection camera')
        self.flipperButton_label.setStyleSheet("color: black; ")
        self.flipperButton_label.setToolTip('Up/Down flipper mirror')        
        
        # 488 power
        power488_label = QtGui.QLabel('Power 488 (mW):')
        self.power488_edit = QtGui.QLineEdit(str(initial_blue_power))
        self.power488_edit_previous = float(self.power488_edit.text())
        self.power488_edit.editingFinished.connect(self.power488_changed_check)
        self.power488_edit.setValidator(QtGui.QDoubleValidator(0.00, 200.00, 2))
        
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
        grid_shutters_layout.addWidget(self.shutterTisaButton, 0, 0)
        grid_shutters_layout.addWidget(self.shutter488button, 1, 0)
        grid_shutters_layout.addWidget(self.shutter532button, 2, 0)
        grid_shutters_layout.addWidget(self.flipperButton, 3, 0)
        grid_shutters_layout.addWidget(self.flipperButton_label, 3, 1, 1, 2)
        
        # Power box
        grid_shutters_layout.addWidget(power488_label, 1, 1)
        grid_shutters_layout.addWidget(self.power488_edit, 1, 2)
        # Status box
        grid_shutters_layout.addWidget(self.updateParamsButton, 4, 0, 1, 3)
        grid_shutters_layout.addWidget(self.statusBlockDefinitions, 5, 0)
        grid_shutters_layout.addWidget(self.statusBlock488, 5, 1)
        grid_shutters_layout.addWidget(self.statusBlock532, 5, 2)

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

    def flipperButton_check(self):
        if self.flipperButton.isChecked():
            print('caca')
            self.flipperButton_label.setText('INSPECTION cam (Thorlabs)')
            self.flipper_signal.emit(True)
        else:
            self.flipperButton_label.setText('XY STABILIZATION cam (pco)')
            self.flipper_signal.emit(False)
        return

    def power488_changed_check(self):
        power488_mW = float(self.power488_edit.text()) # in mW
        if power488_mW != self.power488_edit_previous:
            print('\nPower 488 changed to', power488_mW, 'mW')
            self.power488_edit_previous = power488_mW
            self.powerChangedSignal.emit(power488_mW)
        return
    
    def update_params_button_check(self):
        if self.updateParamsButton.isChecked():
            self.updateParams_signal.emit(True)
        else:
            self.updateParams_signal.emit(False)
            self.statusBlock488.setText(self.no_text488)
            self.statusBlock532.setText(self.no_text532)
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
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.update_params) 
        self.updateTimer.setInterval(updateParams_period) # in ms
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
    
    @pyqtSlot(bool)    
    def start_updating_params(self, updatebool):
        if updatebool:
            print('Starting updater (QtTimer)... Update period: %.1f s' % (updateParams_period/1000))
            self.updateTimer.start()
        else:
            print('Stopping updater (QtTimer)...')
            self.updateTimer.stop()
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
        print('Stopping updater (QtTimer)...')
        self.updateTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
       
    def make_connections(self, frontend):
        frontend.shutterTisa_signal.connect(self.shutterTisa)
        frontend.shutter488_signal.connect(self.shutter488)
        frontend.shutter532_signal.connect(self.shutter532)
        frontend.flipper_signal.connect(self.flipper_inspec_cam)
        frontend.powerChangedSignal.connect(self.change_power)
        frontend.closeSignal.connect(self.closeBackend)
        frontend.updateParams_signal.connect(self.start_updating_params)
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
    worker.updateTimer.moveToThread(workerThread)

    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()

    gui.show()
    app.exec()