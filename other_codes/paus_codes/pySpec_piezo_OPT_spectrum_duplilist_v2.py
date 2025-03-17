# -*- coding: utf-8 -*-
"""
Created on Thu April 22, 2022

pySpec is a control software of the 2nd gen Plasmonic Optical Tweezer setup that
allows the user to acquire spectra of nanostructures using the tunable laser
and the APDs
Here, the Graphical User Interface of pySpec integrates the following modules:
    - lasers control
    - APD signal acquisition

@author: Mariano Barella
mariano.barella@unifr.ch
Adolphe Merkle Institute - University of Fribourg
Fribourg, Switzerland
"""
import time as tm
from pyqtgraph.Qt import QtGui, QtCore
from pyqtgraph.dockarea import DockArea, Dock
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QPushButton, QLineEdit, QLabel
import apd_trace_GUI_S
import laser_control_GUI
import numpy as np
import re
import threading
import matplotlib.pyplot as plt

import piezo_stage_GUI
from bayes_opt import BayesianOptimization
#from bayes_opt import UtilityFunction
#import numpy as np

# time interval to check state of the specturm acquisition button
check_button_state = 100 # in ms
initial_filename = 'spectrum'
spectra_path = 'D:\\daily_data\\spectra\\self_generated_spectra'

#=====================================

# GUI / Frontend definition

#=====================================

class Frontend(QtGui.QMainWindow):
    
    closeSignal = pyqtSignal()
    process_acquired_spectrum_signal = pyqtSignal()
    filenameSignal = pyqtSignal(str)
    Optifunctionx_signal=pyqtSignal()
    Optifunctiony_signal=pyqtSignal()
    Optifunctionz_signal=pyqtSignal()
    OptAll_signal=pyqtSignal()
    OptIterSignal = pyqtSignal(str)
    OptcicleSignal = pyqtSignal(str)
    stepmaxSignal = pyqtSignal(str)
    stepminSignal = pyqtSignal(str)
    Auto_OptAll_signal=pyqtSignal(bool)
    
    
    def __init__(self,piezo_frontend, main_app = True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cwidget = QtGui.QWidget()
        self.setCentralWidget(self.cwidget)
        
        self.main_app = main_app
        
        self.setWindowTitle('pySpec')
        self.setGeometry(150, 30, 1400, 800) # x pos, y pos, width, height
        self.setUpGUI()
        

        return
    
    def setUpGUI(self):
        # import front end modules

        
        self.piezoWidget = piezo_frontend
        self.apdWidget = apd_trace_GUI_S.Frontend()
        self.lasersWidget = laser_control_GUI.Frontend()
        
        # modify from laser's GUI the spectrum acquisition buttons
        self.lasersWidget.integration_time_label.setText('Integration time (s):')
        self.lasersWidget.acquire_spectrum_button.setCheckable(True)
        self.lasersWidget.acquire_spectrum_button.clicked.connect(self.lasersWidget.acquire_spectrum_button_check)
        self.lasersWidget.acquire_spectrum_button.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::checked { background-color: red; }")
        self.lasersWidget.integration_time_comment.setText('Attention: It overrides Duration variable of the APD trace.')
        self.lasersWidget.process_spectrum_button.clicked.connect(self.process_spectrum_button_check)
        self.lasersWidget.process_spectrum_button.setStyleSheet(
                "QPushButton { background-color: lightgray; }"
                "QPushButton::checked { background-color: lightgreen; }")
        self.lasersWidget.filename_label.setText('Filename (.dat)')
        self.lasersWidget.filename_name.setFixedWidth(200)
        self.lasersWidget.filename = initial_filename
        self.lasersWidget.filename_name.setText(self.lasersWidget.filename)
        self.lasersWidget.filename_name.editingFinished.connect(self.set_filename)
        
        # set by default: save APD signals = True
        self.apdWidget.saveAutomaticallyBox.setChecked(True)
        # set autorange by default
        self.apdWidget.enableAutoRagenButton.setChecked(True)
        self.apdWidget.enable_autorange(True)
        
        # GUI layout
        grid = QtGui.QGridLayout()
        self.cwidget.setLayout(grid)
        # Dock Area
        dockArea = DockArea()
        self.dockArea = dockArea
        grid.addWidget(self.dockArea)
        
        ## Add APD trace GUI module
        apdDock = Dock('APD signal')
        apdDock.addWidget(self.apdWidget)
        self.dockArea.addDock(apdDock)

        ## Add Lasers GUI module
        lasersDock = Dock('Lasers')
        lasersDock.addWidget(self.lasersWidget)
        self.dockArea.addDock(lasersDock , 'right', apdDock)    
        
        ## Add piezo module
        piezoDock = Dock('Piezostage control', size=(1,10))
        piezoDock.addWidget(self.piezoWidget)
        self.dockArea.addDock(piezoDock)
        
        
        ## Add optimization Module
        
        self.OptiWidget= QtGui.QWidget()
        OptiWidget_layout = QtGui.QGridLayout()
        self.OptiWidget.setLayout(OptiWidget_layout)
        self.OptimizeZ = QPushButton(self)
        self.OptimizeZ.setText("Optimize Z") #text
        self.OptimizeZ.clicked.connect(self.Optifunctionz_check)
        self.OptimizeZ.setToolTip("OPtimization") #Tool tip
        #self.Optimize.move(230,290)
        self.OptimizeZ.setStyleSheet("background-color : white")
        
        self.OptimizeY = QPushButton(self)
        self.OptimizeY.setText("Optimize Y") #text
        self.OptimizeY.clicked.connect(self.Optifunctiony_check)
        self.OptimizeY.setToolTip("OPtimization") #Tool tip
        #self.Optimize.move(230,290)
        self.OptimizeY.setStyleSheet("background-color : white")
        
        self.OptimizeX = QPushButton(self)
        self.OptimizeX.setText("Optimize X") #text
        self.OptimizeX.clicked.connect(self.Optifunctionx_check)
        self.OptimizeX.setToolTip("OPtimization") #Tool tip
        #self.Optimize.move(230,290)
        self.OptimizeX.setStyleSheet("background-color : white")
        
        self.OptimizeAll = QPushButton(self)
        self.OptimizeAll.setText("Optimize All") #text
        self.OptimizeAll.clicked.connect(self.OptifunctionAll_check)
        self.OptimizeAll.setToolTip("OPtimization of X Y and Z in cicles") #Tool tip
        #self.Optimize.move(230,290)
        self.OptimizeAll.setStyleSheet("background-color : white")
        
        
        self.OptiterationsLabel = QLabel(self)
        self.OptiterationsLabel.setText('N° iterations:')
        self.Optiterations = QLineEdit(self)
        self.Optiterations.setText('10')
        self.Optiterations.setFixedWidth(100)
        
        
        
        self.OptciclesLabel = QLabel(self)
        self.OptciclesLabel.setText('Full ZYX cicles:')
        self.Optcicles = QLineEdit(self)
        self.Optcicles.setText('5')
        self.Optcicles.setFixedWidth(100)
        
        self.OptstepmaxLabel = QLabel(self)
        self.OptstepmaxLabel.setText('Step max (μm):')
        self.Optstepmax = QLineEdit(self)
        self.Optstepmax.setText('0.1')
        self.Optstepmax.setFixedWidth(100)
        
        self.OptstepminLabel = QLabel(self)
        self.OptstepminLabel.setText('Step min (μm):')
        self.OptstepminLabel.setToolTip("This is the one used normally") #Tool tip
        self.Optstepmin = QLineEdit(self)
        self.Optstepmin.setText('0.005')
        self.Optstepmin.setFixedWidth(100)
        self.Optstepmin.setToolTip("This is the one used normally") #Tool tip
        
        self.BLed = QPushButton(self)
        self.BLed.setText("Auto Opt. Spectrum") #text
        self.BLed.clicked.connect(self.FLed)
        self.BLed.setCheckable(True)       
        #self.BInfuse.clicked.connect(self.changeColor)
        self.BLed.setToolTip("Do a optimization round before aquiring spectra at each wavelength") #Tool tip
        
        
        
        
        OptiWidget_layout.addWidget(self.OptiterationsLabel, 1, 3)
        OptiWidget_layout.addWidget(self.Optiterations, 2, 3)
        OptiWidget_layout.addWidget(self.OptciclesLabel, 1, 4)
        OptiWidget_layout.addWidget(self.Optcicles, 2, 4)
        OptiWidget_layout.addWidget(self.OptstepmaxLabel, 3, 3)
        OptiWidget_layout.addWidget(self.Optstepmax, 4, 3)
        OptiWidget_layout.addWidget(self.OptstepminLabel, 3, 4)
        OptiWidget_layout.addWidget(self.Optstepmin, 4, 4)
        OptiWidget_layout.addWidget(self.OptimizeX, 1, 1)
        OptiWidget_layout.addWidget(self.OptimizeY, 2, 1)
        OptiWidget_layout.addWidget(self.OptimizeZ, 3, 1)
        OptiWidget_layout.addWidget(self.OptimizeAll, 4, 1)
        OptiWidget_layout.addWidget(self.BLed, 5, 1)
        
        
        OptiWidgetDock = Dock('Transmission Optimization', size=(1, 4))
        OptiWidgetDock.addWidget(self.OptiWidget)
        self.dockArea.addDock(OptiWidgetDock,'right', piezoDock)
        
        '''gotoDock = Dock('Go to', )
        gotoDock.addWidget(self.gotoWidget)
        dockArea.addDock(gotoDock, 'left', posDock)'''
        
        return
    
    def OptifunctionAll_check(self):
        step=self.Optstepmin.text()
        self.step_signal=step
        self.stepminSignal.emit(self.step_signal)
        
        stepmax=self.Optstepmax.text()
        self.stepmax_signal=stepmax
        self.stepmaxSignal.emit(self.stepmax_signal)
        
        
        iterations=self.Optiterations.text()
        self.iterations_signal=iterations
        self.OptIterSignal.emit(self.iterations_signal)
        
        cicles=self.Optcicles.text()
        self.cicles_signal=cicles
        self.OptcicleSignal.emit(self.cicles_signal)
                
        
        self.OptAll_signal.emit()
        return
    
    def FLed(self):
        if self.BLed.isChecked():
            self.BLed.setStyleSheet("background-color : green")
            self.Auto_OptAll_signal.emit(True)
            
        else:
            self.BLed.setStyleSheet("background-color : White")
            self.Auto_OptAll_signal.emit(False)
            
    
    
    def Optifunctionx_check(self):
        step=self.Optstepmin.text()
        self.step_signal=step
        self.stepminSignal.emit(self.step_signal)
        
        iterations=self.Optiterations.text()
        self.iterations_signal=iterations
        self.OptIterSignal.emit(self.iterations_signal)
        
        self.Optifunctionx_signal.emit()
        return
    
    def Optifunctiony_check(self):
        step=self.Optstepmin.text()
        self.step_signal=step
        self.stepminSignal.emit(self.step_signal)
        
        iterations=self.Optiterations.text()
        self.iterations_signal=iterations
        self.OptIterSignal.emit(self.iterations_signal)

        self.Optifunctiony_signal.emit()
        return
    
    def Optifunctionz_check(self):
        step=self.Optstepmin.text()
        self.step_signal=step
        self.stepminSignal.emit(self.step_signal)
        
        iterations=self.Optiterations.text()
        self.iterations_signal=iterations
        self.OptIterSignal.emit(self.iterations_signal)

        
        self.Optifunctionz_signal.emit()
        return

        
    
    def process_spectrum_button_check(self):
        self.process_acquired_spectrum_signal.emit()
        return
    
    
    @pyqtSlot()    
    def apd_acq_started(self):
        self.apdWidget.traceButton.setChecked(True)
        self.apdWidget.get_trace()
        return
    
    @pyqtSlot()    
    def apd_acq_stopped(self):
        self.apdWidget.acquisition_stopped()
        return    
    
    @pyqtSlot()    
    def spectrum_finished(self):
        self.lasersWidget.acquire_spectrum_button.setChecked(False)
        return
    
    def set_filename(self):
        filename = self.lasersWidget.filename_name.text()
        if filename != self.lasersWidget.filename:
            self.lasersWidget.filename = filename
            self.filenameSignal.emit(self.lasersWidget.filename)    
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
            self.closeSignal.emit()
            tm.sleep(1)
            app.quit()
        else:
            event.ignore()
            print('Back in business...')    
        return
    
    #def OptiWidget(self):

    
    def make_modules_connections(self, backend):    
        # connect Frontend modules with their respectives Backend modules
        backend.piezoWorker.make_connections(self.piezoWidget)
        backend.apdWorker.make_connections(self.apdWidget)
        backend.lasersWorker.make_connections(self.lasersWidget)
        backend.spectrum_finished_signal.connect(self.spectrum_finished)
        backend.apd_acq_started_signal.connect(self.apd_acq_started)
        backend.apd_acq_stopped_signal.connect(self.apd_acq_stopped)
        return

    

#=====================================

# Controls / Backend definition

#===================================== 
        
class Backend(QtCore.QObject):
    
    apd_acq_started_signal = pyqtSignal()
    apd_acq_stopped_signal = pyqtSignal()
    spectrum_finished_signal = pyqtSignal()
    OPtiflag_signal = pyqtSignal()
    
    def __init__(self, piezo_stage, piezo_backend, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.piezo_stage = piezo_stage
        self.piezoWorker = piezo_backend
        self.lasersWorker = laser_control_GUI.Backend()
        self.apdWorker = apd_trace_GUI_S.Backend()
        self.apdWorker.save_automatically_bool = True
        self.AutoOpti= False
        self.acquiring_spectrum_flag= False  
        self.scanTimer = QtCore.QTimer()
        self.scanTimer.timeout.connect(self.continue_scan) # funciton to connect after each interval
        self.scanTimer.setInterval(check_button_state) # in ms
        self.list_of_transmission_files = []
        self.list_of_monitor_files = []
        self.filename = initial_filename
        return
    
    @pyqtSlot(str)
    def set_filename(self, new_filename):
        self.filename = new_filename
        print('New filename has been set:', self.filename)
        return
    
    def OptIter_Signal(self, Niterations):
        print(Niterations)
        self.iterations = Niterations
        return
    
    def OptCicle_Signal(self, Ncicles):
        print(Ncicles)
        self.cicles = Ncicles
        return
    
    def Optflag_Signal(self):
        self.OptiFlag = False
    
    def stepmin_signal(self, stepsizemin):
        self.step = stepsizemin
        return
    
    def stepmax_signal(self, stepsizemax):
        self.stepmax = stepsizemax
        return
    
    def auto_opt_signal_fun(self, optbool):
        self.AutoOpti=optbool
        print("AutoOpti= "+ str(self.AutoOpti))
        return
    
    

    def OptAll2(self):
        
        
        
        channels=['z','y','x']
        
        if self.cicles==' ':
            jmax=5 #default number of iterations
            
        else: jmax=int(self.cicles)+1
        
        for j in range(jmax):

            stepmax=float(self.stepmax)
            stepmin=float(self.step)
            
            

            step=np.linspace(stepmax, stepmin , jmax)

            for axis in channels:
                self.Optifunction(axis, step[j])
                #print(step[j])
           
        if self.acquiring_spectrum_flag:  
            print ("closing sognals")
            self.OPtiflag_signal.emit()      
            
            self.apdWorker.acquire_continuously_bool=False
            #self.apdWorker.acquisition_flag = False
            #tm.wait(1)
            self.apd_acq_stopped_signal.emit()
        
    def Optifunction(self, axis, step):
        
        #print(step)
        #Initposition=piezo_backend.read_position() 
        #self.apdWorker.mean_data_APD
        
        #print('Initial signal ' + "%.4f" %self.apdWorker.mean_data_APD+ ' V')
        #print('Initial Position ' +str(Initposition))
        Initsignal=float ("%.3f" % self.apdWorker.mean_data_APD)
        Cursignal=100.00
        #step=float(self.step)
        
        i=0 # i is going to be the maximum number of iterations
        if self.iterations==' ':
            imax=11 #default number of iterations
        else : imax=int(self.iterations)+1
        #while Cursignal!=Initsignal and i<20:
            
        def Move (step):
            piezo_backend.piezo_stage.move_relative(axis,step)
            LastMov=step
            #print(LastMov)
            tm.sleep(0.05)
            Cursignal=float ("%.3f" % self.apdWorker.mean_data_APD)

            return LastMov, Cursignal #LastMov will define if the previous movement was up or down
        
        for i in range (imax):
                       
            #set moving command according to axis and direction
            #up or down is going to be defined inside the function
                                
            if i==0:
                LastMov, Cursignal=Move(-step)
                SignalList=[Initsignal]



            elif LastMov<0 and SignalList[i]>SignalList[i-1]:
                LastMov, Cursignal=Move(-step)
                #print("Last move was down and succesfull, so moving DOWN again")
                
            elif LastMov<0 and SignalList[i]<SignalList[i-1]:
                LastMov, Cursignal=Move(step)
                #print("Last move was down and UNsuccesfull, so moving UP")
                
            elif LastMov>0 and SignalList[i]>SignalList[i-1]:
                LastMov, Cursignal=Move(step)
                #print("Last move was UP and succesfull, so moving UP again")
                
            elif LastMov>0 and SignalList[i]<SignalList[i-1]:
                LastMov, Cursignal=Move(-step)
                #print("Last move was UP and UNsuccesfull, so moving DOWN")
                
            elif SignalList[i]==SignalList[i-1]:
                break
            
            SignalList= SignalList+[Cursignal]
             
            print(SignalList)
            
            
                #print(SignalList)
                #print('end of cicle')
                
                
    @pyqtSlot(bool)    
    def acquire_spectrum(self, acq_spec_flag):
        # acq_spec_flag varaiable is the state of the button
        self.acquiring_spectrum_flag = acq_spec_flag
        if self.acquiring_spectrum_flag:
            self.OPtiflag_signal.emit() 
            print('\nStarting acquisition of the spectrum...')
            # set integration time
            self.apdWorker.change_duration(self.lasersWorker.integration_time)
            # measure baseline first
            print('\nAcquiring baseline first...')
            self.measure_baseline()
            self.spectrum_counter = 0
            self.Dspectrum_counter = 0
            # initiate list of files
            self.list_of_transmission_files = []
            self.list_of_monitor_files = []
            # start timer to acquire the spectrum
            print('\nAcquiring spectrum...')
            self.scanTimer.start()
        else:
            self.scanTimer.stop()
            self.apd_acq_stopped_signal.emit()
            self.spectrum_finished_signal.emit()
            self.spectrum_counter = 0
            self.Dspectrum_counter = 0
            print('\nAborting acquisition of the spectrum...')
            
        return
    
    

    def continue_scan(self):
        # check if button is checked or counter continues to increase
        if self.acquiring_spectrum_flag:
            # check if transmission APD is acquiring first
            # if not, continue with the spectrum
            if not self.apdWorker.acquisition_flag:
                
                #if not self.OptiFlag:
                # close shutter of Ti:Sa if open
                self.lasersWorker.shutterTisa(False)
                # check status of Ti:Sa
                # if Ti:Sa is not changing wavelength continue with the spectrum
                status = self.lasersWorker.update_tisa_status()
                if status == 1:
                    # try to measure or check if we're done
                    
                    """self.dupliWavelength=[]"""
                    self.dupliWavelength = [val for pair in zip(self.lasersWorker.wavelength_scan_array-self.lasersWorker.wavelength_scan_array, self.lasersWorker.wavelength_scan_array) for val in pair]
                    #print (self.dupliWavelength)
                    if self.Dspectrum_counter < len(self.dupliWavelength):
                       
                        # still scanning
                        # get and change wavelength
                        wavelength = self.lasersWorker.wavelength_scan_array[self.spectrum_counter]
                        self.lasersWorker.change_wavelength(wavelength)
                        
                        Doublewavelength = self.dupliWavelength[self.Dspectrum_counter]
                        # set suffix for saving the intensity trace, wavelength in angstroms
                        self.apdWorker.spectrum_suffix = '_{:05d}ang'.format(int(round(Doublewavelength*10,0)))
                        # increment counter for next step
                        
                        self.Dspectrum_counter += 1    
                         # add a delay before opening shutter to allow the system to settle
                        
                        # open shutter
                        
                        

                        #part added to run the optimization at each wavelength

                        self.OptiFlag=True
                        #print (wavelength)
                        #print (Doublewavelength)
                        
                        # emit pyqtSignal to frontend to enable trace displaying
                        # and start signal acquisition

                         
                        if int(Doublewavelength)==0:
                            
                            if self.AutoOpti:
                                tm.sleep(0.1)
                                self.lasersWorker.shutterTisa(True)

                                self.apdWorker.save_automatically_bool = False
                                self.apdWorker.acquire_continuously_bool=True
                                self.apd_acq_started_signal.emit()
                                # set acquisition variable of APD backend to True
                                self.apdWorker.acquisition_flag = True
                                tm.sleep(0.1)
                                
                                self.OptAll()
                                
                                #self.Initiosignal=float ("%.3f" % self.apdWorker.mean_data_APD)
                                #print (self.Initiosignal)
                                #print (self.OptiFlag)
                                
                            
                        
                            
                                #print ("OPtimizing first")
                            
                        else:
                                tm.sleep(0.1)
                                self.lasersWorker.shutterTisa(True)                            
                                #print("autooptiFALSE="+str(self.AutoOpti))
                                self.spectrum_counter += 1
                                #print ("saving")
                                self.apdWorker.save_automatically_bool = True
                                print (wavelength)
                                

                                self.apd_acq_started_signal.emit()
                                # set acquisition variable of APD backend to True
                                self.apdWorker.acquisition_flag = True
                                
                                
                                #if self.AutoOpti:
                                    
                                    #self.Finitiosignal=float ("%.3f" % self.apdWorker.mean_data_APD)
                                    #print (self.Finitiosignal)
                                    #print ("Auto Optimization Improved: "+str(((self.Finitiosignal-self.Initiosignal)/self.Initiosignal)*100)+"%")
                         
                            
                    
                    else:
                        # no more points to scan
                        self.acquire_spectrum(False)
                else:
                    print('\nWavelength has not been changed.')
                    #print('Ti:Sa status: ', status)
        return
    
    
    def measure_baseline(self):
        # check if button is checked or counter continues to increase
        if self.acquiring_spectrum_flag:
            # check if transmission APD is acquiring first
            # if not, continue with the spectrum
            if not self.apdWorker.acquisition_flag:
                # close shutter of Ti:Sa if open
                self.lasersWorker.shutterTisa(False)
                # set suffix for saving the intensity trace
                self.apdWorker.spectrum_suffix = '_baseline'
                # emit pyqtSignal to frontend to enable trace displaying
                # and start signal acquisition
                self.apd_acq_started_signal.emit()
                # set acquisition variable of APD backend to True
                self.apdWorker.acquisition_flag = True
        return

    @pyqtSlot(str, str)
    def append_saved_file(self, full_filepath_data, full_filepath_monitor):
        self.list_of_transmission_files.append(full_filepath_data)
        self.list_of_monitor_files.append(full_filepath_monitor)
        return
    
    def process_signals(self, list_of_files):
        list_of_files.sort()
        # find baseline file and spectrum files
        list_of_files_spectra = [f for f in list_of_files if not re.search('baseline', f)]
        baseline_file = [f for f in list_of_files if re.search('baseline', f)][0]
        # open baseline file
        baseline_data = np.load(baseline_file)
        # get baseline level
        baseline_level = np.mean(baseline_data)
        baseline_std_dev = np.std(baseline_data, ddof = 1)
        # allocate spectrum
        number_of_points = len(list_of_files_spectra)
        mean_array = np.zeros(number_of_points)
        error_array = np.zeros(number_of_points)
        # calculate spectrum
        for i in range(number_of_points):
            f = list_of_files_spectra[i]
            data = np.load(f)
            mean_array[i] = np.mean(data) - baseline_level
            std_dev = np.std(data, ddof = 1)
            error_array[i] = np.sqrt(std_dev**2 + baseline_std_dev**2)
        return mean_array, error_array
    
    @pyqtSlot()

    
    def process_acquired_spectrum(self):
        print('Processing all spectra...')
        # preapre arrays
        wavelength = self.lasersWorker.wavelength_scan_array
        mean_data, error_data = self.process_signals(self.list_of_transmission_files)
        mean_monitor, error_monitor = self.process_signals(self.list_of_monitor_files)
        # set filename
        filename_spectrum = self.filename
        timestr = tm.strftime("_%Y%m%d_%H%M%S")
        filename_spectrum = filename_spectrum + timestr
        # it will save an ASCII encoded text file
        data_to_save = np.transpose(np.vstack((wavelength[:len(mean_data)], \
                                               mean_data, error_data, \
                                               mean_monitor, error_monitor)))
        header_txt = 'wavelength transmission_mean transmission_error monitor_mean monitor_error\nnm V V V V'
        ascii_full_filepath = spectra_path + '\\' + filename_spectrum + '.dat'
        np.savetxt(ascii_full_filepath, data_to_save, fmt='%.6f', header=header_txt)
        print('Spectrum has been generated and saved with filename %s.dat' % filename_spectrum)
        return

    
    @pyqtSlot()
    def close_all_backends(self):
        self.piezoWorker.close_backend(main_app = False)
        print('Closing all Backends...')
        self.lasersWorker.closeBackend()
        self.apdWorker.closeBackend()
        print('Stopping updater (QtTimer)...')
        self.scanTimer.stop()
        print('Exiting thread...')
        workerThread.exit()
        return
    #=====================================
    
    # Optimiyzation extra
    
    #===================================== 
    
    def Optifunctionx(self):

        self.x = threading.Thread(target=self.Optifunction, args=('x', float(self.step)))
        self.x.start()
        
    def Optifunctiony(self):
        self.y = threading.Thread(target=self.Optifunction, args=('y', float(self.step)))
        self.y.start()
        
    def Optifunctionz(self):
        #self.apd_acq_started_signal.emit()
        #print ("emmited")
        #self.apdWorker.acquisition_flag = True
        #print ("flag raised")
        
        self.z = threading.Thread(target=self.Optifunction, args=('z', float(self.step)))
        self.z.start()
        
    def OptAll(self):
        self.OPtall1 = threading.Thread(target=self.OptAll2)
        self.OPtall1.start()
        #self.OptAll2()
        
        

                
           
            
    def make_modules_connections(self, frontend):
        frontend.closeSignal.connect(self.close_all_backends)
        # connect Backend modules with their respectives Frontend modules
        frontend.apdWidget.make_connections(self.apdWorker)
        frontend.lasersWidget.make_connections(self.lasersWorker)
        frontend.piezoWidget.make_connections(self.piezoWorker)
        # connection that triggers the measurement of the spectrum
        frontend.lasersWidget.acquire_spectrum_button_signal.connect(self.acquire_spectrum)
        # connection that process the acquired data
        frontend.process_acquired_spectrum_signal.connect(self.process_acquired_spectrum)
        frontend.filenameSignal.connect(self.set_filename)
        frontend.Optifunctionx_signal.connect(self.Optifunctionx)
        frontend.Optifunctiony_signal.connect(self.Optifunctiony)
        frontend.Optifunctionz_signal.connect(self.Optifunctionz)
        frontend.OptAll_signal.connect(self.OptAll)
        frontend.OptIterSignal.connect(self.OptIter_Signal)
        frontend.OptcicleSignal.connect(self.OptCicle_Signal)
        frontend.stepminSignal.connect(self.stepmin_signal)
        frontend.stepmaxSignal.connect(self.stepmax_signal)
        frontend.Auto_OptAll_signal.connect(self.auto_opt_signal_fun)
        # from backend
        self.apdWorker.fileSavedSignal.connect(self.append_saved_file)
        self.OPtiflag_signal.connect(self.Optflag_Signal)
        return
    

#=====================================

#  Main program

#=====================================
      
if __name__ == '__main__':
    # make application
    app = QtGui.QApplication([])

    # init stage
    piezo = piezo_stage_GUI.piezo_stage  
    piezo_frontend = piezo_stage_GUI.Frontend(main_app = False)
    piezo_backend = piezo_stage_GUI.Backend(piezo)
    

    # create both classes
    gui = Frontend(piezo_frontend)
    worker = Backend(piezo, piezo_backend)
       
    ###################################
    # move backend to another thread
    workerThread = QtCore.QThread()
    
    workerThread = QtCore.QThread()
    # move the timer of the piezo and its main worker
    worker.piezoWorker.updateTimer.moveToThread(workerThread)
    worker.piezoWorker.moveToThread(workerThread)
    
    # for APD signal displaying
    worker.apdWorker.updateTimer.moveToThread(workerThread)
    worker.apdWorker.moveToThread(workerThread)
    # for lasers
    worker.lasersWorker.moveToThread(workerThread)
    # now the master backend
    worker.scanTimer.moveToThread(workerThread)
    worker.moveToThread(workerThread)

    ###################################

    # connect both classes 
    worker.make_modules_connections(gui)
    gui.make_modules_connections(worker)
    
    # start thread
    workerThread.start()
    
    gui.show()
    app.exec()
    
    
