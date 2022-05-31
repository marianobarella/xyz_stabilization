# -*- coding: utf-8 -*-
"""
Created on mon May 16, 2022

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
import thorlabs_camera_toolbox as tl_cam
from PIL import Image
from tkinter import filedialog
import tkinter as tk
import time as tm

#=====================================

# Initialize cameras

#=====================================
        
camera_constructor, \
    mono_cam, \
    mono_cam_flag, \
    color_cam, \
    color_cam_flag, \
    mono_cam_sensor_width_pixels, \
    mono_cam_sensor_height_pixels, \
    mono_cam_sensor_pixel_width_um, \
    mono_cam_sensor_pixel_height_um, \
    color_cam_sensor_width_pixels, \
    color_cam_sensor_height_pixels, \
    color_cam_sensor_pixel_width_um, \
    color_cam_sensor_pixel_height_um, \
    mono_to_color_constructor, \
    mono_to_color_processor = tl_cam.init_Thorlabs_cameras()

mono_color_string = 'mono'
camera = mono_cam
pixel_size = mono_cam_sensor_pixel_width_um
initial_filepath = 'D:\\daily_data' # save in SSD for fast and daily use
initial_filename = 'image_pco_test'

#=====================================

# GUI / Frontend definition

#=====================================
    
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    exposureChangedSignal = pyqtSignal(bool, float)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Z stabilization module"
        self.setWindowTitle(title)
            
    def setUpGUI(self):
        
        optical_format = mono_cam_sensor_width_pixels/mono_cam_sensor_height_pixels
        
        # Image
        imageWidget = pg.GraphicsLayoutWidget()
        self.vb = imageWidget.addPlot()
        self.img = pg.ImageItem()
        self.img.setOpts(axisOrder = 'row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image = self.img, levelMode = 'mono')
        self.hist.gradient.loadPreset('grey')
        self.hist.disableAutoHistogramRange()
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin = 0, yMax = 1024) # 10-bit camera
        imageWidget.addItem(self.hist, row = 0, col = 1)

        self.autolevel_tickbox = QtGui.QCheckBox('Autolevel')
        self.initial_autolevel_state = True
        self.autolevel_tickbox.setChecked(self.initial_autolevel_state)
        self.autolevel_tickbox.setText('Autolevel')
        self.autolevel_tickbox.stateChanged.connect(self.autolevel)
        self.autolevel_bool = self.initial_autolevel_state

        # Buttons and labels
        self.take_picture_button = QtGui.QPushButton('Take a picture')
        self.take_picture_button.setCheckable(False)
        self.take_picture_button.clicked.connect(self.take_picture_button_check)
        self.take_picture_button.setStyleSheet(
                "QPushButton:pressed { background-color: red; }")
        
        self.save_picture_button = QtGui.QPushButton('Save picture')
        self.save_picture_button.clicked.connect(self.save_button_check)
        self.save_picture_button.setStyleSheet(
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
        self.exp_time_edit.setValidator(QtGui.QIntValidator(1, 26843))

        # Pixel size       
        pixel_size_Label = QtGui.QLabel('Pixel size (µm):')
        self.pixel_size = QtGui.QLabel(str(pixel_size))
        self.pixel_size.setToolTip('Pixel size at sample plane.')
        
        # Working folder and filename
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory:')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        self.working_dir_path.setReadOnly(True) 
        
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
        layout_liveview.addWidget(pixel_size_Label ,      10, 0)
        layout_liveview.addWidget(self.pixel_size,        10, 1)

        # Place layouts and boxes
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)
        
        viewDock = Dock('Camera', size = (200*optical_format, 200) )
        viewDock.addWidget(imageWidget)
        # viewDock.hideTitleBar()
        dockArea.addDock(viewDock)
        
        liveview_paramDock = Dock('Live view parameters')
        liveview_paramDock.addWidget(self.liveviewWidget)
        dockArea.addDock(liveview_paramDock, 'right', viewDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)

    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if exposure_time_ms != self.exp_time_edit_previous:
            print('\nExposure time changed to', exposure_time_ms, 'ms')
            self.exp_time_edit_previous = exposure_time_ms
            if self.live_view_button.isChecked():
                self.exposureChangedSignal.emit(True, exposure_time_ms)
            else:
                self.exposureChangedSignal.emit(False, exposure_time_ms)

    def take_picture_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.takePictureSignal.emit(True, exposure_time_ms)
        else:
            self.takePictureSignal.emit(False, exposure_time_ms)            

    def save_button_check(self):
        if self.save_picture_button.isChecked:
           self.saveSignal.emit()

    def liveview_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.liveViewSignal.emit(True, exposure_time_ms)
        else:
            self.liveViewSignal.emit(False, exposure_time_ms)

    def set_working_dir(self):
        self.setWorkDirSignal.emit()

    def autolevel(self):
        if self.autolevel_tickbox.isChecked():
            self.autolevel_bool = True
            print('Autolevel on')
        else:
            self.autolevel_bool = False
            print('Autolevel off')
            
    @pyqtSlot(np.ndarray)
    def get_image(self, image):
        self.img.setImage(image, autoLevels = self.autolevel_bool)
    
    @pyqtSlot(str)
    def get_file_path(self, file_path):
        self.file_path = file_path
        self.working_dir_label.setText(self.file_path)
        
    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super(QtGui.QFrame, self).closeEvent(event, *args, **kwargs)
        # dialog box
        reply = QtGui.QMessageBox.question(self, 'Exit', 'Are you sure you want to exit the program?',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
        if reply == QtGui.QMessageBox.Yes:
            tl_cam.dispose_all(mono_cam_flag, mono_cam, color_cam_flag, color_cam, \
                        mono_to_color_processor, mono_to_color_constructor, \
                        camera_constructor)
            event.accept()
            print('Closing GUI...')
            self.close()
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
  
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.filePathSignal.connect(self.get_file_path)

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
    
    @pyqtSlot(bool, float)    
    def change_exposure(self, livebool, exposure_time_ms):
        if livebool:
            self.stop_liveview()
            self.exposure_time_ms = exposure_time_ms # in ms, is float
            self.start_liveview(self.exposure_time_ms)
        else:
            self.exposure_time_ms = exposure_time_ms
    
    @pyqtSlot(bool, float)
    def take_picture(self, livebool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.stop_liveview()
        tl_cam.set_camera_one_picture_mode(camera)
        self.frame_time = tl_cam.set_exp_time(camera, self.exposure_time_ms)
        image_np, _ = tl_cam.get_image(camera, mono_to_color_processor, mono_color_string)
        if image_np is not None:
            self.image_np = image_np # assign to class to be able to save it later
            tl_cam.stop_camera(camera)
            self.imageSignal.emit(image_np)            
        
    @pyqtSlot(bool, float)
    def liveview(self, livebool, exposure_time_ms):
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.start_liveview(self.exposure_time_ms)
        else:
            self.stop_liveview()

    def start_liveview(self, exposure_time_ms):
        print('\nLive view started at', datetime.now())
        tl_cam.set_camera_continuous_mode(camera)
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        self.frame_time = tl_cam.set_exp_time(camera, self.exposure_time_ms)
        image_np, _ = tl_cam.get_image(camera, mono_to_color_processor, mono_color_string)
        self.imageSignal.emit(image_np) 
        self.viewTimer.start(round(self.frame_time)) # ms
                
    def update_view(self):
        # Image update while in Live view mode
        image_np, _ = tl_cam.get_image(camera, mono_to_color_processor, mono_color_string)
        self.imageSignal.emit(image_np)
        
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        tl_cam.stop_camera(camera)
        self.viewTimer.stop()

    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "inspec_cam_pic_" + timestr + ".jpg"
        full_filename = os.path.join(self.file_path, filename)
        image_to_save = Image.fromarray(self.image_np)
        image_to_save.save(full_filename) 
        print('Image %s saved' % filename)
        
    @pyqtSlot()    
    def set_working_folder(self):
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askdirectory()
        if not file_path:
            print('No folder selected!')
        else:
            self.file_path = file_path
            self.filePathSignal.emit(self.file_path) # TODO Lo reciben los módulos de traza, confocal y printing

    def make_connections(self, frontend):
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.takePictureSignal.connect(self.take_picture) 
        frontend.saveSignal.connect(self.save_picture)
        frontend.setWorkDirSignal.connect(self.set_working_folder)
      
#=====================================

# Main program

#=====================================
         
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # create classes
    gui = Frontend()
    worker = Backend()
    
    # connect both classes
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    gui.show()    
    app.exec()