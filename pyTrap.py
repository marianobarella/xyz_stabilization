# -*- coding: utf-8 -*-
"""
Created on Thu April 22, 2022

pyTrap is the control software of the 2nd gen Plasmonic Optical Tweezer setup
Here, the Graphical User Interface of pyTrap integrates all microscope modules:
    - liveview of the color Thorlabs cam
    - lasers control
    - xy and z stabilization modules
    - APD signal acquisition

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

# import os
import time as tm
# from tkinter import filedialog
# import tkinter as tk
# import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
import apd_trace_GUI
import laser_control_GUI
import liveview_cam_GUI
import piezo_stage_GUI
import thorlabs_camera_toolbox as tl_cam

# #=====================================

# # Initialize cameras

# #=====================================

# camera_constructor, \
#     mono_cam, \
#     mono_cam_flag, \
#     color_cam, \
#     color_cam_flag, \
#     mono_cam_sensor_width_pixels, \
#     mono_cam_sensor_height_pixels, \
#     mono_cam_sensor_pixel_width_um, \
#     mono_cam_sensor_pixel_height_um, \
#     color_cam_sensor_width_pixels, \
#     color_cam_sensor_height_pixels, \
#     color_cam_sensor_pixel_width_um, \
#     color_cam_sensor_pixel_height_um, \
#     mono_to_color_constructor, \
#     mono_to_color_processor = liveview_cam_GUI.init_Thorlabs_cameras()

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    # selectDirSignal = pyqtSignal()
    # createDirSignal = pyqtSignal()
    # openDirSignal = pyqtSignal()
    # loadpositionSignal = pyqtSignal()
    closeSignal = pyqtSignal()

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setWindowTitle('pyTrap')

        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setGeometry(30, 30, 200, 200)

    #     # Create de file location
    #     localDirAction = QtGui.QAction('&Select Dir (Ctrl+A)', self)
    #     localDirAction.setStatusTip('Select the work folder')
    #     localDirAction.triggered.connect(self.get_selectDir)

    #     # Create de create daily directory
    #     dailyAction = QtGui.QAction('&Create daily Dir (Ctrl+S)', self)
    #     dailyAction.setStatusTip('Create the work folder')
    #     dailyAction.triggered.connect(self.get_create_daily_directory)
        
    #     # Open directory
    #     openAction = QtGui.QAction('&Open Dir (Ctrl+D)', self)
    #     openAction.setStatusTip('Open document')
    #     openAction.triggered.connect(self.get_openDir)
        
    #     # Load las position
    #     load_position_Action = QtGui.QAction('&Load Last position', self)
    #     load_position_Action.setStatusTip('Load last position when PyPrinting closed.')
    #     load_position_Action.triggered.connect(self.load_last_position)
        
    #     QtGui.QShortcut(
    #         QtGui.QKeySequence('Ctrl+A'), self, self.get_selectDir)
       
    #     QtGui.QShortcut(
    #         QtGui.QKeySequence('Ctrl+S'), self, self.get_create_daily_directory)
         
    #     QtGui.QShortcut(
    #         QtGui.QKeySequence('Ctrl+D'), self, self.get_openDir)

    # # Create de create daily directory action
    #     save_docks_Action = QtGui.QAction(QtGui.QIcon('algo.png'), '&Save Docks', self)
    #     save_docks_Action.setStatusTip('Saves the Actual Docks configuration')
    #     save_docks_Action.triggered.connect(self.save_docks)

    # # Create de create daily directory action
    #     load_docks_Action = QtGui.QAction(QtGui.QIcon('algo.png'), '&Restore Docks', self)
    #     load_docks_Action.setStatusTip('Load a previous Docks configuration')
    #     load_docks_Action.triggered.connect(self.load_docks)
        
    # # Open Tools: Cursor
    #     tools_cursor_Action = QtGui.QAction('&Cursor', self)
    #     tools_cursor_Action.triggered.connect(self.tools_cursor)
        
    # # Measurment Printing
    #     printing_Action = QtGui.QAction('&Do Printing', self)
    #     printing_Action.triggered.connect(self.measurement_printing)
        
    # # Measurment Dimers
    #     dimers_Action = QtGui.QAction('&Do Dimers', self)
    #     dimers_Action.triggered.connect(self.measurement_dimers)

    #     # Actions in menubar
    
    #     menubar = self.menuBar()

    #     fileMenu = menubar.addMenu('&Files Direction')
    #     fileMenu.addAction(localDirAction)
    #     fileMenu.addAction(openAction)
    #     fileMenu.addAction(dailyAction)
    #     fileMenu.addAction(load_position_Action)
        
    #     fileMenu2 = menubar.addMenu('&Tools')
    #     fileMenu2.addAction(tools_cursor_Action)

    #     fileMenu3 = menubar.addMenu('&Measurements')
    #     fileMenu3.addAction(printing_Action)
    #     fileMenu3.addAction(dimers_Action)
        
    #     fileMenu4 = menubar.addMenu('&Docks config')
    #     fileMenu4.addAction(save_docks_Action)
    #     fileMenu4.addAction(load_docks_Action)
        
        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        ## Add APD trace GUI module
        apdDock = Dock('APD signal')
        self.apdWidget = apd_trace_GUI.Frontend()
        apdDock.addWidget(self.apdWidget)
        self.dockArea.addDock(apdDock)
        
        ## Add Liveview module
        liveviewDock = Dock('Liveview')
        self.liveviewWidget = liveview_cam_GUI.Frontend()
        liveviewDock.addWidget(self.liveviewWidget)
        self.dockArea.addDock(liveviewDock, 'right', apdDock)
        
        ## Add Lasers GUI module
        lasersDock = Dock('Lasers')
        self.lasersWidget = laser_control_GUI.Frontend()
        lasersDock.addWidget(self.lasersWidget)
        self.dockArea.addDock(lasersDock , 'bottom', liveviewDock)

        ## Add Piezo stage GUI module
        piezoDock = Dock('Piezo stage')
        self.piezoWidget = piezo_stage_GUI.Frontend()
        piezoDock.addWidget(self.piezoWidget)
        self.dockArea.addDock(piezoDock , 'right', lasersDock)
              
    # def get_openDir(self):
    #     self.openDirSignal.emit()
        
    # def get_selectDir(self):
    #     self.selectDirSignal.emit()
        
    # def get_create_daily_directory(self):
    #     self.createDirSignal.emit()
        
    # def load_last_position(self):
    #     self.loadpositionSignal.emit()

    # def save_docks(self):  # Funciones para acomodar los Docks
    #     self.state = self.dockArea.saveState()

    # def load_docks(self):
    #     self.dockArea.restoreState(self.state)
        
    # def measurement_printing(self):
        
    #     self.printingWidget.show()
        
    # def measurement_dimers(self):
        
    #     self.dimersWidget.show()
        
    # def tools_cursor(self):

    #     self.cursorWidget.show()
         
    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super().closeEvent(event, *args, **kwargs)
        # dialog box
        reply = QtGui.QMessageBox.question(self, 'Exit', 'Are you sure you want to exit the program?',
                                           QtGui.QMessageBox.No |
                                           QtGui.QMessageBox.Yes)
        if reply == QtGui.QMessageBox.Yes:
            tl_cam.dispose_all(liveview_cam_GUI.mono_cam_flag, \
                                liveview_cam_GUI.mono_cam, \
                                liveview_cam_GUI.color_cam_flag, \
                                liveview_cam_GUI.color_cam, \
                                liveview_cam_GUI.mono_to_color_processor, \
                                liveview_cam_GUI.mono_to_color_constructor, \
                                liveview_cam_GUI.camera_constructor)
            event.accept()
            self.closeSignal.emit()
            tm.sleep(1)
            print('Closing GUI...')
            self.close()
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    def make_modules_connections(self, backend):    
        # connect Frontend modules with their respectives Backend modules
        backend.apdWorker.make_connections(self.apdWidget)
        backend.lasersWorker.make_connections(self.lasersWidget)
        backend.livewviewWorker.make_connections(self.liveviewWidget)
        backend.piezoWorker.make_connections(self.piezoWidget)
        return
            
#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):
    
    # fileSignal = pyqtSignal(str)
    # close_all_instrument_Signal = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage = piezo_stage_GUI.piezo_stage     
        self.livewviewWorker = liveview_cam_GUI.Backend()
        self.lasersWorker = laser_control_GUI.Backend()
        self.apdWorker = apd_trace_GUI.Backend()
        self.piezoWorker = piezo_stage_GUI.Backend(self.piezo_stage)
        # self.confocalWorker = Confocal.Backend(pi_device, task_nidaqmx)
        # self.printingWorker = Printing.Backend(pi_device, task_nidaqmx)
        # self.dimersWorker = Dimers.Backend(pi_device, task_nidaqmx)
        # self.cursorWorker = Cursor.Backend(pi_device)
        return
    
    # @pyqtSlot()    
    # def selectDir(self):
    #     root = tk.Tk()
    #     root.withdraw()

    #     file_path = filedialog.askdirectory()
    #     if not file_path:
    #         print("Don't choose a folder...")
    #     else:
    #         self.file_path = file_path
    #         self.fileSignal.emit(self.file_path)   #Lo reciben los módulos de traza, confocal y printing
             
    # @pyqtSlot()  
    # def openDir(self):
    #     os.startfile(self.file_path)
    #     print('Open: ', self.file_path)
        
    # @pyqtSlot()      
    # def create_daily_directory(self):
    #     root = tk.Tk()
    #     root.withdraw()

    #     file_path = filedialog.askdirectory()
    #     if not file_path:
    #         print("If you don't choose a folder... ==> Doesn't make a folder")
    #     else:
    #         timestr = time.strftime("%Y-%m-%d")  # -%H%M%S")

    #         newpath = file_path + "/" + timestr
    #         if not os.path.exists(newpath):
    #             os.makedirs(newpath)
    #             print("Folder ok!")
    #         else:
    #             print("Folder already exixts ok.")

    #         self.file_path = newpath 
    #         self.fileSignal.emit(self.file_path) 
            
            
    # @pyqtSlot()             
    # def load_last_position(self): 
        
    #     filepath = "C:/Users/CibionPC/Desktop/PyPrinting"
    #     name = str(filepath  + "/" + "Last_position.txt")
     
    #     last_position = np.loadtxt(name)
    #     print(last_position)
        
    #     targets = list(last_position)
                
    #     self.pi_device.MOV(['A', 'B', 'C'], targets)
    #     time.sleep(0.01)
     
            
    @pyqtSlot()
    def close_all_backends(self):
        print('Shutting down piezo stage...')
        self.piezo_stage.shutdown()
        laser_control_GUI.laser488.close()
        laser_control_GUI.laser532.close()
        laser_control_GUI.flipperMirror.close()
        print('Laser\'s shutters closed.') 
        self.apdWorker.APD_task.close()
        print('Task closed.') 
        print('Stopping timers...')
        self.lasersWorker.updateTimer.stop()
        self.apdWorker.updateTimer.stop()
        self.piezoWorker.updateTimer.stop()
        print('Exiting threads...')
        lasersThread.exit()
        livewviewThread.exit()
        apdThread.exit()
        return
    
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.apdWidget.make_connections(self.apdWorker)
        frontend.lasersWidget.make_connections(self.lasersWorker)
        frontend.liveviewWidget.make_connections(self.livewviewWorker)
        frontend.piezoWidget.make_connections(self.piezoWorker)
        return
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])

    # create both classes
    gui = Frontend()
    worker = Backend()
       
    ###################################
    # move modules and their timers to different threads
    
    # for lasers
    lasersThread = QtCore.QThread()
    worker.lasersWorker.moveToThread(lasersThread)
    worker.lasersWorker.updateTimer.moveToThread(lasersThread)  
    
    # for liveview camera
    livewviewThread = QtCore.QThread()
    worker.livewviewWorker.moveToThread(livewviewThread)
    worker.livewviewWorker.viewTimer.moveToThread(livewviewThread)
    
    # for APD signal displaying
    apdThread = QtCore.QThread()
    worker.apdWorker.moveToThread(apdThread)
    worker.apdWorker.updateTimer.moveToThread(apdThread)

    # for piezo stage position update
    piezoThread = QtCore.QThread()
    worker.piezoWorker.moveToThread(piezoThread)
    worker.piezoWorker.updateTimer.moveToThread(piezoThread)

    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start threads
    lasersThread.start()
    livewviewThread.start()
    apdThread.start()
    piezoThread.start()
    
    gui.show()
    app.exec()
    