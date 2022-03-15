# -*- coding: utf-8 -*-
"""
Created on Tue March 1, 2022

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import numpy as np
from datetime import datetime
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from pyqtgraph.dockarea import Dock, DockArea
import thorlabs_camera_toolbox as tl_cam

# initialize Thorlabs cameras
# get Thorlabs camera parameters
camera_constructor = tl_cam.init_thorlabs_cameras()
mono_cam, mono_cam_flag, color_cam, color_cam_flag = tl_cam.list_cameras(camera_constructor)
if mono_cam_flag:
    mono_cam_sensor_width_pixels, mono_cam_sensor_height_pixels, \
    mono_cam_sensor_pixel_width_um, mono_cam_sensor_pixel_height_um = tl_cam.get_camera_param(mono_cam)
    mono_to_color_processor = None
    mono_to_color_constructor = None
if color_cam_flag:
    color_cam_sensor_width_pixels, color_cam_sensor_height_pixels, \
    color_cam_sensor_pixel_width_um, color_cam_sensor_pixel_height_um = tl_cam.get_camera_param(color_cam)
    mono_to_color_constructor, mono_to_color_processor = tl_cam.init_thorlabs_color_cameras(color_cam)
    
pixel_size = mono_cam_sensor_pixel_width_um
if mono_cam_sensor_pixel_width_um != mono_cam_sensor_pixel_height_um:
    print('Pixel is not a square. Width and height are different. Pixel size set to pixel width.')
    pixel_size = mono_cam_sensor_pixel_width_um

class Frontend(QtGui.QFrame):

    liveViewSignal = pyqtSignal(bool, float)
    moveSignal = pyqtSignal(float, float, float, float)
    fixcursorSignal = pyqtSignal(float, float)
    closeSignal = pyqtSignal()
    exposureChangedSignal = pyqtSignal(bool, float)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setUpGUI()
        # set the title of thw window
        title = "Z stabilization"
        self.setWindowTitle(title)
            
    def setUpGUI(self):
        
        max_y_cursor = mono_cam_sensor_width_pixels
        max_x_cursor = mono_cam_sensor_height_pixels
        optical_format = mono_cam_sensor_width_pixels/mono_cam_sensor_height_pixels

        # Image
        imageWidget = pg.GraphicsLayoutWidget()
        self.vb = imageWidget.addPlot()
        self.img = pg.ImageItem()
        self.img.setOpts(axisOrder='row-major')
        self.vb.addItem(self.img)
        self.hist = pg.HistogramLUTItem(image=self.img)
        self.hist.gradient.loadPreset('grey')
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey'
        self.hist.vb.setLimits(yMin=0, yMax=1024)
        # for tick in self.hist.gradient.ticks:
        #     tick.hide()
        imageWidget.addItem(self.hist, row=0, col=1)

        self.autolevel_tickbox = QtGui.QCheckBox('Autolevel')
        self.initial_autolevel_state = True
        self.autolevel_tickbox.setChecked(self.initial_autolevel_state)
        self.autolevel_tickbox.setText('Autolevel')
        self.autolevel_tickbox.stateChanged.connect(self.autolevel)
        self.autolevel_bool = self.initial_autolevel_state
        
        # Buttons and labels
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
        self.exp_time_edit.editingFinished.connect(self.exposure_changed_check)
        self.exp_time_edit.setValidator(QtGui.QIntValidator(1, 26843))
        
        pixel_size_Label = QtGui.QLabel('Pixel size (µm)')
        self.pixel_size = QtGui.QLabel(str(pixel_size))

        # Cursor controls
        self.fix_cursor_button = QtGui.QPushButton('Fix cursor')
        self.fix_cursor_button.setCheckable(True)
        self.fix_cursor_button.clicked.connect(self.fix_cursor)
        
        # ROI creation
        self.ROI_button = QtGui.QPushButton('ROI square')
        self.ROI_button.setCheckable(True)
        self.ROI_button.clicked.connect(self.create_ROI)
        self.ROI_button.setStyleSheet(
                "QPushButton:pressed { background-color: blue; }")

        # Live view parameters dock
        self.liveviewWidget = QtGui.QWidget()
        layout_liveview = QtGui.QGridLayout()
        self.liveviewWidget.setLayout(layout_liveview) 

        # place Live view button
        layout_liveview.addWidget(self.live_view_button, 0, 0)
        # Exposure time box
        layout_liveview.addWidget(exp_time_label,              1, 0)
        layout_liveview.addWidget(self.exp_time_edit,          1, 1)
        # auto level
        layout_liveview.addWidget(self.autolevel_tickbox,      2, 0)
        # layout_liveview.addWidget(self.pixel_size,        3, 1)
        # pixel size
        layout_liveview.addWidget(pixel_size_Label ,      3, 0)
        layout_liveview.addWidget(self.pixel_size,        3, 1)

        # Cursor dock
        self.cursorWidget = QtGui.QWidget()
        layout_cursor = QtGui.QGridLayout()
        self.cursorWidget.setLayout(layout_cursor) 

        # # place Fix reference button
        # layout_cursor.addWidget(self.fix_cursor_button, 0, 0)
        # # place sliders
        # # Cursor X
        # layout_cursor.addWidget(cursor_x_label, 1, 0)
        # layout_cursor.addWidget(self.cursor_x,  2, 0)
        # layout_cursor.addWidget(self.mov_x_sl, 2, 1)
        # # Cursor Y
        # layout_cursor.addWidget(cursor_y_label, 3, 0)
        # layout_cursor.addWidget(self.cursor_y,  4, 0)
        # layout_cursor.addWidget(self.mov_y_sl, 4, 1)             

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
        print('\nExposure time changed to', exposure_time_ms, 'ms')
        if self.live_view_button.isChecked():
            self.exposureChangedSignal.emit(True, exposure_time_ms)
        else:
            self.exposureChangedSignal.emit(False, exposure_time_ms)
          
    def liveview_button_check(self):
        exposure_time_ms = float(self.exp_time_edit.text()) # in ms
        if self.live_view_button.isChecked():
            self.liveViewSignal.emit(True, exposure_time_ms)
        else:
            self.liveViewSignal.emit(False, exposure_time_ms)

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
        self.vb.addItem(self.point_graph_cursor)

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
            # self.closeSignal.emit()
            event.accept()
            self.close()          
            print('\nClosing GUI...')
        else:
            event.ignore()
            print('\nBack in business...')    
  
    def make_connections(self, backend):
        backend.imageSignal.connect(self.get_image)
        backend.datacursorSignal.connect(self.get_cursor_values)

class Backend(QtCore.QObject):

    imageSignal = pyqtSignal(np.ndarray)
    datacursorSignal = pyqtSignal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.referencebool = False
        self.x_pos_reference = 0
        self.y_pos_reference = 0
        self.x_cursor_reference = 0
        self.y_cursor_reference = 0
        self.viewTimer = QtCore.QTimer()
        self.viewTimer.timeout.connect(self.update_view)   

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
            self.exposure_time_ms = exposure_time_ms
            self.start_liveview(self.exposure_time_ms)
        else:
            self.exposure_time_ms = exposure_time_ms
  
    @pyqtSlot(bool, float)
    def liveview(self, livebool, exposure_time_ms):
        self.exposure_time_ms = exposure_time_ms # in ms, is float
        if livebool:
            self.start_liveview(self.exposure_time_ms)
        else:
            self.stop_liveview()

    def start_liveview(self, exposure_time_ms):
        print('\nLive view started at', datetime.now())
        tl_cam.set_camera_continuous_mode(mono_cam)
        self.frame_time = tl_cam.set_exp_time(mono_cam, exposure_time_ms)
        mono_image_np, _ = tl_cam.get_mono_image(mono_cam)
        self.imageSignal.emit(mono_image_np) 
        # update_time = 1.5*self.exposure_time*10**3
        self.viewTimer.start(round(self.frame_time)) # ms, DON'T USE time.sleep() inside the update()
        
    def update_view(self):
        # Image update while in Live view mode
        mono_image_np, _ = tl_cam.get_mono_image(mono_cam)
        self.imageSignal.emit(mono_image_np)
        
    def stop_liveview(self):
        tl_cam.stop_camera_continuous_mode(mono_cam)
        self.viewTimer.stop()
        print('Live view stopped at', datetime.now())

    def make_connections(self, frontend):
        frontend.exposureChangedSignal.connect(self.change_exposure)
        frontend.liveViewSignal.connect(self.liveview) 
        frontend.moveSignal.connect(self.cursor)
        frontend.fixcursorSignal.connect(self.fix_cursor_reference)

               
if __name__ == '__main__':

    app = QtGui.QApplication([])

    gui = Frontend()
    worker = Backend()
    
    worker.make_connections(gui)
    gui.make_connections(worker)
    
    gui.show()
    
    
    