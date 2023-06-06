# -*- coding: utf-8 -*-
"""
Created on Mon May 2, 2022

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

# ID of the benchtop controller BPC303
deviceID = '71260444'
piezo_stage = piezoTool.BPC303(deviceID)
# initialize (connect)
piezo_stage.connect()
# method to check if it's connected
if piezo_stage.controller.IsConnected:
    print('Piezo stage succesfully connected.')
else:
    print('Couldn\'t connect to piezo stage.')
# get info
print(piezo_stage.get_info())
print('Zeroing the piezo stage. This step takes around 30 s. Please wait...\n')
# perform zero routine for all axis
piezo_stage.zero('all')

# time period used to update stage position
initial_updatePosition_period = 500 # in ms

#=====================================

# GUI / Frontend definition

#=====================================
  
class Frontend(QtGui.QFrame):

    read_pos_button_signal = pyqtSignal()
    move_signal = pyqtSignal(str, float)
    go_to_pos_signal = pyqtSignal(list)
    feedbackLoopSignal = pyqtSignal(bool)
    # set_reference_signal = pyqtSignal()
    closeSignal = pyqtSignal(bool)

    def __init__(self, main_app = True, *args, **kwargs):  
        super().__init__(*args, **kwargs)
        self.main_app = main_app
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

        # xyz position control
        self.StepEdit = QtGui.QLineEdit("0.2")
        self.StepEdit.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))

        self.xLabel = QtGui.QLabel('Nan')
        self.xLabel.setTextFormat(QtCore.Qt.RichText)
        self.xname = QtGui.QLabel("<strong>x (μm) =")
        self.xname.setTextFormat(QtCore.Qt.RichText)
        self.xUpButton = QtGui.QPushButton("x ►")
        self.xDownButton = QtGui.QPushButton("◄ x")
        self.xUp2Button = QtGui.QPushButton("x ►►")  
        self.xDown2Button = QtGui.QPushButton("◄◄ x")
        self.xUpButton.pressed.connect(self.xUp)
        self.xUp2Button.pressed.connect(self.xUp2)
        self.xDownButton.pressed.connect(self.xDown)
        self.xDown2Button.pressed.connect(self.xDown2)

        self.yLabel = QtGui.QLabel('Nan')
        self.yLabel.setTextFormat(QtCore.Qt.RichText)
        self.yname = QtGui.QLabel("<strong>y (μm) =")
        self.yname.setTextFormat(QtCore.Qt.RichText)
        self.yUpButton = QtGui.QPushButton("y ▲")  # ↑
        self.yDownButton = QtGui.QPushButton("y ▼")  # ↓
        self.yUp2Button = QtGui.QPushButton("y ▲▲")  # ↑
        self.yDown2Button = QtGui.QPushButton("y ▼▼")  # ↓
        self.yUpButton.pressed.connect(self.yUp)
        self.yUp2Button.pressed.connect(self.yUp2)
        self.yDownButton.pressed.connect(self.yDown)
        self.yDown2Button.pressed.connect(self.yDown2)

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

        size = 50
        self.xUp2Button.setFixedWidth(size)
        self.xDown2Button.setFixedWidth(size)
        self.xUpButton.setFixedWidth(size)
        self.xDownButton.setFixedWidth(size)
        self.yUp2Button.setFixedWidth(size)
        self.yDown2Button.setFixedWidth(size)
        self.yUpButton.setFixedWidth(size)
        self.yDownButton.setFixedWidth(size)
        
        # Positioner - Interface
        self.positioner = QtGui.QWidget()
        layout = QtGui.QGridLayout()
        self.positioner.setLayout(layout)
        layout.addWidget(self.read_pos_button, 0, 0, 1, 2)
        layout.addWidget(self.xname,        1, 0)
        layout.addWidget(self.xLabel,       1, 1)
        layout.addWidget(self.xUpButton,    2, 6, 2, 1)
        layout.addWidget(self.xDownButton,  2, 4, 2, 1)
        layout.addWidget(self.xUp2Button,   2, 7, 2, 1)
        layout.addWidget(self.xDown2Button, 2, 3, 2, 1)
        layout.addWidget(self.yname,       2, 0)
        layout.addWidget(self.yLabel,      2, 1)
        layout.addWidget(self.yUpButton,   1, 5, 3, 1)
        layout.addWidget(self.yDownButton, 3, 5, 2, 1)
        layout.addWidget(QtGui.QLabel("Step x/y (µm)"), 4, 6, 1, 2)
        layout.addWidget(self.StepEdit,   5, 6)
        layout.addWidget(self.yUp2Button,   0, 5, 2, 1)
        layout.addWidget(self.yDown2Button, 4, 5, 2, 1)
        layout.addWidget(self.zname,       3, 0)
        layout.addWidget(self.zLabel,      3, 1)
        layout.addWidget(self.zUp2Button,   0, 9, 2, 1)
        layout.addWidget(self.zUpButton,   1, 9, 3, 1)
        layout.addWidget(self.zDownButton, 3, 9, 2, 1)
        layout.addWidget(self.zDown2Button, 4, 9, 2, 1)
        layout.addWidget(QtGui.QLabel("Step z (µm)"), 4, 10)
        layout.addWidget(self.zStepEdit,   5, 10)
        # feedback loop mode
        layout.addWidget(self.feedback_loop_mode_tickbox,   6, 0, 1, 7)

        size = 40
        self.StepEdit.setFixedWidth(size)
        self.zStepEdit.setFixedWidth(size)
        
        # Go to - Interface and buttons
        self.gotoWidget = QtGui.QWidget()
        layout2 = QtGui.QGridLayout()
        self.gotoWidget.setLayout(layout2)
        layout2.addWidget(QtGui.QLabel("x (µm)"), 1, 0)
        layout2.addWidget(QtGui.QLabel("y (µm)"), 2, 0)
        layout2.addWidget(QtGui.QLabel("z (µm)"), 3, 0)
        self.xgotoLabel = QtGui.QLineEdit("10")
        self.ygotoLabel = QtGui.QLineEdit("10")
        self.zgotoLabel = QtGui.QLineEdit("10")
        self.gotoButton = QtGui.QPushButton("Go to")
        self.gotoButton.pressed.connect(self.go_to)
        self.xgotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        self.ygotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        self.zgotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        
        layout2.addWidget(self.gotoButton, 0, 0, 1, 2)
        layout2.addWidget(self.xgotoLabel, 1, 1)
        layout2.addWidget(self.ygotoLabel, 2, 1)
        layout2.addWidget(self.zgotoLabel, 3, 1)
 
        size = 50
        self.xgotoLabel.setFixedWidth(size)
        self.ygotoLabel.setFixedWidth(size)
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
        
    def xUp(self):
        if self.xUpButton.isChecked:
            self.move_signal.emit('x', float(self.StepEdit.text()))
        return
    
    def xUp2(self):
        if self.xUp2Button.isChecked:
            self.move_signal.emit('x', 10*float(self.StepEdit.text()))
        return
    
    def xDown(self):
        if self.xDownButton.isChecked:
            self.move_signal.emit('x', -float(self.StepEdit.text()))
        return
    
    def xDown2(self):
        if self.xDown2Button.isChecked:
            self.move_signal.emit('x', -10*float(self.StepEdit.text()))
        return
    
    def yUp(self):
        if self.yUpButton.isChecked:
            self.move_signal.emit('y', float(self.StepEdit.text()))
        return
    
    def yUp2(self):
        if self.xUp2Button.isChecked:
            self.move_signal.emit('y', 10*float(self.StepEdit.text()))
        return
    
    def yDown(self):
        if self.yDownButton.isChecked:
            self.move_signal.emit('y', -float(self.StepEdit.text()))
        return
    
    def yDown2(self):
        if self.yDown2Button.isChecked:
            self.move_signal.emit('y', -10*float(self.StepEdit.text()))
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
    
    @pyqtSlot(list)
    def read_pos_list(self, position):
        self.xLabel.setText('{:.3f}'.format(position[0]))
        self.yLabel.setText('{:.3f}'.format(position[1]))
        self.zLabel.setText('{:.3f}'.format(position[2]))
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
        go_to_pos = [float(self.xgotoLabel.text()), float(self.ygotoLabel.text()), float(self.zgotoLabel.text())]
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
        backend.read_pos_signal.connect(self.read_pos_list)
        # backend.reference_signal.connect(self.get_go_to_reference)

#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    read_pos_signal = pyqtSignal(list)
    # reference_signal = pyqtSignal(list)

    def __init__(self, piezo_stage, \
                 updatePosition_period = initial_updatePosition_period, \
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage = piezo_stage
        # set timer to update lasers status
        self.updatePosition_period = updatePosition_period
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.read_position)
        self.updateTimer.setInterval(self.updatePosition_period) # in ms
        self.updateTimer.start()
        self.move_absolute([10, 10, 10])
        return
    
    @pyqtSlot()
    def read_position(self):
        """
        Read position from controller
        """ 
        x_pos = self.piezo_stage.get_axis_position('x')
        y_pos = self.piezo_stage.get_axis_position('y')
        z_pos = self.piezo_stage.get_axis_position('z')
        x_pos = round(x_pos, 3)
        y_pos = round(y_pos, 3)
        z_pos = round(z_pos, 3)
        self.read_pos_signal.emit([x_pos, y_pos, z_pos])
        return x_pos, y_pos, z_pos
    
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
        # x_pos_before, y_pos_before, z_pos_before = self.read_position() 
        # print('\nBefore')
        # print('x_pos', x_pos_before)
        # print('y_pos', y_pos_before)
        # print('z_pos', z_pos_before)
        # print('Asking for a %.3f step on %s axis' % (distance, axis) )
        self.piezo_stage.move_relative(axis, distance)
        # check piezo_toolbox.py\response_time function
        # after running it, it's clear that 0.5 s is a suitable settling time
        # uncomment for debbuging
        # impose a settling time before reading
        # tm.sleep(0.5) 
        # x_pos_after, y_pos_after, z_pos_after = self.read_position() 
        # print('After')
        # print('x_pos', x_pos_after)
        # print('y_pos', y_pos_after)
        # print('z_pos', z_pos_after)
        # print('x_shift', round((x_pos_after-x_pos_before), 3))
        # print('y_shift', round((y_pos_after-y_pos_before), 3))
        # print('z_shift', round((z_pos_after-z_pos_before), 3))
        return

    @pyqtSlot(list)
    def move_absolute(self, position):
        """
        Moves the stage to an absolute position.
        """
        # first x, then y, and last z
        # print("Setting Position:", position)
        self.piezo_stage.set_position(x = position[0], \
                                      y = position[1], \
                                      z = position[2])
        self.read_position() 
        return
    
    @pyqtSlot(bool)
    def switch_feedback_loop_mode(self, close_flag):
        """ 
        Set (True) or Unset (False) feedback loop mode
        """
        self.piezo_stage.set_close_loop(close_flag)
        return
    
    @pyqtSlot(bool)
    def close_backend(self, main_app = True):
        print('Stopping updater (QtTimer)...')
        self.updateTimer.stop()
        if main_app:
            print('Shutting down piezo stage...')
            self.piezo_stage.shutdown()
            print('Exiting thread...')
            tm.sleep(1)
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
    worker = Backend(piezo_stage)
    
    # # thread that run in background
    workerThread = QtCore.QThread()
    worker.updateTimer.moveToThread(workerThread)
    worker.moveToThread(workerThread)

    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # # start worker in a different thread (avoids GUI freezing)
    workerThread.start()

    gui.show()
    app.exec()