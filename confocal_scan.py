# -*- coding: utf-8 -*-
"""
Created on Mon March 17, 2025

confocal scan performs a raster scan in the xyz space using the piezostage 
and the transmitted signal of the APD
Here, the Graphical User Interface of confocal_scan.py uses:
    - piezo_stage_GUI_two_controllers
    - apd_trace_GUI

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
import apd_trace_GUI

scanModes = ['Ramp', 'Step by step']
PSFmodes = ['x/y', 'x/z', 'y/x', 'y/z'] 
scanImage = ['Maximum', 'Minimum']
centeringMethod = ['Center of mass', 'Gaussian fit']

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    startScanSignal = pyqtSignal(int)
    stopScanSignal = pyqtSignal()
    parametersRampSignal = pyqtSignal(list)
    parametersStepSignal = pyqtSignal(list)
    scanModeSignal = pyqtSignal(str)
    psfModeSignal = pyqtSignal(str)
    scanImageSignal = pyqtSignal(str)
    centeringMethodSignal = pyqtSignal(str)

    CMSignal = pyqtSignal()
    CMautoSignal = pyqtSignal(bool)
    CMSignal_NP2 = pyqtSignal()
    driftSignal = pyqtSignal(bool, int, float, float)
    saveSignal = pyqtSignal()
    closeSignal = pyqtSignal(bool)
    
    def __init__(self, piezo_frontend, main_app = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        self.setWindowTitle('Confocal scanner')
        self.setGeometry(5, 30, 1900, 600) # x pos, y pos, width, height
        self.main_app = main_app
        # import frontend modules
        # piezo widget (frontend) must be imported in the main
        self.piezoWidget = piezo_frontend
        self.setUpGUI()
        return
    
    def setUpGUI(self):
    # Buttons
    # Defino el laser
        self.scan_laser = QtGui.QComboBox()
        self.scan_laser.addItems(shutters)
        self.scan_laser.setCurrentIndex(0)
        self.scan_laser.setFixedWidth(80)
        self.scan_laser.activated.connect(
                                    lambda: self.color_menu(self.scan_laser))
        self.color_menu(self.scan_laser)
        
    # Button: defino el scan ramp o step
        self.scan_mode = QtGui.QComboBox()  
        self.scan_mode.addItems(Scanmodes)
        self.scan_mode.setCurrentIndex(0)
        self.scan_mode.setFixedWidth(80)
        self.scan_mode.currentIndexChanged.connect(self.set_scan_mode)
        
    # Button: defino el scan xy,xz,yz 
        self.PSF_mode = QtGui.QComboBox()  
        self.PSF_mode.addItems(PSFmodes)
        self.PSF_mode.setCurrentIndex(0)
        self.PSF_mode.setFixedWidth(80)
        self.PSF_mode.currentIndexChanged.connect(self.set_psf_mode)
        
        
    # scan
        self.scanButton = QtGui.QPushButton('Start Scan')
        self.scanButton.clicked.connect(self.get_scan)    
        
    # scan
        self.scanButtonstop = QtGui.QPushButton('Stop')
        self.scanButtonstop.clicked.connect(self.get_scan_stop)   
        
    # Scanning parameters
        self.scanrangeLabel = QtGui.QLabel('Range x or z (µm)')
        self.scanrangeEdit = QtGui.QLineEdit('2')

        self.NxLabel = QtGui.QLabel('Number of pixel x')
        self.NxEdit = QtGui.QLineEdit('34')
        self.NxEdit.setToolTip('Poner multiples de 16 por cada 1 µm')
        
        self.scanrangeLabel_y = QtGui.QLabel('Range y or z (µm)')        
        self.scanrangeEdit_y = QtGui.QLineEdit('2')
       
        self.NyLabel = QtGui.QLabel('Number of pixel y or z')
        self.NyEdit = QtGui.QLineEdit('34')
        self.NxEdit.setToolTip('Poner multiples de 16 por cada 1 µm')
        
        self.scanrangeEdit.textChanged.connect(self.set_parameters)
        self.scanrangeEdit_y.textChanged.connect(self.set_parameters) 
        self.NxEdit.textChanged.connect(self.set_parameters) 
        self.NyEdit.textChanged.connect(self.set_parameters) 
        
        # save image Button
        self.saveimageButton = QtGui.QPushButton('Save Frame')
        self.saveimageButton.clicked.connect(self.get_save_frame)
        self.saveimageButton.setStyleSheet(
                "QPushButton { background-color:  rgb(200, 200, 10); }")
        tamaño = 110
        self.saveimageButton.setFixedWidth(tamaño)
        
        # Interface

        self.paramWidget = QtGui.QWidget()
        subgrid = QtGui.QGridLayout()
        self.paramWidget.setLayout(subgrid)

        subgrid.addWidget(self.scan_laser,             1, 1)
        subgrid.addWidget(self.scan_mode,              1, 2) 
        subgrid.addWidget(self.PSF_mode,               1, 3)

        subgrid.addWidget(self.scanrangeLabel,         3, 1)
        subgrid.addWidget(self.scanrangeEdit,          3, 2)  
        subgrid.addWidget(self.scanrangeLabel_y,       4, 1)
        subgrid.addWidget(self.scanrangeEdit_y,        4, 2) 

        subgrid.addWidget(self.NxLabel,                5, 1)
        subgrid.addWidget(self.NxEdit,                 5, 2)        
        subgrid.addWidget(self.NyLabel,                6, 1)
        subgrid.addWidget(self.NyEdit,                 6, 2)      
        
        subgrid.addWidget(self.scanButton,             7, 1)
        subgrid.addWidget(self.scanButtonstop,         7, 3)

        subgrid.addWidget(self.saveimageButton,        8, 3)   #evaluar si vale la pena
        
        # Interface and Buttons of CM and Gauss

        self.goCMWidget = QtGui.QWidget()
        layout3 = QtGui.QGridLayout()
        self.goCMWidget.setLayout(layout3) 

        self.CMcheck = QtGui.QPushButton('go to NP1')
        self.CMcheck.clicked.connect(self.get_CM)
        
        self.CMcheck_auto = QtGui.QCheckBox('')
        self.CMcheck_auto.clicked.connect(self.get_CM_auto)
        
        self.CMcheck_NP2 = QtGui.QPushButton('go to NP2')
        self.CMcheck_NP2.clicked.connect(self.get_CM_NP2)
        
        # Button: defino si el scan es minimun o maximum, o choose
        self.scan_image = QtGui.QComboBox()
        self.scan_image.addItems(ScanImage)
        self.scan_image.setCurrentIndex(0)
        self.scan_image.setFixedWidth(80)
        self.scan_image.currentIndexChanged.connect(self.set_image_scan)
        
        # Button: defino si el metodo de encontrar el centro es center of mass, gauss, o hay dos NP con dos gauss
        self.method_center = QtGui.QComboBox()
        self.method_center.addItems(MethodCenter)
        self.method_center.setCurrentIndex(0)
        self.method_center.setFixedWidth(80)
        self.method_center.currentIndexChanged.connect(self.set_method_center)
        
        NPLabel_1 = QtGui.QLabel('NP 1:')
        NPLabel_2 = QtGui.QLabel('NP 2:')
        
        CxLabel = QtGui.QLabel('Center X:')
        CyLabel = QtGui.QLabel('Center Y:')
        
        self.CxValue_1 = QtGui.QLabel('NaN')
        self.CyValue_1 = QtGui.QLabel('NaN')
        self.CxValue_2 = QtGui.QLabel('NaN')
        self.CyValue_2 = QtGui.QLabel('NaN')

        layout3.addWidget(self.CMcheck,        1,1)
        layout3.addWidget(self.CMcheck_auto,   1,2)
        layout3.addWidget(self.CMcheck_NP2,    1,3)
        layout3.addWidget(self.scan_image,     2,1)
        layout3.addWidget(self.method_center,  2,2)
        
        layout3.addWidget(NPLabel_1,      3, 2)
        layout3.addWidget(NPLabel_2,      3, 3)
        layout3.addWidget(CxLabel,        4, 1)
        layout3.addWidget(CyLabel,        5, 1)
        
        layout3.addWidget(self.CxValue_1, 4, 2)
        layout3.addWidget(self.CxValue_2, 4, 3)
        
        layout3.addWidget(self.CyValue_1, 5, 2)
        layout3.addWidget(self.CyValue_2, 5, 3)
        
        #drift

        self.driftWidget = QtGui.QWidget()
        layout4 = QtGui.QGridLayout()
        self.driftWidget.setLayout(layout4) 

        self.driftButton = QtGui.QPushButton('DRIFT measurment/stop')
        self.driftButton.setCheckable(True)
        self.driftButton.clicked.connect(self.get_drift)
        self.driftButton.setToolTip('With on scan mode: ramp, psf: x/y')
        
        total_time = QtGui.QLabel('Total time (min):')
        refresh_time = QtGui.QLabel('Refresh time (s):')
        
        self.drift_totaltime = QtGui.QLineEdit('20')
        self.drift_refreshtime = QtGui.QLineEdit('40')

        layout4.addWidget(self.driftButton,        1,1)
        layout4.addWidget(total_time,              2,1)
        layout4.addWidget(self.drift_totaltime,    2,2)
        layout4.addWidget(refresh_time,            3,1)
        layout4.addWidget(self.drift_refreshtime,  3,2)
        
        self.drift_widget = pg.GraphicsLayoutWidget()
        
        #image scan
        
        imageWidget = pg.GraphicsLayoutWidget()
        imageWidget.setAspectLocked(True)
        #imageWidget.setMinimumHeight(50)
        #imageWidget.setMinimumWidth(50)
        
        self.img = pg.ImageItem()
        self.point_graph_CM = pg.ScatterPlotItem(size=10,
                                                 symbol='+', color='m')
        
        self.point_graph_CM_2 = pg.ScatterPlotItem(size=5,
                                                 symbol='+', color='b') 
      #   self.vb = imageWidget.addViewBox(row=1, col=1)
     #   self.vb.setMouseMode(pg.ViewBox.RectMode)
     
        self.xlabel = pg.AxisItem(orientation = 'left')
        labelStyle = {'color': '#FFF', 'font-size': '8pt'}
        self.xlabel.setLabel('X', units = 'um',**labelStyle)
        self.ylabel = pg.AxisItem(orientation = 'bottom')
        self.ylabel.setLabel('Y', units = 'um',**labelStyle)
        
        pixel_initial = round(2/34, 3)
        self.get_view_scale(pixel_initial, pixel_initial)
        
        self.vb = imageWidget.addPlot(axisItems={'bottom': self.ylabel, 'left': self.xlabel} )
        self.vb.addItem(self.img)
        self.vb.invertY()
        self.vb.setAspectLocked(True)

        self.hist = pg.HistogramLUTItem(image=self.img)
        self.hist.gradient.loadPreset('thermal')
        # 'thermal', 'flame', 'yellowy', 'bipolar', 'spectrum',
        # 'cyclic', 'greyclip', 'grey' # Solo son estos
        #self.hist.vb.setLimits(yMin=0, yMax=66000)

        for tick in self.hist.gradient.ticks:
            tick.hide()
            
        imageWidget.addItem(self.hist, row=0, col=1)
        
        dockArea = DockArea()
        hbox = QtGui.QHBoxLayout(self)

        viewDock = Dock('Viewbox',size=(100,100))
        viewDock.addWidget(imageWidget)
        viewDock.hideTitleBar()
        dockArea.addDock(viewDock)

        scanDock = Dock('Confocal parameters')
        scanDock.addWidget(self.paramWidget)
        dockArea.addDock(scanDock, 'right', viewDock)

        goCMDock = Dock('CM')
        goCMDock.addWidget(self.goCMWidget)
        dockArea.addDock(goCMDock, 'right', scanDock)

        driftDock = Dock('Drift measurment')
        driftDock.addWidget(self.driftWidget)
        dockArea.addDock(driftDock, 'bottom', goCMDock)
        
        hbox.addWidget(dockArea)
        self.setLayout(hbox)

        
    def color_menu(self, QComboBox):
        """ le pongo color a los menus"""
        if QComboBox.currentText() == shutters[0]:  # verde
            QComboBox.setStyleSheet("QComboBox{color: rgb(0,128,0);}\n")
        elif QComboBox .currentText() == shutters[1]:  # rojo
            QComboBox.setStyleSheet("QComboBox{color: rgb(255,0,0);}\n")
        elif QComboBox .currentText() == shutters[2]: # azul
            QComboBox.setStyleSheet("QComboBox{color: rgb(0,0,255);}\n")
        elif QComboBox .currentText() == shutters[3]: # IR
            QComboBox.setStyleSheet("QComboBox{color: rgb(100,0,0);}\n")

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

        return
    
    def set_parameters(self):
        # set scan parameters 
        parameters = [float(self.scanRangeEdit.text()), \
                      float(self.scanRangeEdit_y.text()), \ 
                      int(self.NxEdit.text()), \
                      int(self.NyEdit.text())]
        # send parameters according to the type of scan
        if self.scan_mode.currentText() == scanModes[0]:
            # ramp
            self.parametersRampSignal.emit(parameters)
            
        elif self.scan_mode.currentText() == scanModes[1]:
            # step by step
            self.parametersStepSignal.emit(parameters)
        return

    def start_scan(self):
        # TODO
        self.point_graph_CM.hide()
        self.point_graph_CM_2.hide()
        if self.scanButton.isChecked():
            self.startScanSignal.emit(self.scan_laser.currentIndex())
        return

    def stop_scan(self):
        self.stopScanSignal.emit()
        return

    def get_CM(self):
        if self.CMcheck.isChecked():
            self.CMSignal.emit()
        return
            
    def get_CM_auto(self):
        if self.CMcheck_auto.isChecked():
            self.CMautoSignal.emit(True)
        else:
            self.CMautoSignal.emit(False)
        return

    def set_scan_mode(self):
        self.set_parameters()
        if self.scan_mode.currentText() == scanModes[0]:
            self.scan_modeSignal.emit(scanModes[0])
        elif self.scan_mode.currentText() == scanModes[1]:
            self.scan_modeSignal.emit(scanModes[1])
        return

    def set_psf_mode(self):
        
        if self.PSF_mode.currentText() == PSFmodes[0]:
            self.psf_modeSignal.emit(PSFmodes[0])
            
        elif self.PSF_mode.currentText() == PSFmodes[1]:
            self.psf_modeSignal.emit(PSFmodes[1])
            
        elif self.PSF_mode.currentText() == PSFmodes[2]:
            self.psf_modeSignal.emit(PSFmodes[2])
            
        elif self.PSF_mode.currentText() == PSFmodes[3]:
            self.psf_modeSignal.emit(PSFmodes[3])
         

    def set_image_scan(self):
        if self.scan_image.currentText() == scanImage[0]:
            self.scanImageSignal.emit(scanImage[0])    
        else self.scan_image.currentText() == scanImage[1]:
            self.scanImageSignal.emit(scanImage[1])
        return            
            
    def set_method_center(self):
        if self.method_center.currentText() == centeringMethod[0]:
            self.centeringMethodSignal.emit(centeringMethod[0])
        else self.method_center.currentText() == centeringMethod[1]:
            self.centeringMethodSignal.emit(centeringMethod[1])
        return
   
    def get_save_frame(self):
        if self.saveImageButton.isChecked():
            self.saveSignal.emit()
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
    
    