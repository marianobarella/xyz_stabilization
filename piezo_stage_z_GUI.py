# -*- coding: utf-8 -*-
"""
Graphical User Interface to interact with a 
single-axis Piezo Controller BPC 301 Thorlabs

Created on Wed Jan 22, 2025

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import DockArea, Dock
import piezostage_toolbox as piezoTool
import time as tm

#=====================================

# Initialize stage

#=====================================

# 41401114 deviceID is the benchtop controller BPC 301 for 1 axis
deviceID_BPC301 = '41401114'
piezo_stage_z = piezoTool.BPC301(deviceID_BPC301)
# time period used to update stage position
initial_updatePosition_period = 500 # in ms

initialize_flag = True

#=====================================

# GUI / Frontend definition

#=====================================
  
class Frontend(QtGui.QFrame):

    read_pos_button_signal = pyqtSignal()
    move_signal = pyqtSignal(str, float)
    go_to_pos_signal = pyqtSignal(float)
    feedbackLoopSignal = pyqtSignal(bool)
    # set_reference_signal = pyqtSignal()
    closeSignal = pyqtSignal(bool)

    def __init__(self, main_app = True, *args, **kwargs):  
        super().__init__(*args, **kwargs)
        self.main_app = main_app
        self.setWindowTitle('z piezo stage control')
        self.setUpGUI()
        self.go_to_action()
        return
            
    def setUpGUI(self):
        # Buttons for positionning
        # Read position from piezo controller
        self.read_pos_button = QtGui.QPushButton('Read position')
        self.read_pos_button.clicked.connect(self.get_pos)
        self.read_pos_button.setToolTip('Get current position from the piezo controller')
        self.read_pos_Label = QtGui.QLabel('Position')
        
        # # Set reference
        # self.set_ref_button = QtGui.QPushButton("Set reference")
        # self.set_ref_button.clicked.connect(self.set_reference)
        # self.set_ref_button.setToolTip('Set/lock the position')

        # feedback loop mode
        self.feedback_loop_mode_tickbox = QtGui.QCheckBox('Close-loop mode')
        self.initial_state_feedback_loop_mode = True
        self.feedback_loop_mode_tickbox.setChecked(self.initial_state_feedback_loop_mode)
        self.feedback_loop_mode_tickbox.stateChanged.connect(self.feedback_loop_mode_changed)
        self.feedback_loop_mode_tickbox.setToolTip('Tick = Close-loop mode / Untick = Open-loop mode.')

        # z position control
        self.zLabel = QtGui.QLabel('Nan')  
        self.zLabel.setTextFormat(QtCore.Qt.RichText)
        self.zname = QtGui.QLabel("<strong>z (μm) =")
        self.zname.setTextFormat(QtCore.Qt.RichText)
        self.zUpButton = QtGui.QPushButton("z ▲")
        self.zDownButton = QtGui.QPushButton("z ▼")
        self.zUp2Button = QtGui.QPushButton("z ▲▲")
        self.zDown2Button = QtGui.QPushButton("z ▼▼")
        self.zUpButton.pressed.connect(self.zUp)
        self.zUp2Button.pressed.connect(self.zUp2)
        self.zDownButton.pressed.connect(self.zDown)
        self.zDown2Button.pressed.connect(self.zDown2)
        self.zStepEdit = QtGui.QLineEdit("0.2")
        self.zStepEdit.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        
        # Positioner - Interface
        self.positioner = QtGui.QWidget()
        layout = QtGui.QGridLayout()
        self.positioner.setLayout(layout)
        layout.addWidget(self.read_pos_button, 0, 0, 1, 2)
        layout.addWidget(self.zname,       1, 0)
        layout.addWidget(self.zLabel,      1, 1)
        layout.addWidget(self.zUp2Button,   0, 9, 2, 1)
        layout.addWidget(self.zUpButton,   1, 9, 3, 1)
        layout.addWidget(self.zDownButton, 3, 9, 2, 1)
        layout.addWidget(self.zDown2Button, 5, 9, 2, 1)
        layout.addWidget(QtGui.QLabel("Step z (µm)"), 4, 0)
        layout.addWidget(self.zStepEdit,   5, 0)
        # feedback loop mode
        layout.addWidget(self.feedback_loop_mode_tickbox,   6, 0, 1, 7)

        size = 40
        self.StepEdit = QtGui.QLineEdit("0.2")
        self.StepEdit.setFixedWidth(size)
        self.zStepEdit.setFixedWidth(size)
        
        # Go to - Interface and buttons
        self.gotoWidget = QtGui.QWidget()
        layout2 = QtGui.QGridLayout()
        self.gotoWidget.setLayout(layout2)
        layout2.addWidget(QtGui.QLabel("z (µm)"), 1, 0)
        self.zgotoLabel = QtGui.QLineEdit("10")
        self.gotoButton = QtGui.QPushButton("Go to")
        self.gotoButton.pressed.connect(self.go_to)
        self.zgotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        
        layout2.addWidget(self.gotoButton, 0, 0, 1, 2)
        layout2.addWidget(self.zgotoLabel, 1, 1)
 
        size = 50
        self.zgotoLabel.setFixedWidth(size)
        
        # Do docks       
        hbox = QtGui.QHBoxLayout(self)
        dockArea = DockArea()

        # Positioner
        posDock = Dock('Relative position', size=(1, 1))
        posDock.addWidget(self.positioner)
        dockArea.addDock(posDock)

        # Go to  
        gotoDock = Dock('Go to', size=(1, 2))
        gotoDock.addWidget(self.gotoWidget)
        dockArea.addDock(gotoDock, 'left', posDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
      
    def get_pos(self):
        if self.read_pos_button.isChecked:
            self.read_pos_button_signal.emit()
        return
        
    def zUp(self):
        if self.zUpButton.isChecked:
            self.move_signal.emit('z', float(self.zStepEdit.text()))
        return
    
    def zUp2(self):
        if self.zUp2Button.isChecked:
            self.move_signal.emit('z', 10*float(self.zStepEdit.text()))
        return
    
    def zDown(self):
        if self.zDownButton.isChecked:
            self.move_signal.emit('z', -float(self.zStepEdit.text()))
        return
    
    def zDown2(self):
        if self.zDown2Button.isChecked:
            self.move_signal.emit('z', -10*float(self.zStepEdit.text()))
        return
    
    @pyqtSlot(float)
    def read_pos(self, position):
        self.zLabel.setText('{:.3f}'.format(position))
        return
            
    def set_reference(self):
        if self.set_ref_button.isChecked:
            self.set_reference_signal.emit()
        return
            
    # @pyqtSlot(list)        
    # def get_go_to_reference(self, positions):
    #     list_pos = positions
    #     self.xgotoLabel.setText(str(list_pos[0]))
    #     self.ygotoLabel.setText(str(list_pos[1]))
    #     self.zgotoLabel.setText(str(list_pos[2]))
    #     return
    
    def feedback_loop_mode_changed(self):
        # set ON closed-loop operation
        if self.feedback_loop_mode_tickbox.isChecked():
            self.feedbackLoopSignal.emit(True)
        else:
            self.feedbackLoopSignal.emit(False)
        return
    
    def go_to(self):
        if self.gotoButton.isChecked:
            self.go_to_action()
        return
    
    def go_to_action(self):
        go_to_pos = float(self.zgotoLabel.text())
        self.go_to_pos_signal.emit(go_to_pos)
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
            self.closeSignal.emit(self.main_app)
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_connections(self, backend):
        backend.read_pos_signal.connect(self.read_pos)
        # backend.reference_signal.connect(self.get_go_to_reference)

#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    read_pos_signal = pyqtSignal(float)
    # reference_signal = pyqtSignal(list)

    def __init__(self, piezo_stage, \
                 updatePosition_period = initial_updatePosition_period, \
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage_z = piezo_stage
        self.initialize_piezo()
        # set timer to update lasers status
        self.updatePosition_period = updatePosition_period
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.setInterval(self.updatePosition_period) # in ms
        return
    
    def initialize_piezo(self):
        # initialize (connect)
        self.piezo_stage_z.connect()
        # method to check if it's connected
        if self.piezo_stage_z.controller.IsConnected:
            print('z piezo stage succesfully connected.')
        else:
            print('Couldn\'t connect to z piezo stage.')

        # get info
        print(self.piezo_stage_z.get_info())
        print('Zeroing the z piezo stage. This step takes around 30 s. Please wait...\n')
        # perform zero routine for all axis
        if initialize_flag:
            self.piezo_stage_z.zero()
        return
    
    @pyqtSlot()
    def read_position(self):
        """
        Read position from controller
        """ 
        z_pos = self.piezo_stage_z.get_axis_position('z')
        z_pos = round(z_pos, 3)
        self.read_pos_signal.emit(z_pos)
        return z_pos
    
    # @pyqtSlot()
    # def set_reference(self):
    #     x_pos, y_pos, z_pos = self.read_pos()
    #     self.reference_signal.emit([x_pos, y_pos, z_pos])
    #     return

    @pyqtSlot(str, float)
    def move_relative(self, axis, distance):
        """ 
        Moves the stage relative to its current position along the specified axis.
        """
        # uncomment for debbuging
        # impose a settling time before reading
        # tm.sleep(0.5) 
        # z_pos_before = self.read_position() 
        # print('\nBefore')
        # print('z_pos', z_pos_before)
        # print('Asking for a %.3f step on %s axis' % (distance, axis) )
        if axis == 'z':
            self.piezo_stage_z.move_relative(axis, distance)
        else:
            print('Cannot do \"move relative\". Axis should be z.')
        # check piezo_toolbox.py\response_time function
        # after running it, it's clear that 0.5 s is a suitable settling time
        # uncomment for debbuging
        # impose a settling time before reading
        # tm.sleep(0.5) 
        # z_pos_after = self.read_position() 
        # print('After')
        # print('z_pos', z_pos_after)
        # print('z_shift', round((z_pos_after-z_pos_before), 3))
        return

    @pyqtSlot(float)
    def move_absolute(self, position):
        """
        Moves the stage to an absolute position.
        """
        # print("Setting Position:", position)
        self.piezo_stage_z.set_position(z = position)
        self.read_position() 
        return
    
    @pyqtSlot(bool)
    def switch_feedback_loop_mode(self, close_flag):
        """ 
        Set (True) or Unset (False) feedback loop mode
        """
        self.piezo_stage_z.set_close_loop(close_flag)
        return
    
    def run(self):
        self.updateTimer.start()
        return

    @pyqtSlot(bool)
    def close_backend(self, main_app = True):
        print('Stopping updater (QtTimer)...')
        self.updateTimer.stop()
        if main_app:
            print('Shutting down piezo stage...')
            self.piezo_stage_z.shutdown()
            print('Exiting thread...')
            tm.sleep(5)
            workerThread.exit()
        return            

    def make_connections(self, frontend):
        frontend.read_pos_button_signal.connect(self.read_position)
        frontend.move_signal.connect(self.move_relative)
        # frontend.set_reference_signal.connect(self.set_reference)
        frontend.go_to_pos_signal.connect(self.move_absolute)
        frontend.feedbackLoopSignal.connect(self.switch_feedback_loop_mode)
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
    worker = Backend(piezo_stage_z)
    
    # # thread that run in background
    workerThread = QtCore.QThread()
    worker.updateTimer.moveToThread(workerThread)
    worker.updateTimer.timeout.connect(worker.read_position)
    worker.moveToThread(workerThread)
    
    # start timer when thread has started
    workerThread.started.connect(worker.run)

    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # # start worker in a different thread (avoids GUI freezing)
    workerThread.start()

    gui.show()
    app.exec()