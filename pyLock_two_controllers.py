# -*- coding: utf-8 -*-
"""
Created on Thu May 31, 2023
Modified on Wed Jan 22, 2025

pyLock is a control software of the 2nd gen Plasmonic Optical Tweezer setup that
allows the user to stabilize the system in xyz using a closed-loop system made 
of the piezostage and two cameras
Here, the Graphical User Interface of pyLock integrates the following modules:
    - piezostage control
    - xy stabilization
    - z stabilization 

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""

import time as tm
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
# import numpy as np
import piezo_stage_GUI_two_controllers
import z_stabilization_GUI_v2
import xy_stabilization_GUI_v2

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    closeSignal = pyqtSignal(bool)
    
    def __init__(self, piezo_frontend, main_app = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setWindowTitle('pyLock')
        self.setGeometry(5, 30, 1900, 600) # x pos, y pos, width, height
        self.main_app = main_app
        # import frontend modules
        # piezo widget (frontend) must be imported in the main
        # hide piezo GUI on the xy and z widgets
        self.piezoWidget = piezo_frontend
        self.xyWidget = xy_stabilization_GUI_v2.Frontend(piezo_frontend, \
                                                    show_piezo_subGUI = False, \
                                                    main_app = False, \
                                                    connect_to_piezo_module = False)
        self.zWidget = z_stabilization_GUI_v2.Frontend(piezo_frontend, \
                                                       show_piezo_subGUI = False, \
                                                       main_app = False, \
                                                       connect_to_piezo_module = False)
        self.setUpGUI()
        return
    
    def setUpGUI(self):
       
        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        ## Add piezo module
        piezoDock = Dock('Piezostage control', size=(1,10))
        piezoDock.addWidget(self.piezoWidget)
        self.dockArea.addDock(piezoDock)
        
        ## Add xy stabilization module
        xyDock = Dock('xy stabilization')
        xyDock.addWidget(self.xyWidget)
        self.dockArea.addDock(xyDock, 'bottom', piezoDock)
        
        ## Add z stabilization module
        zDock = Dock('z stabilization')
        zDock.addWidget(self.zWidget)
        self.dockArea.addDock(zDock, 'left', xyDock)
        return
           
    # re-define the closeEvent to execute an specific command
    def closeEvent(self, event, *args, **kwargs):
        super().closeEvent(event, *args, **kwargs)
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
    
    def make_modules_connections(self, backend):    
        # connect Frontend modules with their respectives Backend modules
        backend.piezoWorker.make_connections(self.piezoWidget)
        backend.xyWorker.make_connections(self.xyWidget)
        backend.zWorker.make_connections(self.zWidget)
        return
            
#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):
    
    def __init__(self, piezo_stage_xy, piezo_stage_z, piezo_backend, \
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage_xy = piezo_stage_xy
        self.piezo_stage_z = piezo_stage_z
        # there's only one backend in the piezo_stage_GUI_two_controllers
        self.piezoWorker = piezo_backend
        self.xyWorker = xy_stabilization_GUI_v2.Backend(piezo_stage_xy, \
                                                     piezo_backend, \
                                                     connect_to_piezo_module = False)
        self.zWorker = z_stabilization_GUI_v2.Backend(piezo_stage_z, \
                                                   piezo_backend, \
                                                   connect_to_piezo_module = False)
        return
    
    @pyqtSlot(bool)
    def close_all_backends(self, main_app = True):
        print('Closing all backends...')
        self.piezoWorker.close_backend(main_app = False)
        self.xyWorker.close_backend(main_app = False)
        self.zWorker.close_backend(main_app = False)
        # print('Stopping updater (QtTimer)...')
        # self.scanTimer.stop()
        if main_app:
            print('Exiting thread...')
            tm.sleep(1)
            workerThread.exit()
        return
    
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.piezoWidget.make_connections(self.piezoWorker)
        frontend.xyWidget.make_connections(self.xyWorker)
        frontend.zWidget.make_connections(self.zWorker)
        return
    
#=====================================

#  Main program

#=====================================
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])
    
    # init stage
    piezo_xy = piezo_stage_GUI_two_controllers.piezo_stage_xy
    piezo_z = piezo_stage_GUI_two_controllers.piezo_stage_z
    piezo_frontend = piezo_stage_GUI_two_controllers.Frontend(main_app = False)
    piezo_backend = piezo_stage_GUI_two_controllers.Backend(piezo_xy, piezo_z)
    
    # create both classes
    gui = Frontend(piezo_frontend)
    worker = Backend(piezo_xy, piezo_z, piezo_backend)
       
    ###################################
    # move backend to another thread
    workerThread = QtCore.QThread()
    # move the timer of the piezo and its main worker
    worker.piezoWorker.updateTimer.moveToThread(workerThread)
    worker.piezoWorker.moveToThread(workerThread)
    # move the timers of the xy and its main worker
    worker.xyWorker.viewTimer.moveToThread(workerThread)
    worker.xyWorker.trackingTimer.moveToThread(workerThread)
    worker.xyWorker.tempTimer.moveToThread(workerThread)
    worker.xyWorker.moveToThread(workerThread)
    # move the timers of the z and its main worker
    worker.zWorker.trackingTimer.moveToThread(workerThread)
    worker.zWorker.viewTimer.moveToThread(workerThread)
    worker.zWorker.moveToThread(workerThread)
    # move the main worker
    worker.moveToThread(workerThread)

    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start thread
    workerThread.start()
    
    gui.show()
    app.exec()
    
    