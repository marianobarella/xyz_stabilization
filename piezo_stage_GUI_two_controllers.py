# -*- coding: utf-8 -*-
"""
Created on Mon May 2, 2022
Modified on Mon Jan 20, 2025

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

# 71260444 deviceID is the benchtop controller BPC 303 for 3 axis
deviceID_BPC303 = '71260444'
# 41401114 deviceID is the benchtop controller BPC 301 for 1 axis
deviceID_BPC301 = '41401114'
piezo_stage_xy = piezoTool.BPC303(deviceID_BPC303)
piezo_stage_z = piezoTool.BPC301(deviceID_BPC301)
# time period used to update stage position
initial_updatePosition_period = 500 # in ms
# set True if you want to perform zero the stage during initialization
zeroing_flag = False

#=====================================

# GUI / Frontend definition

#=====================================
  
class Frontend(QtGui.QFrame):

    read_pos_button_signal = pyqtSignal()
    move_signal = pyqtSignal(str, float)
    go_to_pos_signal = pyqtSignal(list)
    feedbackLoopSignal = pyqtSignal(bool)
    # set_reference_signal = pyqtSignal()
    zeroing_signal = pyqtSignal()
    closeSignal = pyqtSignal(bool)

    def __init__(self, main_app = True, *args, **kwargs):  
        super().__init__(*args, **kwargs)
        self.main_app = main_app
        self.setWindowTitle('xyz two piezo stages control')
        self.setGeometry(850, 30, 200, 200) # x pos, y pos, width, height
        self.setUpGUI()
        # self.go_to_action()
        return
            
    def setUpGUI(self):
        # Buttons for positionning
        # Read position from piezo controller
        self.read_pos_button = QtGui.QPushButton('Copy position')
        self.read_pos_button.clicked.connect(self.get_pos)
        self.read_pos_button.setToolTip('Copy current position from the piezo controller top go-to sub-module.')
        
        # Zero the stage
        self.zeroingButton = QtGui.QPushButton('Zero the stage and center')
        self.zeroingButton.clicked.connect(self.zero)
        self.zeroingButton.setToolTip('Send instruction to zero the 3 axes and go to the center of their range.')

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

        # xy position control
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

        size = 50
        self.xUp2Button.setFixedWidth(size)
        self.xDown2Button.setFixedWidth(size)
        self.xUpButton.setFixedWidth(size)
        self.xDownButton.setFixedWidth(size)
        self.yUp2Button.setFixedWidth(size)
        self.yDown2Button.setFixedWidth(size)
        self.yUpButton.setFixedWidth(size)
        self.yDownButton.setFixedWidth(size)
        
        # Read position - Interface and buttons
        self.read_pos_widget = QtGui.QWidget()
        layout_read_pos = QtGui.QGridLayout()
        self.read_pos_widget.setLayout(layout_read_pos)
        layout_read_pos.addWidget(self.read_pos_button, 0, 0, 1, 2)
        layout_read_pos.addWidget(self.xname,        1, 0)
        layout_read_pos.addWidget(self.xLabel,       1, 1)
        layout_read_pos.addWidget(self.yname,       2, 0)
        layout_read_pos.addWidget(self.yLabel,      2, 1)
        layout_read_pos.addWidget(self.zname,       3, 0)
        layout_read_pos.addWidget(self.zLabel,      3, 1)

        # Positioner - Interface and buttons
        self.positioner = QtGui.QWidget()
        layout_xyz_control = QtGui.QGridLayout()
        self.positioner.setLayout(layout_xyz_control)
        layout_xyz_control.addWidget(self.xUpButton,    2, 3, 2, 1)
        layout_xyz_control.addWidget(self.xDownButton,  2, 1, 2, 1)
        layout_xyz_control.addWidget(self.xUp2Button,   2, 4, 2, 1)
        layout_xyz_control.addWidget(self.xDown2Button, 2, 0, 2, 1)
        layout_xyz_control.addWidget(self.yUpButton,    1, 2, 2, 1)
        layout_xyz_control.addWidget(self.yDownButton,  3, 2, 2, 1)
        layout_xyz_control.addWidget(self.yUp2Button,   0, 2, 2, 1)
        layout_xyz_control.addWidget(self.yDown2Button, 4, 2, 2, 1)
        layout_xyz_control.addWidget(QtGui.QLabel("Step x/y (µm)"), 7, 0, 1, 2)
        layout_xyz_control.addWidget(self.StepEdit,     7, 2)
        layout_xyz_control.addWidget(self.zUp2Button,   0, 5, 2, 1)
        layout_xyz_control.addWidget(self.zUpButton,    1, 5, 2, 1)
        layout_xyz_control.addWidget(self.zDownButton,  3, 5, 2, 1)
        layout_xyz_control.addWidget(self.zDown2Button, 4, 5, 2, 1)
        layout_xyz_control.addWidget(QtGui.QLabel("Step z (µm)"), 7, 4)
        layout_xyz_control.addWidget(self.zStepEdit,    7, 5)
        # feedback loop mode
        layout_xyz_control.addWidget(self.feedback_loop_mode_tickbox,   8, 0, 1, 3)
        layout_xyz_control.addWidget(self.zeroingButton,   8, 3, 1, 3)

        size = 40
        self.StepEdit.setFixedWidth(size)
        self.zStepEdit.setFixedWidth(size)
        
        # Go to - Interface and buttons
        self.gotoWidget = QtGui.QWidget()
        layout_goto = QtGui.QGridLayout()
        self.gotoWidget.setLayout(layout_goto)
        layout_goto.addWidget(QtGui.QLabel("x (µm)"), 1, 0)
        layout_goto.addWidget(QtGui.QLabel("y (µm)"), 2, 0)
        layout_goto.addWidget(QtGui.QLabel("z (µm)"), 3, 0)
        self.xgotoLabel = QtGui.QLineEdit("10")
        self.ygotoLabel = QtGui.QLineEdit("10")
        self.zgotoLabel = QtGui.QLineEdit("10")
        self.gotoButton = QtGui.QPushButton("Go to XYZ")
        self.gotoButton.pressed.connect(self.go_to)
        self.xgotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        self.ygotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        self.zgotoLabel.setValidator(QtGui.QDoubleValidator(0.000, 20.000, 3))
        
        # self.gotoButtonX = QtGui.QPushButton("Go to X")
        # self.gotoButtonY = QtGui.QPushButton("Go to Y")
        # self.gotoButtonZ = QtGui.QPushButton("Go to Z")
        # self.gotoButtonX.pressed.connect(self.go_to_x)
        # self.gotoButtonY.pressed.connect(self.go_to_y)
        # self.gotoButtonZ.pressed.connect(self.go_to_z)

        layout_goto.addWidget(self.gotoButton, 0, 0, 1, 2)
        layout_goto.addWidget(self.xgotoLabel, 1, 1)
        layout_goto.addWidget(self.ygotoLabel, 2, 1)
        layout_goto.addWidget(self.zgotoLabel, 3, 1)
 
        size = 50
        self.xgotoLabel.setFixedWidth(size)
        self.ygotoLabel.setFixedWidth(size)
        self.zgotoLabel.setFixedWidth(size)
        
        # Do docks       
        hbox = QtGui.QHBoxLayout(self)
        dockArea = DockArea()

        # Read pos
        readPosDock = Dock('Position', size=(1, 2))
        readPosDock.setOrientation('horizontal')
        readPosDock.addWidget(self.read_pos_widget)
        dockArea.addDock(readPosDock)
        # Positioner
        posDock = Dock('Controller', size=(2, 1))
        posDock.addWidget(self.positioner)
        dockArea.addDock(posDock, 'top', readPosDock)
        # Go to  
        gotoDock = Dock('Go to', size=(1, 2))
        gotoDock.setOrientation('horizontal')
        gotoDock.addWidget(self.gotoWidget)
        dockArea.addDock(gotoDock, 'left', readPosDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
      
    def get_pos(self):
        if self.read_pos_button.isChecked:
            self.xgotoLabel.setText('{}'.format(self.xLabel.text()))
            self.ygotoLabel.setText('{}'.format(self.yLabel.text()))
            self.zgotoLabel.setText('{}'.format(self.zLabel.text()))
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

    def zero(self):
        if self.zeroingButton.isChecked:
            reply = QtGui.QMessageBox.question(self, 'Zeroing warning', '\nAre you sure you want to zero the stage?\n \nThe stage will: \n- go idle for 35 s\n- do the calibration \n- move to (10,10,10)',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
            if reply == QtGui.QMessageBox.Yes:
                # emit the signal to perfom zero
                self.zeroing_signal.emit()
            else:
                print('Zero not performed.')            
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
        return

#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    read_pos_signal = pyqtSignal(list)
    # reference_signal = pyqtSignal(list)

    def __init__(self, piezo_stage_xy, piezo_stage_z, \
                 updatePosition_period = initial_updatePosition_period, \
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage_xy = piezo_stage_xy
        self.piezo_stage_z = piezo_stage_z
        self.initialize_piezo()
        # set timer to update lasers status
        self.updatePosition_period = updatePosition_period
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.setInterval(self.updatePosition_period) # in ms
        return
    
    def initialize_piezo(self):
        # initialize (connect)
        self.piezo_stage_xy.connect()
        self.piezo_stage_z.connect()
        # method to check if it's connected
        # if self.piezo_stage_xy.controller.IsConnected:
        #     print('xy piezo stage succesfully connected.')
        # else:
        #     print('Couldn\'t connect to xy piezo stage.')
        # if self.piezo_stage_z.controller.IsConnected:
        #     print('z piezo stage succesfully connected.')
        # else:
        #     print('Couldn\'t connect to z piezo stage.')
        # get info
        print(self.piezo_stage_xy.get_info())
        print(self.piezo_stage_z.get_info())
        if zeroing_flag:
            print('Zeroing the xy piezo stage. This step takes around 20 s. Please wait...\n')
            # perform zero routine for all axis
            self.piezo_stage_xy.zero('x')
            self.piezo_stage_xy.zero('y')
            print('Zeroing the z piezo stage. This step takes around 10 s. Please wait...\n')
            # perform zero routine for all axis
            self.piezo_stage_z.zero()
            # move to the center of the 3D range
            tm.sleep(5)
            self.move_absolute([10, 10, 10])
        return
    
    @pyqtSlot()
    def read_position(self):
        """
        Read position from controller
        """ 
        x_pos = self.piezo_stage_xy.get_axis_position('x')
        y_pos = self.piezo_stage_xy.get_axis_position('y')
        z_pos = self.piezo_stage_z.get_axis_position('z')
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
        if axis == 'x' or axis == 'y':
            self.piezo_stage_xy.move_relative(axis, distance)
        elif axis == 'z':
            self.piezo_stage_z.move_relative(axis, distance)
        else:
            print('Cannot do \"move relative\". Axis should be x, y or z.')
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
        self.piezo_stage_xy.set_position(x = position[0], \
                                         y = position[1], \
                                         z = 0)
        self.piezo_stage_z.set_position(z = position[2])
        self.read_position() 
        return
    
    @pyqtSlot(bool)
    def switch_feedback_loop_mode(self, close_flag):
        """ 
        Set (True) or Unset (False) feedback loop mode
        """
        self.piezo_stage_xy.set_close_loop(close_flag)
        self.piezo_stage_z.set_close_loop(close_flag)
        return

    @pyqtSlot()
    def do_zeroing(self):
        """ 
        Perform zeroing of the axes and move to the center of their range
        """
        self.piezo_stage_xy.zero('x')
        self.piezo_stage_xy.zero('y')
        self.piezo_stage_z.zero()
        tm.sleep(5)
        self.move_absolute([10, 10, 10])
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
            self.piezo_stage_xy.shutdown()
            tm.sleep(5)
            self.piezo_stage_z.shutdown()
            tm.sleep(5)
            print('Exiting thread...')
            workerThread.exit()
        return            

    def make_connections(self, frontend):
        frontend.read_pos_button_signal.connect(self.read_position)
        frontend.move_signal.connect(self.move_relative)
        # frontend.set_reference_signal.connect(self.set_reference)
        frontend.zeroing_signal.connect(self.do_zeroing)
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
    worker = Backend(piezo_stage_xy, piezo_stage_z)

    # Threads that run in background
    workerThread = QtCore.QThread()
    # move worker and its timers to a different thread (avoids GUI freezing)
    worker.updateTimer.moveToThread(workerThread)
    worker.updateTimer.timeout.connect(worker.read_position)
    worker.moveToThread(workerThread)

    # start timer when thread has started
    workerThread.started.connect(worker.run)
    
    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)

    # start worker
    workerThread.start()
    
    gui.show()
    app.exec()