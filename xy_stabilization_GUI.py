# -*- coding: utf-8 -*-
"""
Created on Thu May 12, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import os
import numpy as np
from datetime import datetime
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import Dock, DockArea
import pco_camera_toolbox as pco
from PIL import Image
from tkinter import filedialog
import tkinter as tk
import time as tm

#=====================================

# Initialize camera and useful variables

#=====================================

cam = pco.pco_camera()
initial_pixel_size = 65 # in nm (with 1x1 binning)
initial_filepath = 'D:\\daily_data' # save in SSD for fast and daily use
initial_filename = 'image_pco_test'
viewTimer_update = 17 # in ms (makes no ses to go lower than the refresh rate of the screen)

#=====================================

# GUI / Frontend definition

#=====================================
   
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    closeSignal = pyqtSignal()
    roiChangedSignal = pyqtSignal(bool, list)
    exposureChangedSignal = pyqtSignal(bool, float)
    binningChangedSignal = pyqtSignal(bool, int)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of the window
        title = "XY stabilization module"
        self.setWindowTitle(title)
            
    def setUpGUI(self):
        
        # Image
        imageWidget = pg.GraphicsLayoutWidget()
        self.vb = imageWidget.addPlot()
        self.img = pg.ImageItem()
        self.img.setOpts(axisOrder = 'row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image = self.img, levelMode = 'mono')
        self.hist.gradient.loadPreset('grey')
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin = 0, yMax = 65536) # 16-bit camera
        imageWidget.addItem(self.hist, row = 0, col = 1)
        # TODO: if performance is an issue, try scaleToImage

        self.autolevel_tickbox = QtGui.QCheckBox('Autolevel')
        self.initial_autolevel_state = True
        self.autolevel_tickbox.setChecked(self.initial_autolevel_state)
        self.autolevel_tickbox.setText('Autolevel')
        self.autolevel_tickbox.stateChanged.connect(self.autolevel)
        self.autolevel_bool = self.initial_autolevel_state

        # Working folder and filename
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        self.working_dir_path.setReadOnly(True) 

        # Buttons and labels
        self.take_picture_button = QtGui.QPushButton('Take a picture')
        self.take_picture_button.setCheckable(False)
        self.take_picture_button.clicked.connect(self.take_picture_button_check)
        self.take_picture_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: red; }")
        
        self.save_picture_button = QtGui.QPushButton('Save picture')
        self.save_picture_button.clicked.connect(self.save_button_check)
        self.save_picture_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: blue; }")
        
        self.live_view_button = QtGui.QPushButton('Live view')
        self.live_view_button.setCheckable(True)
        self.live_view_button.clicked.connect(self.liveview_button_check)
        self.live_view_button.setStyleSheet(
            "QPushButton { background-color: yellow; }"
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: red; }")

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit('100')
        self.exp_time_edit_previous = float(self.exp_time_edit.text())
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QDoubleValidator(0.01, 5000.00, 2))
        self.exp_time_edit.setToolTip('Minimum is 10 µs. Maximum is 5 s.')

        # Pixel size
        pixel_size_label = QtGui.QLabel('Pixel size (nm)')
        self.pixel_size_value = QtGui.QLabel(str(initial_pixel_size))
        self.pixel_size_value.setToolTip('Pixel size at sample plane.')
        self.pixel_size = int(self.pixel_size_value.text())

        # Binning
        binning_label = QtGui.QLabel('Binning (pixels):')
        self.binning_edit = QtGui.QLineEdit('1')
        self.binning_edit.setToolTip('Restricted to squared binning. Options are 1x1, 2x2 and 4x4.')
        self.binning_previous = float(self.binning_edit.text())
        self.binning_edit.editingFinished.connect(self.binning_changed_check)
        self.binning_edit.setValidator(QtGui.QIntValidator(1, 4))
        
        # ROI entry
        starting_col_label = QtGui.QLabel('Starting col (pixel):')
        final_col_label = QtGui.QLabel('Final col (pixel):')
        starting_row_label = QtGui.QLabel('Starting row (pixel):')
        final_row_label = QtGui.QLabel('FInal row (pixel):')
        self.starting_col = QtGui.QLineEdit('1')
        self.final_col = QtGui.QLineEdit('2048')
        self.starting_row = QtGui.QLineEdit('1')
        self.final_row = QtGui.QLineEdit('2048')
        self.starting_col_previous = int(self.starting_col.text())
        self.final_col_previous = int(self.final_col.text())
        self.starting_row_previous = int(self.starting_row.text())
        self.final_row_previous = int(self.final_row.text())
        self.roi_list_previous = [self.starting_col_previous, self.starting_row_previous, \
                                  self.final_col_previous, self.final_row_previous]
        self.starting_col.editingFinished.connect(self.roi_changed_check)
        self.final_col.editingFinished.connect(self.roi_changed_check)
        self.starting_row.editingFinished.connect(self.roi_changed_check)
        self.final_row.editingFinished.connect(self.roi_changed_check)
        self.starting_col.setValidator(QtGui.QIntValidator(1, 2048))
        self.final_col.setValidator(QtGui.QIntValidator(1, 2048))
        self.starting_row.setValidator(QtGui.QIntValidator(1, 2048))
        self.final_row.setValidator(QtGui.QIntValidator(1, 2048))
        
        # Live view parameters dock
        self.liveviewWidget = QtGui.QWidget()
        layout_liveview = QtGui.QGridLayout()
        self.liveviewWidget.setLayout(layout_liveview)

        # folder and filename button
        layout_liveview.addWidget(self.working_dir_button, 0, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_label, 1, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_path, 2, 0, 1, 2)
        # place Live view button and Take a Picture button
        layout_liveview.addWidget(self.live_view_button, 5, 0, 1, 2)
        layout_liveview.addWidget(self.take_picture_button, 6, 0, 1, 2)
        layout_liveview.addWidget(self.save_picture_button, 7, 0, 1, 2)
        # Exposure time box
        layout_liveview.addWidget(exp_time_label,              8, 0)
        layout_liveview.addWidget(self.exp_time_edit,          8, 1)
        # auto level
        layout_liveview.addWidget(self.autolevel_tickbox,      9, 0)
        # pixel size
        layout_liveview.addWidget(pixel_size_label,      10, 0)
        layout_liveview.addWidget(self.pixel_size_value,        10, 1)
        # binning
        layout_liveview.addWidget(binning_label,        11, 0)
        layout_liveview.addWidget(self.binning_edit,        11, 1)
        # ROI box
        layout_liveview.addWidget(starting_col_label,      12, 0)
        layout_liveview.addWidget(self.starting_col,      12, 1)
        layout_liveview.addWidget(final_col_label,      13, 0)
        layout_liveview.addWidget(self.final_col,      13, 1)
        layout_liveview.addWidget(starting_row_label,      14, 0)
        layout_liveview.addWidget(self.starting_row,      14, 1)
        layout_liveview.addWidget(final_row_label,      15, 0)
        layout_liveview.addWidget(self.final_row,      15, 1)       

        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        viewDock = Dock('Camera', size = (200, 200)) # optical format is squared
        viewDock.addWidget(imageWidget)
        dockArea.addDock(viewDock)
        
        liveview_paramDock = Dock('Live view parameters')
        liveview_paramDock.addWidget(self.liveviewWidget)
        dockArea.addDock(liveview_paramDock, 'right', viewDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)
        return
    
    def roi_changed_check(self):
        starting_col = int(self.starting_col.text())
        final_col = int(self.final_col.text())
        starting_row = int(self.starting_row.text())
        final_row = int(self.final_row.text())
        roi_list = [starting_col, starting_row, final_col, final_row]
        if roi_list != self.roi_list_previous:
            self.roi_list_previous = roi_list
            if self.live_view_button.isChecked():
                self.roiChangedSignal.emit(True, roi_list)
            else:
                self.roiChangedSignal.emit(False, roi_list)
        return
    
    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if exposure_time_ms != self.exp_time_edit_previous:
            self.exp_time_edit_previous = exposure_time_ms
            if self.live_view_button.isChecked():
                self.exposureChangedSignal.emit(True, exposure_time_ms)
            else:
                self.exposureChangedSignal.emit(False, exposure_time_ms)
        return
            
    def binning_changed_check(self):
        binning = int(self.binning_edit.text())
        if binning != self.binning_previous:
            self.binning_previous = binning
            self.pixel_size = initial_pixel_size*binning
            self.pixel_size_value.setText(str(self.pixel_size))
            new_starting_col = self.roi_list_previous[0]
            new_starting_row = self.roi_list_previous[1]
            new_width = int((self.roi_list_previous[2] - new_starting_col + 1)/binning) - 1
            new_height = int((self.roi_list_previous[3] - new_starting_row + 1)/binning) - 1
            new_final_col = self.roi_list_previous[0] + new_width
            new_final_row = self.roi_list_previous[1] + new_height
            self.starting_col.setText(str(new_starting_col))
            self.starting_row.setText(str(new_starting_row))
            self.final_col.setText(str(new_final_col))
            self.final_row.setText(str(new_final_row))
            if self.live_view_button.isChecked():
                self.binningChangedSignal.emit(True, binning)
            else:
                self.binningChangedSignal.emit(False, binning)
            self.roi_changed_check()
        return
    
    def take_picture_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.takePictureSignal.emit(True, exposure_time_ms)
        else:
            self.takePictureSignal.emit(False, exposure_time_ms)            
        return
        
    def save_button_check(self):
        if self.save_picture_button.isChecked:
           self.saveSignal.emit()
        return
    
    def liveview_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.liveViewSignal.emit(True, exposure_time_ms)
        else:
            self.liveViewSignal.emit(False, exposure_time_ms)
        return

    def set_working_dir(self):
        self.setWorkDirSignal.emit()
        return

    def autolevel(self):
        if self.autolevel_tickbox.isChecked():
            self.autolevel_bool = True
            print('Autolevel on')
        else:
            self.autolevel_bool = False
            print('Autolevel off')
        return
    
    @pyqtSlot(np.ndarray)
    def get_image(self, image):
        self.img.setImage(image, autoLevels = self.autolevel_bool)
        return
    
    @pyqtSlot(str)
    def get_file_path(self, file_path):
        self.file_path = file_path
        self.working_dir_label.setText(self.file_path)
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
        backend.imageSignal.connect(self.get_image)
        backend.filePathSignal.connect(self.get_file_path)
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    filePathSignal = pyqtSignal(str)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.viewTimer = QtCore.QTimer()
        self.viewTimer.timeout.connect(self.update_view)   
        self.image_np = None
        self.binning = 1
        self.exposure_time_ms = 100
        self.file_path = initial_filepath
        return
    
    @pyqtSlot(bool, list)    
    def change_roi(self, livebool, roi_list):
        print('\nROI changed to', roi_list)
        if livebool:
            self.stop_liveview()
            cam.set_roi(roi_list[0], roi_list[1], roi_list[2], roi_list[3])
            self.start_liveview(self.exposure_time_ms)
        else:
            cam.set_roi(roi_list[0], roi_list[1], roi_list[2], roi_list[3])
        return
    
    @pyqtSlot(bool, float)    
    def change_exposure(self, livebool, exposure_time_ms):
        print('\nExposure time changed to', exposure_time_ms, 'ms')
        if livebool:
            self.stop_liveview()
            self.exposure_time_ms = exposure_time_ms # in ms, is float
            self.start_liveview(self.exposure_time_ms)
        else:
            self.exposure_time_ms = exposure_time_ms
            cam.set_exp_time(self.exposure_time_ms)
        return
    
    @pyqtSlot(bool, int)    
    def change_binning(self, livebool, binning):
        print('\nBinning changed to {}x{}'.format(binning, binning))
        if livebool:
            self.stop_liveview()
            self.binning = binning # is int
            cam.set_binning(self.binning)
            self.start_liveview(self.exposure_time_ms)
        else:
            self.binning = binning
            cam.set_binning(self.binning)
        return
    
    @pyqtSlot(bool, float)
    def take_picture(self, livebool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.stop_liveview()
        cam.set_exp_time(self.exposure_time_ms)
        cam.config_recorder()
        image_np, metadata = cam.get_image()
        if image_np is not None:
            self.image_np = image_np # assign to class to be able to save it later
            cam.stop()
            self.imageSignal.emit(image_np)            
        return
    
    @pyqtSlot(bool, float)
    def liveview(self, livebool, exposure_time_ms):
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.start_liveview(self.exposure_time_ms)
        else:
            self.stop_liveview()
        return
    
    def start_liveview(self, exposure_time_ms):
        print('\nLive view started at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        cam.set_exp_time(self.exposure_time_ms)
        cam.config_recorder()
        self.viewTimer.start(viewTimer_update) # ms
        return
            
    def update_view(self):
        # Image update while in Live view mode
        image_np, metadata = cam.get_image()
        self.imageSignal.emit(image_np)
        return
    
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        cam.stop()
        self.viewTimer.stop()
        return
    
    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "image_pco_test" + timestr + ".jpg"
        full_filename = os.path.join(self.file_path, filename)
        image_to_save = Image.fromarray(self.image_np)
        image_to_save.save(full_filename) 
        print('Image %s saved' % filename)
        return
      
    @pyqtSlot()    
    def set_working_folder(self):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askdirectory()
        if not file_path:
            print('No folder selected!')
        else:
            self.file_path = file_path
            self.filePathSignal.emit(self.file_path)
        return
    
    @pyqtSlot()
    def closeBackend(self):
        # laser488.close()
        # laser532.close()
        # flipperMirror.close()
        cam.stop()
        print('Stopping updater (QtTimer)...')
        self.viewTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
    
    def make_connections(self, frontend):
        frontend.roiChangedSignal.connect(self.change_roi)
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.binningChangedSignal.connect(self.change_binning)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.takePictureSignal.connect(self.take_picture)
        frontend.closeSignal.connect(self.closeBackend)
        frontend.saveSignal.connect(self.save_picture)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
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
    worker.viewTimer.moveToThread(workerThread)
    
    # connect both classes 
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()
    
    gui.show()
    app.exec()