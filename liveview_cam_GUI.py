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
        
camera_constructor = tl_cam.load_Thorlabs_SDK_cameras()
color_cam, \
color_cam_flag, \
color_cam_sensor_width_pixels, \
color_cam_sensor_height_pixels, \
color_cam_sensor_pixel_width_um, \
color_cam_sensor_pixel_height_um, \
mono_to_color_constructor, \
mono_to_color_processor = tl_cam.init_Thorlabs_color_camera(camera_constructor)

camera = color_cam
pixel_size = color_cam_sensor_pixel_width_um
initial_filepath = 'D:\\daily_data\\inspection_cam' # save in SSD for fast and daily use
initial_filename = 'image_Thorcam'
initial_gain = 240 # int

# initial fake image
initial_image_np = 128*np.ones((1080, 1440, 3))
dummy_image_np = initial_image_np

#=====================================

# GUI / Frontend definition

#=====================================
   
class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    moveSignal = pyqtSignal(float, float, float, float)
    fixcursorSignal = pyqtSignal(float, float)
    closeSignal = pyqtSignal(bool)
    exposureChangedSignal = pyqtSignal(bool, float)
    gainChangedSignal = pyqtSignal(bool, int)
    takePictureSignal = pyqtSignal(bool, float)
    saveSignal = pyqtSignal()
    setWorkDirSignal = pyqtSignal()
    
    def __init__(self, main_app = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setGeometry(5, 30, 900, 500) # x pos, y pos, width, height
        # set the title of thw window
        title = "Live view module"
        self.setWindowTitle(title)
        self.gain = initial_gain
        self.main_app = main_app
        self.setUpGUI()
        self.get_image(initial_image_np)
        self.hist._updateView
        return
            
    def setUpGUI(self):
        max_y_cursor = color_cam_sensor_width_pixels
        max_x_cursor = color_cam_sensor_height_pixels
        optical_format = color_cam_sensor_width_pixels/color_cam_sensor_height_pixels

        # Image
        self.imageWidget = pg.GraphicsLayoutWidget()
        self.vb = self.imageWidget.addPlot()
        self.img = pg.ImageItem()
        self.vb.setAspectLocked()
        self.img.setOpts(axisOrder = 'row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image = self.img, levelMode = 'mono')
        self.hist.gradient.loadPreset('grey')
        self.hist.disableAutoHistogramRange()
        self.hist.vb.setRange(yRange=[0,256])
        self.hist.vb.setLimits(yMin = 0, yMax = 256) # 10-bit camera
        self.imageWidget.addItem(self.hist, row = 0, col = 1)

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
            "QPushButton:pressed { background-color: red; }"
            "QPushButton::checked { background-color: red; }")

        # Exposure time
        exp_time_label = QtGui.QLabel('Exposure time (ms):')
        self.exp_time_edit = QtGui.QLineEdit('100')
        self.exp_time_edit_previous = float(self.exp_time_edit.text())
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QIntValidator(1, 26843))
        
        # Gain
        gain_label = QtGui.QLabel('Gain:')
        self.gain_slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.gain_slider.setMinimum(0)
        self.gain_slider.setMaximum(480)
        self.gain_slider.setValue(initial_gain)
        self.gain_slider.setTickPosition(QtGui.QSlider.TicksBelow)
        self.gain_slider.setTickInterval(1)
        self.gain_slider.sliderReleased.connect(self.gain_changed_check)
        self.gain_value_label = QtGui.QLabel('0')
        self.gain_value_label.setText('%d' % int(self.gain_slider.value()))
        
        pixel_size_Label = QtGui.QLabel('Pixel size (µm):')
        self.pixel_size = QtGui.QLabel(str(pixel_size))
        
        # Working folder and filename
        self.working_dir_button = QtGui.QPushButton('Select directory')
        self.working_dir_button.clicked.connect(self.set_working_dir)
        self.working_dir_button.setStyleSheet(
            "QPushButton:pressed { background-color: palegreen; }")
        self.working_dir_label = QtGui.QLabel('Working directory:')
        self.filepath = initial_filepath
        self.working_dir_path = QtGui.QLineEdit(self.filepath)
        self.working_dir_path.setReadOnly(True) 
        
        # Cursor controls
        self.fix_cursor_button = QtGui.QPushButton('Lock cursor')
        self.fix_cursor_button.setCheckable(True)
        self.fix_cursor_button.clicked.connect(self.fix_cursor)
        
        # Cursor pointer
        self.point_graph_cursor = pg.ScatterPlotItem(size = 25, 
                                             symbol = 'crosshair', 
                                             pen = 'r',
                                             brush = None)
        self.point_graph_cursor.setData([int(max_y_cursor/2)], [int(max_x_cursor/2)])
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

        self.cursor_x.setText('%d' % int(self.mov_x_sl.value()))
        self.cursor_y.setText('%d' % int(self.mov_y_sl.value()))

        self.x_cursor = float(self.cursor_x.text())
        self.y_cursor = float(self.cursor_y.text())

        # Live view parameters dock
        self.liveviewWidget = QtGui.QWidget()
        layout_liveview = QtGui.QGridLayout()
        self.liveviewWidget.setLayout(layout_liveview)

        # place Live view button and Take a Picture button
        layout_liveview.addWidget(self.working_dir_button, 0, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_label, 1, 0, 1, 2)
        layout_liveview.addWidget(self.working_dir_path, 2, 0, 1, 2)
        layout_liveview.addWidget(self.live_view_button, 3, 0, 1, 2)
        layout_liveview.addWidget(self.take_picture_button, 4, 0, 1, 2)
        layout_liveview.addWidget(self.save_picture_button, 5, 0, 1, 2)
        # Exposure time box
        layout_liveview.addWidget(exp_time_label,              6, 0)
        layout_liveview.addWidget(self.exp_time_edit,          6, 1)
        # Gain box
        layout_liveview.addWidget(gain_label,              7, 0)
        layout_liveview.addWidget(self.gain_value_label,   7, 1)
        layout_liveview.addWidget(self.gain_slider,        8, 0, 1, 2)
        # auto level
        layout_liveview.addWidget(self.autolevel_tickbox,      9, 0)
        # pixel size
        layout_liveview.addWidget(pixel_size_Label,      10, 0)
        layout_liveview.addWidget(self.pixel_size,       10, 1)

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

        viewDock = Dock('Camera', size = (200*optical_format, 200))
        viewDock.addWidget(self.imageWidget)
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
        return

    def exposure_changed_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if exposure_time_ms != self.exp_time_edit_previous:
            print('\nExposure time changed to', exposure_time_ms, 'ms')
            self.exp_time_edit_previous = exposure_time_ms
            if self.live_view_button.isChecked():
                self.exposureChangedSignal.emit(True, exposure_time_ms)
            else:
                self.exposureChangedSignal.emit(False, exposure_time_ms)
        return
    
    def gain_changed_check(self):
        self.gain_value_label.setText(format(int(self.gain_slider.value())))
        self.gain = int(self.gain_value_label.text())
        if self.live_view_button.isChecked():
            self.gainChangedSignal.emit(True, self.gain)
        else:
            self.gainChangedSignal.emit(False, self.gain)
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
        return
      
    def set_mov_y(self):
        # move cursor
        self.cursor_y.setText(format(int(self.mov_y_sl.value())))
        self.y_cursor = float(self.cursor_y.text())
        pixel_y = pixel_size
        self.moveSignal.emit(self.x_cursor, self.y_cursor, 0, pixel_y)
        return
    
    def set_mov_x(self):
        # move cursor
        self.cursor_x.setText(format(int(self.mov_x_sl.value())))
        self.x_cursor = float(self.cursor_x.text())
        pixel_x = pixel_size
        self.moveSignal.emit(self.x_cursor, self.y_cursor, pixel_x, 0)
        return
    
    @pyqtSlot(list)
    def get_cursor_values(self, data_cursor):
        point_cursor_x = data_cursor[0]
        point_cursor_y = data_cursor[1]
        self.cursor_x.setText('%d' % int(point_cursor_x))
        self.cursor_y.setText('%d' % int(point_cursor_y))
        # self.cursor_x.setText(format(point_cursor_x))
        # self.cursor_y.setText(format(point_cursor_y))
        self.point_graph_cursor.setData([point_cursor_y], [point_cursor_x])
        self.point_graph_cursor._updateView()
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
    
    @pyqtSlot()
    def liveview_stopped(self):
        # uncheck liveview button
        self.live_view_button.setChecked(False)
        return
    
    @pyqtSlot()
    def liveview_started(self):
        # uncheck liveview button
        self.live_view_button.setChecked(True)
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
            self.closeSignal.emit(self.main_app)
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.datacursorSignal.connect(self.get_cursor_values)
        backend.filePathSignal.connect(self.get_file_path)
        backend.liveview_stopped_signal.connect(self.liveview_stopped)
        backend.liveview_started_signal.connect(self.liveview_started)
        return
    
#=====================================

# Controls / Backend definition

#=====================================

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    datacursorSignal = pyqtSignal(list)
    filePathSignal = pyqtSignal(str)
    stop_imaging_signal = pyqtSignal()
    liveview_stopped_signal = pyqtSignal()
    liveview_started_signal = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.referencebool = False
        self.x_pos_reference = 0
        self.y_pos_reference = 0
        self.x_cursor_reference = 0
        self.y_cursor_reference = 0
        self.viewTimer = QtCore.QTimer()
        self.viewTimer.timeout.connect(self.update_view)   
        self.image_np = initial_image_np
        self.file_path = initial_filepath
        self.counter_flag_ok = 0
        self.change_gain(False, initial_gain)
        return
    
    def go_initial_cursor(self):
        x_cursor_initial = self.total_pixel_x/2
        y_cursor_initial = self.total_pixel_y/2
        self.datacursorSignal.emit([x_cursor_initial , y_cursor_initial])
        return
    
    @pyqtSlot(float, float, float, float)    
    def cursor(self, x_cursor, y_cursor, pixel_x, pixel_y):
        x_new_cursor = x_cursor
        y_new_cursor = y_cursor
        self.datacursorSignal.emit([x_new_cursor, y_new_cursor])
        return
    
    @pyqtSlot(float, float)
    def fix_cursor_reference(self, x_cursor_reference, y_cursor_reference):
        self.x_cursor_reference = x_cursor_reference 
        self.y_cursor_reference = y_cursor_reference
        self.referencebool = True
        return
    
    @pyqtSlot(bool, float)    
    def change_exposure(self, livebool, exposure_time_ms):
        if livebool:
            self.stop_liveview()
            tm.sleep(round(self.frame_time/1000)) # wait until the last frame is acquired
            self.exposure_time_ms = exposure_time_ms # in ms, is float
            self.start_liveview(self.exposure_time_ms)
        else:
            self.exposure_time_ms = exposure_time_ms
        return
    
    @pyqtSlot(bool, int)    
    def change_gain(self, livebool, gain):
        if livebool:
            self.stop_liveview()
            tl_cam.set_gain(camera, gain)
            self.start_liveview(self.exposure_time_ms)
        else:
            tl_cam.set_gain(camera, gain)
        return
    
    @pyqtSlot(bool, float)
    def take_picture(self, livebool, exposure_time_ms):
        print('\nPicture taken at', datetime.now())
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.stop_liveview()
        # take a single picture
        # sequence is: set mode, set exposure, get image, stop
        tl_cam.set_camera_one_picture_mode(camera)
        self.frame_time = tl_cam.set_exp_time(camera, self.exposure_time_ms)
        image_np, image_pil, flag_ok = tl_cam.get_color_image(camera, mono_to_color_processor)
        tl_cam.stop_camera(camera)
        if flag_ok:
            self.image_np = image_np
        else:
            self.image_np = dummy_image_np
        # emit
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
        self.viewTimer.start(round(self.frame_time)) # ms
        self.liveview_started_signal.emit()
        return
    
    def update_view(self):
        # Image update while in Live view mode
        image_np, image_pil, flag_ok = tl_cam.get_color_image(camera, mono_to_color_processor)
        # if there's no error send image, otherwise stop livewview
        if flag_ok:
            self.image_np = image_np
        else:
            print('Displaying last taken image.')
        self.imageSignal.emit(self.image_np)
        return
    
    def stop_liveview(self):
        print('\nLive view stopped at', datetime.now())
        tl_cam.stop_camera(camera)
        self.viewTimer.stop()
        self.liveview_stopped_signal.emit()
        return
    
    @pyqtSlot()    
    def save_picture(self):
        timestr = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
        filename = "inspec_cam_pic_" + timestr + ".jpg"
        full_filename = os.path.join(self.file_path, filename)
        image_to_save = Image.fromarray(np.flipud(self.image_np))
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
    
    @pyqtSlot(bool)
    def close_backend(self, main_app = True):
        print('Dispossing camera objects...')
        tl_cam.dispose_cam(color_cam)
        tl_cam.dispose_sdk(camera_constructor)
        print('Stopping updater (QtTimer)...')
        self.viewTimer.stop()
        if main_app:
            print('Exiting thread...')
            tm.sleep(1)
            workerThread.exit()
        return
    
    def make_connections(self, frontend):
        frontend.closeSignal.connect(self.close_backend)
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.gainChangedSignal.connect(self.change_gain)
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
    worker.viewTimer.moveToThread(workerThread)
    worker.moveToThread(workerThread)

    # connect both classes 
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    # start worker in a different thread (avoids GUI freezing)
    workerThread.start()
    
    gui.show()
    app.exec()
    