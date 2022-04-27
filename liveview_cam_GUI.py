# -*- coding: utf-8 -*-
"""
Created on Tue March 1, 2022

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

def init_Thorlabs_cameras():
    # initialize Thorlabs cameras
    # get Thorlabs camera parameters
    camera_constructor = tl_cam.init_thorlabs_cameras()
    mono_cam, mono_cam_flag, color_cam, color_cam_flag = tl_cam.list_cameras(camera_constructor)
    if mono_cam_flag:
        mono_cam_sensor_width_pixels, mono_cam_sensor_height_pixels, \
        mono_cam_sensor_pixel_width_um, mono_cam_sensor_pixel_height_um = tl_cam.get_camera_param(mono_cam)
        mono_to_color_constructor = None
        mono_to_color_processor = None
    if color_cam_flag:
        color_cam_sensor_width_pixels, color_cam_sensor_height_pixels, \
        color_cam_sensor_pixel_width_um, color_cam_sensor_pixel_height_um = tl_cam.get_camera_param(color_cam)
        mono_to_color_constructor, mono_to_color_processor = tl_cam.init_thorlabs_color_cameras(color_cam)
    return camera_constructor, \
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
        mono_to_color_processor
        
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
    mono_to_color_processor = init_Thorlabs_cameras()

mono_color_string = 'color'
camera = color_cam
pixel_size = color_cam_sensor_pixel_width_um

#=====================================

# GUI / Frontend definition

#=====================================
   
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    moveSignal = pyqtSignal(float, float, float, float)
    fixcursorSignal = pyqtSignal(float, float)
    # closeSignal = pyqtSignal()
    exposureChangedSignal = pyqtSignal(bool, float)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Live view module"
        self.setWindowTitle(title)
            
    def setUpGUI(self):
        max_y_cursor = color_cam_sensor_width_pixels
        max_x_cursor = color_cam_sensor_height_pixels
        optical_format = color_cam_sensor_width_pixels/color_cam_sensor_height_pixels

        # Image
        imageWidget = pg.GraphicsLayoutWidget()
        self.vb = imageWidget.addPlot()
        self.img = pg.ImageItem()
        self.img.setOpts(axisOrder = 'row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image = self.img, levelMode = 'rgba')
        self.hist.gradient.loadPreset('grey')
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin = 0, yMax = 1024) # 10-bit camera
        imageWidget.addItem(self.hist, row = 0, col = 1)
        # TODO: if performance is an issue, try scaleToImage

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
        self.exp_time_edit.setValidator(QtGui.QIntValidator(1, 26843))
        
        pixel_size_Label = QtGui.QLabel('Pixel size (µm)')
        self.pixel_size = QtGui.QLabel(str(pixel_size))
        
        # Working folder
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton { background-color: lightgray; }"
            "QPushButton:pressed { background-color: palegreen; }")
        self.file_path = ''
        self.working_dir_label = QtGui.QLineEdit(self.file_path)
        self.working_dir_label.setReadOnly(True)

        # Cursor controls
        self.fix_cursor_button = QtGui.QPushButton('Fix cursor')
        self.fix_cursor_button.setCheckable(True)
        self.fix_cursor_button.clicked.connect(self.fix_cursor)
        
        # Cursor pointer
        self.point_graph_cursor = pg.ScatterPlotItem(size = 25, 
                                             symbol = 'crosshair', 
                                             pen = 'k',
                                             brush = None)
        self.point_graph_cursor.setData([0], [0])
        self.vb.addItem(self.point_graph_cursor)

        self.mov_x_sl = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.mov_x_sl.setMinimum(1)
        self.mov_x_sl.setMaximum(max_x_cursor)
        self.mov_x_sl.setValue(int(max_x_cursor/2))
        self.mov_x_sl.setTickPosition(QtGui.QSlider.TicksBelow)
        self.mov_x_sl.setTickInterval(1)
        self.mov_x_sl.valueChanged.connect(self.set_mov_x)

        self.mov_y_sl = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.mov_y_sl.setMinimum(1)
        self.mov_y_sl.setMaximum(max_y_cursor)
        self.mov_y_sl.setValue(int(max_y_cursor/2))
        self.mov_y_sl.setTickPosition(QtGui.QSlider.TicksBelow)
        self.mov_y_sl.setTickInterval(1)
        self.mov_y_sl.valueChanged.connect(self.set_mov_y)

        cursor_x_label = QtGui.QLabel('Cursor X')
        self.cursor_x = QtGui.QLabel('NaN')
        cursor_y_label = QtGui.QLabel('Cursor Y')
        self.cursor_y = QtGui.QLabel('NaN')

        self.cursor_x.setText(format(int(self.mov_x_sl.value())))
        self.cursor_y.setText(format(int(self.mov_y_sl.value())))

        self.x_cursor = float(self.cursor_x.text())
        self.y_cursor = float(self.cursor_y.text())

        # Live view parameters dock
        self.liveviewWidget = QtGui.QWidget()
        layout_liveview = QtGui.QGridLayout()
        self.liveviewWidget.setLayout(layout_liveview) 

        # place Live view button and Take a Picture button
        layout_liveview.addWidget(self.working_dir_button, 0, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_label, 1, 0, 1, 2)
        layout_liveview.addWidget(self.live_view_button, 2, 0)
        layout_liveview.addWidget(self.take_picture_button, 2, 1)
        layout_liveview.addWidget(self.save_picture_button, 3, 1)
        # Exposure time box
        layout_liveview.addWidget(exp_time_label,              4, 0)
        layout_liveview.addWidget(self.exp_time_edit,          4, 1)
        # auto level
        layout_liveview.addWidget(self.autolevel_tickbox,      5, 0)
        # layout_liveview.addWidget(self.pixel_size,        5, 1)
        # pixel size
        layout_liveview.addWidget(pixel_size_Label ,      6, 0)
        layout_liveview.addWidget(self.pixel_size,        6, 1)

        # Cursor dock
        self.cursorWidget = QtGui.QWidget()
        layout_cursor = QtGui.QGridLayout()
        self.cursorWidget.setLayout(layout_cursor) 

        # place Fix reference button
        layout_cursor.addWidget(self.fix_cursor_button, 0, 0)
        # place sliders
        # Cursor X
        layout_cursor.addWidget(cursor_x_label, 1, 0)
        layout_cursor.addWidget(self.cursor_x,  2, 0)
        layout_cursor.addWidget(self.mov_x_sl, 2, 1)
        # Cursor Y
        layout_cursor.addWidget(cursor_y_label, 3, 0)
        layout_cursor.addWidget(self.cursor_y,  4, 0)
        layout_cursor.addWidget(self.mov_y_sl, 4, 1)             

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

        cursorDock = Dock('Cursor')
        cursorDock.addWidget(self.cursorWidget)
        dockArea.addDock(cursorDock, 'bottom', liveview_paramDock)
        
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

    def fix_cursor(self):
        if self.fix_cursor_button.isChecked():
           x_cursor_reference = float(self.cursor_x.text())
           y_cursor_reference = float(self.cursor_y.text())
           self.fixcursorSignal.emit(x_cursor_reference, y_cursor_reference)
           self.mov_x_sl.setEnabled(False)
           self.mov_y_sl.setEnabled(False)
        else:
           self.mov_x_sl.setEnabled(True)
           self.mov_y_sl.setEnabled(True)

    def set_mov_y(self):
        # move cursor
        self.cursor_y.setText(format(int(self.mov_y_sl.value())))
        self.y_cursor = float(self.cursor_y.text())
        pixel_y = pixel_size
        self.moveSignal.emit(self.x_cursor, self.y_cursor, 0, pixel_y)

    def set_mov_x(self):
        # move cursor
        self.cursor_x.setText(format(int(self.mov_x_sl.value())))
        self.x_cursor = float(self.cursor_x.text())
        pixel_x = pixel_size
        self.moveSignal.emit(self.x_cursor, self.y_cursor, pixel_x, 0)
    
    @pyqtSlot(list)
    def get_cursor_values(self, data_cursor):
        point_cursor_x = data_cursor[0]
        point_cursor_y = data_cursor[1]
        self.cursor_x.setText(format(point_cursor_x))
        self.cursor_y.setText(format(point_cursor_y))
        self.point_graph_cursor.setData([point_cursor_y], [point_cursor_x])
        self.point_graph_cursor._updateView()

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
  
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.datacursorSignal.connect(self.get_cursor_values)
        backend.filePathSignal.connect(self.get_file_path)

#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    datacursorSignal = pyqtSignal(list)
    filePathSignal = pyqtSignal(str)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.referencebool = False
        self.x_pos_reference = 0
        self.y_pos_reference = 0
        self.x_cursor_reference = 0
        self.y_cursor_reference = 0
        self.viewTimer = QtCore.QTimer()
        self.viewTimer.timeout.connect(self.update_view)   
        self.image_np = None

    def go_initial_cursor(self):
        x_cursor_initial = self.total_pixel_x/2
        y_cursor_initial = self.total_pixel_y/2
        self.datacursorSignal.emit([x_cursor_initial , y_cursor_initial])

    @pyqtSlot(float, float, float, float)    
    def cursor(self, x_cursor, y_cursor, pixel_x, pixel_y):
        x_new_cursor = x_cursor
        y_new_cursor = y_cursor
        self.datacursorSignal.emit([x_new_cursor, y_new_cursor])

    @pyqtSlot(float, float)
    def fix_cursor_reference(self, x_cursor_reference, y_cursor_reference):
        self.x_cursor_reference = x_cursor_reference 
        self.y_cursor_reference = y_cursor_reference
        self.referencebool = True
    
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
        tl_cam.set_camera_continuous_mode(camera)
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        self.frame_time = tl_cam.set_exp_time(camera, self.exposure_time_ms)
        image_np, _ = tl_cam.get_image(camera, mono_to_color_processor, mono_color_string)
        self.imageSignal.emit(image_np) 
        self.viewTimer.start(round(self.frame_time)) # ms
        return
            
    def update_view(self):
        # Image update while in Live view mode
        image_np, _ = tl_cam.get_image(camera, mono_to_color_processor, mono_color_string)
        self.imageSignal.emit(image_np)
        return
    
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        tl_cam.stop_camera(camera)
        self.viewTimer.stop()
        return
    
    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "inspec_cam_pic_" + timestr + ".jpg"
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
    
    def make_connections(self, frontend):
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.takePictureSignal.connect(self.take_picture) 
        frontend.moveSignal.connect(self.cursor)
        frontend.fixcursorSignal.connect(self.fix_cursor_reference)
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