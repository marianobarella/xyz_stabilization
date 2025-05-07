# -*- coding: utf-8 -*-
"""
Created on Mon Feb 20, 2023
Modified on Mon May 05, 2025 

@author: Pau Molet Bachs
@contributor: Mariano Barella
"""

import sys
from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QApplication, QPushButton, QListWidget, QInputDialog
from PyQt5.QtWidgets import QAbstractItemView, QVBoxLayout, QDialog, QMenu, QAction, QFileDialog
#from PyQt5.QtCore import QSize, Qt 
from PyQt5.QtGui import QIcon, QFont
import time
import threading
# import pygame
import re
#import os
from datetime import datetime
import calendar
import numpy as np
import MXII_valve # the MXII_valve.py file has to be in the same folder
import serial

# definition of COM ports
COM_valve = 'COM5' # microfluidics valve 
COM_pump = 'COM4' # microfluidics pump

# Channel definitions according to the tube connections
waste_channel = 0 # physically in position 1
cleaning_channel = 1 # physically in position 2
buffer_channel = 2 # physically in position 3
protein_channel = 3  # physically in position 4
substrate_channel = 4  # physically in position 5
chamber_channel = 5 # physically in position 6

# Elite pump dictionary
CarriageReturn=' \r' # it's needed at the end of each command, list below
ClearWithdrawVolume = '0cwvolume'
ClearInfuseVolume = '0civolume'
Volume='0tvolume '
InfuseRate='0irate '
WithdrawRate='0wrate '
Infuse= '0irun'
Withdraw='0wrun'
Stop= '0stop'
Ramp='0iramp '
infusedVolume='0ivolume'
withrawdVolume='0wvolume'

# Connect to the Rheodyne 7-port valve
valve = MXII_valve.MX_valve(COM_valve, ports = 6, name = 'My_valve', verbose = True)

# Connect to the Pump 11 Elite
ser = serial.Serial(COM_pump, baudrate = 115200, bytesize = serial.EIGHTBITS, \
                    stopbits = serial.STOPBITS_TWO, parity = serial.PARITY_NONE, \
                    timeout=3)

# Initialize the pump. Send the instructions
# Reset the volume at start of session
instruction = ClearWithdrawVolume + CarriageReturn
ser.write(instruction.encode())
instruction = ClearInfuseVolume + CarriageReturn
ser.write(instruction.encode())
ser.read(size = 30)

print("Volume reset, Pump ready")
#logging.info("Volume reset, Pump ready")

# define the classe
class Fluidicsys(QWidget):
    
    def __init__(self,log_file_path):
        super(Fluidicsys,self).__init__()
        self.filepath=log_file_path
        print(self.filepath)
        self.BVolume()
        self.BIRate()
        self.BWRate()
        self.BInfuse()
        self.BWithdraw()
        self.Linelist()
        self.BStop()
        self.BcleanLine()
        self.Bramp()
        self.BPulse()
        self.BFinalRate()
        self.BRamptime()
        self.CleanLinelist()
        self.BrepeatCL()
        self.BCurrCh()
        self.Event()
        self.Discard()
        self.Wire1()
        self.BLed()
        self.BReset()
        self.CurrStatus()
        self.setWindowTitle("Fluidic system")
        self.setGeometry(400, 400, 400, 500)
        self.setStyleSheet("background-color : white")
        self.work = True
        self.withdraw = True
        self.CurrCh = 0
        self.dir = True
        self.FExhaust()
        self.NewLog()
        self.getchannel()
        self.displaychannel()
        return
        
    # Buttons
    def Event(self):
        self.Eventline = QLineEdit(self)
        self.Eventline.move(20, 450)
        self.Eventline.resize(280, 40)
        self.Eventline.returnPressed.connect(self.WriteEvent)
        return
        
    def NewLog(self):
        self.NewLog = QPushButton(self)
        self.NewLog.setText("New file")
        self.NewLog.clicked.connect(self.FNewLog)
        self.NewLog.setToolTip("Click to initiate new log file")
        self.NewLog.move(310, 450)
        self.NewLog.setStyleSheet("background-color : #FDFD96")
        return
    
    def CurrStatus(self):
        self.CurrStatus = QLabel(self)
        bold = QFont()
        bold.setBold(True)
        bold.setPointSize(12)
        self.CurrStatus.setFont(bold)
        self.Currstatus_text = "Waiting"
        self.CurrStatus.setText(self.Currstatus_text)
        self.CurrStatus.move(20, 400)
        self.CurrStatus.resize(350, 40)
        return
        
    def Discard(self):
        self.Openinfo = QPushButton(self)
        self.Openinfo.setText("Discard")
        self.Openinfo.clicked.connect(self.FDiscard)
        self.Openinfo.setToolTip("Discard 20 microliters to channel 9") #Can be changed in function
        self.Openinfo.move(280, 100)
        self.Openinfo.setStyleSheet("background-color : #ecd6c0")
        return
        
    def Wire1(self):
        self.Wire1 = QPushButton(self)
        self.Wire1.setText("Wire") #text
        self.Wire1.clicked.connect(self.FExhaust)
        self.Wire1.setCheckable(True) 
        self.Wire1.setChecked(True)
        #self.BInfuse.clicked.connect(self.changeColor)
        self.Wire1.setToolTip("exit app") #Tool tip
        self.Wire1.move(2070, 3000)
        self.Wire1.resize(0, 0)
        self.Wire1.setStyleSheet("background-color : green")
        return

    def BLed(self):
        self.BLed = QPushButton(self)
        self.BLed.setText("LED")
        self.BLed.clicked.connect(self.FLed)
        self.BLed.setCheckable(True)       
        #self.BInfuse.clicked.connect(self.changeColor)
        self.BLed.setToolTip("Switch ON/OFF the LED") #Tool tip
        self.BLed.move(270,370)
        self.BLed.setStyleSheet("background-color : white")
        return
        
    def BcleanLine(self):
        self.BcleanLine = QPushButton(self)
        self.BcleanLine.setText("Clean Line X")          
        self.BcleanLine.setIcon(QIcon("Clean Line.png"))
        self.BcleanLine.setShortcut('Ctrl + c')
        self.BcleanLine.clicked.connect(self.FCleanline)
        self.BcleanLine.setToolTip("Withdraw from channel of left list and infuse at line of right list")
        self.BcleanLine.move(100, 70)
        self.BcleanLine.resize(100, 25)
        self.BcleanLine.setStyleSheet("background-color : #C8A2C8")
        return
        
    def BCurrCh(self):
         self.BCurrCh = QLabel(self)
         self.BCurrCh.setText('Current Channel')
         self.BCurrCh.move(20, 50)
         self.BCurrChtxt = QLabel(self)
         bold=QFont()
         bold.setBold(True)
         bold.setPointSize(14)
         self.BCurrChtxt.setFont(bold)
         self.BCurrChtxt.setText(str(0))
         self.BCurrChtxt.move(100, 40)
         self.BCurrChtxt.resize(70, 30)
         return
        
    def BrepeatCL(self):
        self.BrepeatCLlab = QLabel(self)
        self.BrepeatCLlab.setText('Cycles:')
        self.BrepeatCLlab.move(210, 75)
        self.BrepeatCL = QLineEdit(self)
        self.BrepeatCL.move(250, 70)
        self.BrepeatCL.resize(20, 25)
        self.BrepeatCL.setStyleSheet("background-color : #C8A2C8")
        return
    
    def BWithdraw(self):
        self.BWithdraw = QPushButton(self)
        self.BWithdraw.setText("Withdraw")         
        self.BWithdraw.setIcon(QIcon("Withdraw.png"))
        self.BWithdraw.setShortcut('Ctrl + w')
        self.BWithdraw.clicked.connect(self.FWithdraw)
        self.BWithdraw.setToolTip("Withdraw") 
        self.BWithdraw.move(100, 100)
        self.BWithdraw.setStyleSheet("background-color : #FA8072")
        return
        
    def BWRate(self):
         self.nameLabel = QLabel(self)
         self.nameLabel.setText('Rate (ml/min):')
         self.nameLabel.move(20, 130)
         self.WRate = QLineEdit(self)
         self.WRate.move(100, 130)
         self.WRate.resize(50, 30)
         self.WRate.setStyleSheet("background-color : #FA8072")
         return
        
    def Linelist(self):
        self.withdrawlist = QListWidget(self)
        self.withdrawlist.setSelectionMode(QAbstractItemView.MultiSelection)
        self.withdrawlist.insertItem(waste_channel, "Waste") # 1
        self.withdrawlist.insertItem(cleaning_channel, "EtOH") # 2
        self.withdrawlist.insertItem(buffer_channel, "Buffer") # 3
        self.withdrawlist.insertItem(protein_channel, "Protein") # 4
        self.withdrawlist.insertItem(substrate_channel, "Substrate") # 5
        self.withdrawlist.insertItem(chamber_channel, "Chamber") # 6
        self.withdrawlist.setToolTip("Select the channel to withdraw from")
        self.withdrawlist.move(100,170)
        self.withdrawlist.resize(60, 220)
        self.withdrawlist.setStyleSheet("background-color : white")
        self.withdrawlist.setContextMenuPolicy(3)  # Enable custom context menu (Qt.CustomContextMenu)
        self.createContextMenu()
        return

    def BInfuse(self):
        self.BInfuse = QPushButton(self)
        self.BInfuse.setText("Infuse")          
        self.BInfuse.setIcon(QIcon("Infuse.png"))
        self.BInfuse.setShortcut('Ctrl + i')
        self.BInfuse.clicked.connect(self.FInfuse)
        self.BInfuse.move(190, 100)
        self.BInfuse.setStyleSheet("background-color : #98FB98")
        return
        
    def BIRate(self):
        #self.nameLabel = QLabel(self)
        #self.nameLabel.setText('Rate (ml/min):')
        #self.nameLabel.move(20, 150)
        self.IRate = QLineEdit(self)
        self.IRate.move(190, 130)
        self.IRate.resize(50, 30)
        self.IRate.setStyleSheet("background-color : #98FB98") 
        return
        
    def CleanLinelist(self):
        self.CleanLinelist = QListWidget(self)
        self.CleanLinelist.setSelectionMode(QAbstractItemView.MultiSelection)
        self.CleanLinelist.insertItem(waste_channel, "Waste") # 1
        self.CleanLinelist.insertItem(cleaning_channel, "EtOH") # 2
        self.CleanLinelist.insertItem(buffer_channel, "Buffer") # 3
        self.CleanLinelist.insertItem(protein_channel, "Protein") # 4
        self.CleanLinelist.insertItem(substrate_channel, "Substrate") # 5
        self.CleanLinelist.insertItem(chamber_channel, "Chamber") # 6
        self.CleanLinelist.setToolTip("Select the channel to Infuse to")
        self.CleanLinelist.move(190, 170)
        self.CleanLinelist.resize(60, 220)
        self.CleanLinelist.setStyleSheet("background-color : white")
        return
         
    def BStop(self):
        self.BStop = QPushButton(self)
        self.BStop.setText("Stop")
        self.BStop.setIcon(QIcon("Stop.png"))
        self.BStop.setShortcut('Ctrl + s')
        self.BStop.clicked.connect(self.FStop)
        self.BStop.move(160, 10)
        self.BStop.setStyleSheet("background-color : red")
        return
        
    def BReset(self):
        self.BReset = QPushButton(self)
        self.BReset.setText("Reset")
        self.BReset.setShortcut('Ctrl + r')
        self.BReset.clicked.connect(self.reset)
        self.BReset.setToolTip("Reset the volume in pump")
        self.BReset.move(250, 10)
        self.BReset.setStyleSheet("background-color : orange")
        return
        
    def BVolume(self):
        self.nameLabel = QLabel(self)
        self.nameLabel.setText('Volume (ml):')
        self.nameLabel.move(20, 20)
        self.Volume = QLineEdit(self)
        self.Volume.move(100, 10)
        self.Volume.resize(50, 30)
        return
        
    def BPulse(self):
        self.BPulse = QPushButton(self)
        self.BPulse.setText("Pulse")
        self.BPulse.setIcon(QIcon("Pulse.png"))
        self.BPulse.setShortcut('Ctrl + p')
        self.BPulse.clicked.connect(self.FPulse)
        self.BPulse.setToolTip("Send a pulse of flow")
        self.BPulse.move(270, 150)
        self.BPulse.setStyleSheet("background-color: #3498db; color: #ffffff")   
        return
    
    def Bramp(self):
        self.Bramp = QPushButton(self)
        self.Bramp.setText("Ramp & Infuse")
        self.Bramp.setIcon(QIcon("Ramp.png"))
        self.Bramp.clicked.connect(self.Framp)
        self.Bramp.setToolTip("Infuse with a rate ramp and total volume")
        self.Bramp.move(270, 180)
        self.Bramp.setStyleSheet("background-color : #DE5D83")
        return
        
    def BFinalRate(self):
        self.nameLabel = QLabel(self)
        self.nameLabel.setText('Final:')
        self.nameLabel.move(270, 220)
        self.FinalRate = QLineEdit(self)
        self.FinalRate.setToolTip("Final rate")
        self.FinalRate.move(300, 210)
        self.FinalRate.resize(50, 30)
        return

    def BRamptime(self):
        self.nameLabel = QLabel(self)
        self.nameLabel.setText('s:')
        self.nameLabel.move(270, 260)
        self.Ramptime = QLineEdit(self)
        self.Ramptime.setToolTip("Ramp time")
        self.Ramptime.move(300, 250)
        self.Ramptime.resize(50, 30)
        return
      
    #Changing name of lists      
    def createContextMenu(self):
        self.context_menu = QMenu(self)
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self.editItemText)
        self.context_menu.addAction(edit_action)
        self.withdrawlist.customContextMenuRequested.connect(self.showContextMenu)
        return
    
    def showContextMenu(self, pos):
        item = self.withdrawlist.itemAt(pos)
        if item:
            self.context_menu.popup(self.withdrawlist.mapToGlobal(pos))
        return
    
    def editItemText(self):
        selected_item = self.withdrawlist.currentItem()
        row2Ch=self.withdrawlist.row(self.withdrawlist.currentItem())
        row2txt2=self.CleanLinelist.item(row2Ch)
        if selected_item:
            new_text, ok = QInputDialog.getText(self, "Edit Item", "Edit item text:", text=selected_item.text())
            if ok and new_text:
                selected_item.setText(new_text)    
                row2txt2.setText(new_text)
        return

    # Functions
    def FNewLog(self):
        self.f.close()
        log_file_path = selectFolderDialog()
        self.filepath = log_file_path
        print('Selected filepath:', self.filepath)
        self.f = open(self.filepath, "a") # append mode
        self.f.write("Initializing a new experiment\n")
        return        
        
    def clock(self):
        current_GMT = time.gmtime()
        # ts stores timestamp
        ts = calendar.timegm(current_GMT)   
        timestamp = ts
        # convert to datetime
        date_time = datetime.fromtimestamp(timestamp)
        # convert timestamp to string in dd-mm-yyyy HH:MM:SS
        self.str_date_time = date_time.strftime("%H:%M")
        return self.str_date_time

    def getchannel(self):
        """ for MUX elveflow
        valve = c_int32(-1)
        error = MUX_DRI_Get_Valve(Instr_ID.value,byref(valve)) #get the active valve. it returns 0 if valve is busy.
        """
        self.CurrCh = valve.get_port() # for MXII valve
        time.sleep(0.7)
        #self.CurrCh=valve.value #for MUX
        #print('selected channel', valve.value)
        return
        
    def displaychannel(self):
        if self.Wire1.isChecked():     
            self.BCurrChtxt.setText(str(self.CurrCh))
        else:
            self.BCurrChtxt.setText('Buffer')
        return

    def set_MXII_dis_valve(self, MXII_channel):
        valve.change_port(MXII_channel)
        time.sleep(2)
        return        
 
    # def set_MUX_dis_valve(self, MUX_channel):
    #     valve2=c_double()
    #     Valve2=int(MUX_channel)#convert to int
    #     Valve2=c_int32(Valve2)#convert to c_int32
    #     if self.CurrCh<int(MUX_channel):
    #         error=MUX_DRI_Set_Valve(Instr_ID.value,Valve2,2) #you can select valve rotation way, either shortest 0, clockwise 1 or counter clockwise 2(only for MUX Distribution and Recirculation)
    #     else:
    #         error=MUX_DRI_Set_Valve(Instr_ID.value,Valve2,1) #you can select valve rotation way, either shortest 0, clockwise 1 or counter clockwise 2(only for MUX Distribution and Recirculation)

    #     time.sleep(2)
    #     return

    def ChannelSelection(self, WoI, line):
        self.getchannel()
        self.displaychannel()
        #time.sleep(0.2) #wait 0.2 seconds for the Valve to get the channel
        if WoI == 'Infuse': #select channel for infusing from right list
            items = self.CleanLinelist.selectedItems()
            a = []
            for h in range(len(items)):
                #print(str(self.CleanLinelist.row(self.CleanLinelist.selectedItems()[i])))
                row2Ch = 1 + self.CleanLinelist.row(self.CleanLinelist.selectedItems()[h])
                #print(row2Ch)
                a.append(str(row2Ch))
            if int(a[line]) == self.CurrCh: # Do you have selected a channel?
               pass 
            else :
                #board.digital[12].write(0) #3/2 valve on coil
                #self.set_MUX_dis_valve(a[line])
                self.set_MXII_dis_valve(int(a[line]))
                #time.sleep(0.5) #wait 0.5 seconds for the valve to change2
        else:  #select channel for withdrawing from left list
            witems = self.withdrawlist.selectedItems()
            b = []
            for u in range(len(witems)):
                #print(str(self.CleanLinelist.row(self.CleanLinelist.selectedItems()[i])))
                row2Ch = 1 + self.withdrawlist.row(self.withdrawlist.selectedItems()[u])
                #print(row2Ch)
                b.append(str(row2Ch))
            if int(b[line]) == self.CurrCh: #Do you have selected a channel?
               pass 
            else :
                #board.digital[12].write(0) #3/2 valve on coil
                #self.set_MUX_dis_valve(a[line])
                self.set_MXII_dis_valve(int(b[line]))
                #time.sleep(0.5) #wait 0.5 seconds for the valve to change2
            """#print(str(self.withdrawlist.row(self.withdrawlist.currentItem())))
            row2Ch=1+self.withdrawlist.row(self.withdrawlist.currentItem())
            #print(row2Ch)
            item = row2Ch
            a = []
            a.append(str(item))
            #a=item.text()  # need to select one
            #print (a) 
            #print (self.CurrCh)
            if int(a[line])  == self.CurrCh: #Do you have selected a channel?
               pass 
            else:
                #board.digital[12].write(0) #3/2 valve on coil
                #self.set_MUX_dis_valve(a[line])
                self.set_MXII_dis_valve(int(a[line]))
                #time.sleep(0.5) #wait 0.5 seconds for the valve to change2 """
        self.getchannel()
        self.displaychannel()
        return
    
    def reset(self):
        instruction = ClearWithdrawVolume + CarriageReturn
        ser.write(instruction.encode())
        instruction = ClearInfuseVolume + CarriageReturn
        ser.write(instruction.encode())
        #ser.read(size=15)
        if not self.work:
            self.printandshow("Volume reset")
        return
    
    def Frun(self, direction, SelectedRate):
        instruction = Volume + self.Volume.text() + ' ml' + CarriageReturn
        ser.write(instruction.encode())
        instruction = InfuseRate + SelectedRate + ' ml/min' + CarriageReturn
        ser.write(instruction.encode())
        instruction = WithdrawRate + SelectedRate + ' ml/min' + CarriageReturn
        ser.write(instruction.encode())
        instruction = direction + CarriageReturn
        ser.write(instruction.encode())
        if self.Wire1.isChecked():
            #row2Ch=1+self.withdrawlist.row(self.withdrawlist.currentItem())
            Ch2row = self.CurrCh - 1
            #print("text: ",Ch2row)
            #print("text2: ",row2txt2)
            if direction == Withdraw:
                row2txt = self.withdrawlist.item(Ch2row).text() #for withdrawlist. If error, check that MUX is connected. To do so, print("text: ",Ch2row) (three lines above. If answer is -1, MUX is not recognized)
                txt = self.clock() +' Withdrawing ' + self.Volume.text() + \
                    ' ml from channel ' + row2txt+' at ' + SelectedRate + ' ml/min'
                self.printandshow(txt)
            else:
                row2txt2 = self.CleanLinelist.item(Ch2row).text() #for infuselist.  If error, check that MUX is connected.To do so, print("text: ",Ch2row) (some lines above. If answer is -1, MUX is not recognized)
                txt = self.clock() +' Infusing ' + self.Volume.text() + \
                    ' ml to channel '+ row2txt2 + ' at ' + SelectedRate + ' ml/min'
                self.printandshow(txt)
        else:
            if direction == Withdraw:
                txt = self.clock() +' Withdrawing ' + self.Volume.text() + \
                    ' ml from Buffer at ' + SelectedRate + ' ml/min'
                self.printandshow(txt)
            else:
                txt = self.clock() +' Infusing ' + self.Volume.text() + \
                    ' ml from Buffer at ' + SelectedRate + ' ml/min'
                self.printandshow(txt)
        return
    
    def FExhaust(self):
        print('Doing nothing...')
        """
        if self.Wire1.isChecked():
            self.Wire1.setStyleSheet("background-color : green") #set valve ON
            valve_state=(c_int32*16)(0)
            for i in range (0 ,16): #set valves (from 1 to 16) ON, in future it can be modified
                valve_state[i]=c_int32(1)
                #print ('[',i,']:',valve_state[i])
            error2=MUX_Set_all_valves(Instr_ID.value, valve_state, 16)
            
            txt= self.clock()+' Wire 1 Turned ON '
            self.printandshow(txt)

            #board.digital[2].write(1) #3/2 valve on blocking outlet and opening exhaust
        else:
            self.Wire1.setStyleSheet("background-color : White") #set valve OFF
            valve_state=(c_int32*16)(0)
            for i in range (0 ,16): #set valves (from 1 to 16) off, in future it can be modified
                valve_state[i]=c_int32(0)
                #print ('[',i,']:',valve_state[i])
            error2=MUX_Set_all_valves(Instr_ID.value, valve_state, 16)
            txt= self.clock()+' Wire 1 Turned OFF '
            self.printandshow(txt)
            #board.digital[2].write(0) #3/2 valve on blocking outlet and opening exhaust
        self.displaychannel()
        """
        return
            
    def FLed(self):
        if self.BLed.isChecked():
            self.BLed.setStyleSheet("background-color : green")
            # board.digital[4].write(1) #
            print('LED is ON')
        else:
            self.BLed.setStyleSheet("background-color : White")
            # board.digital[4].write(0) #"""
            print('LED is OFF')
        return
        
    def WriteEvent(self):
        txt = ".\n" + self.clock() + " ######  " + self.Eventline.text() + "\n ."
        time.sleep(0.01)
        self.Eventline.clear()
        self.printandshow(txt)
        return
        
    def Framp(self):
        self.withdraw = False
        self.work = True # to break/stop CleanLinethread
        self.x = threading.Thread(target = self.F1ramp)
        self.x.start()
        return
        
    def F1ramp(self):
        self.withdraw = False
        self.work = True #to start CleanLinethread
        # 0 means it is the first selected channel in the selected list
        self.ChannelSelection('Infuse', 0) 
        txt = self.clock() + ' Ramp from ' + self.IRate.text() + \
            ' ml/min to ' + self.FinalRate.text() + ' ml/min in ' + \
            self.Ramptime.text() + ' s ' + ' at channel' + str(self.CurrCh)
        self.printandshow(txt)        
        self.Frunramp(self.IRate.text(), self.FinalRate.text())
        if self.work == True:
            self.Frun(Infuse, self.FinalRate.text())
        return        
        
    def Frunramp(self, InitialRate, FinalRate):
        if self.work == True:
            instruction = Ramp + InitialRate + ' ml/min ' + FinalRate + \
                ' ml/min ' + self.Ramptime.text() + CarriageReturn
            ser.write(instruction.encode())
            instruction = Infuse + CarriageReturn
            ser.write(instruction.encode())
            time.sleep(float(self.Ramptime.text()))    
        return
    
    def FPulse(self):
        self.withdraw = False
        self.work = True # to break/stop CleanLinethread
        self.x = threading.Thread(target = self.F1Pulse)
        self.x.start()
        return
        
    def F1Pulse(self):
        self.ChannelSelection('Infuse',0)  
        txt = self.clock() + ' Pulse from ' + self.IRate.text() + \
            ' ml/min to ' + self.FinalRate.text() + ' ml/min in ' + \
            self.Ramptime.text() + ' s (and back)' + ' at channel' + str(self.CurrCh)
        self.printandshow(txt)
        self.Frunramp(self.IRate.text(), self.FinalRate.text())
        self.Frunramp(self.FinalRate.text(), self.IRate.text())
        if self.work == True:       
            self.Frun(Infuse, self.IRate.text())
        return
            
    def FInfuse(self):
        self.dir = True
        self.withdraw = False
        self.work = False # to break/stop CleanLinethread
        # always going to select the first selected of the right list  
        self.ChannelSelection('Infuse', 0)
        self.Frun(Infuse ,self.IRate.text())
        #ser.read(size=30)
        return

    def FWithdraw(self):
        self.x = threading.Thread(target = self.F1Withdraw)
        self.x.start()
        return
    
    def F1Withdraw(self):
        self.dir= False
        self.withdraw = True
        self.work = False # to break/stop CleanLinethread
        if self.withdraw == True:
            # 0 means it is the first selected channel in the selected list
            self.ChannelSelection('Withdraw', 0)
            self.Frun(Withdraw, self.WRate.text())
            #ser.read(size=30)
            # Wait the specific time + 2 s buffer
            Tw = float(self.Volume.text())/float(self.WRate.text())*60 + 2
            time.sleep(Tw)
            if self.withdraw == True:
                txt = self.clock() + ' Withdraw Finished'
                self.printandshow(txt)
        return
        
    def FStop(self):
        self.withdraw = False
        self.work = False # to break/stop CleanLinethread
        instruction = Stop + CarriageReturn
        ser.write(instruction.encode())
        ser.reset_output_buffer()
        ser.reset_input_buffer()
        #print(bufferbytes)
        #ser.read(bufferbytes)
        if self.dir:
            instruction = infusedVolume + CarriageReturn
            ser.write(instruction.encode())
            time.sleep(0.1)
            ResponseV = str(ser.read(size = 20))
            pattern = r'\b(?!n00\d+)\d+\b'
            # Search for the numbers in the text, excluding the 00
            matches = re.findall(pattern, ResponseV)
            units = re.findall('.l', ResponseV) # point is to enable variation between micro and mili liter
            #print (len(matches),units,matches, ResponseV)
            if len(matches) < 2 or len(units) < 1:
                pass
            else:
                txt = self.clock() + " Flow stopped: " + 'Infused Volume = ' + \
                    str(matches[0] + '.' + matches[1]) + ' ' + str(units[0])
                self.printandshow(txt)
               #print ('Infused Volume = ' + str(matches[0]+'.'+matches[1])+' '+str(units[0]))
        else:
            instruction = withrawdVolume + CarriageReturn
            ser.write(instruction.encode())
            time.sleep(0.1)
            ResponseV=str(ser.read(size = 20))
            pattern = r'\b(?!n00\d+)\d+\b'
            # Search for the numbers in the text, excluding the 00
            matches = re.findall(pattern, ResponseV)
            units = re.findall('.l', ResponseV)
            #print (len(matches),units,matches, ResponseV)
            if len(matches) < 2 or len(units) < 1:
                pass
            else:
                txt = self.clock() + " Flow stopped: " + 'Withdrawn Volume = ' + \
                    str(matches[0] + '.' + matches[1]) + ' ' + str(units[0])
                self.printandshow(txt)
            #print ('Withdrawn Volume = ' + str(matches[0]+'.'+matches[1])+' '+str(units[0]))
        return
    
    def printandshow(self, txt):
        print(txt)
        self.f = open(self.filepath, "a")
        self.f.write(txt + "\n")
        self.f.close()
        if len(txt) > 41:
            space_index = txt.rfind(" ", 28, 40)
            if space_index == -1:
                space_index = 39
                txt1 = txt[:space_index]
                txt2 = txt[space_index:]
            else:                        
                txt1 = txt[:space_index]
                txt2 = txt[space_index:]
            txt3 = txt1 + "\n" + "          " + txt2
            self.CurrStatus.setText(txt3)
        else:
            self.CurrStatus.setText(txt)
        return
        
    def FCleanline(self):              
        self.x = threading.Thread(target = self.F1Cleanline)
        self.x.start()
        return

    def F1Cleanline(self):
        self.withdraw = False
        self.work = True #to start CleanLinethread
        
        precycles = (self.BrepeatCL.text())
        if precycles == '':
            precycles = '1'
        cycles = int(precycles)
        items = self.CleanLinelist.selectedItems()
        witems= self.withdrawlist.selectedItems()
        self.WRate.text()
        x = []
        y = []
        for p in range(len(witems)):
            y.append(str(self.withdrawlist.selectedItems()[p].text()))
        for i in range(len(items)):            
            x.append(str(self.CleanLinelist.selectedItems()[i].text()))
        else:
            Time = cycles*len(items)*len(witems)*(0.5 + float(self.Volume.text())/float(self.WRate.text())*60 + 2 + float(self.Volume.text())/float(self.IRate.text())*60 + 2)/60
        txt = self.clock() + ' Start Cleaning: Expected cleaning time = ' + "{:.1f}".format(Time) + ' minutes'
        self.printandshow(txt)
        o = 0
        while np.logical_and(self.work == True, o < len(witems)):
            print(str(o) + ' initial')
            for l in range (cycles):    
                j = 0   
                while np.logical_and(self.work == True, j < len(items)):
                    self.ChannelSelection('Withdraw', o)
                    rate= self.WRate.text()
                    self.reset()
                    self.dir = False
                    self.Frun(Withdraw, rate)
                    #ser.read(size=30)
                    # Wait the specific time + 4 s buffer
                    Tw = float(self.Volume.text())/float(self.WRate.text())*60 + 4
                    time.sleep(Tw)
                    if j == 0:
                        w = 0
                    stopcontrol = 0 
                    self.reset()
                    while np.logical_and(self.work == True, j == w):
                        if self.Wire1.isChecked():
                            print('Wire was checked')
                            self.ChannelSelection('Infuse', j)
                            rate = self.IRate.text()
                            self.dir = True
                            self.Frun(Infuse, rate)                 
                            #ser.read(size=30)
                            # Wait the specific time + 4 s buffer
                            Ti = float(self.Volume.text())/float(rate)*60 + 4
                            time.sleep(Ti)
                            w = w + 1
                            if (self.work == False):
                                j = 10
                        else:
                            txt = self.clock() + ' Cleaning from Buffer, Wire 1 Turned ON '
                            self.printandshow(txt)
                            self.Wire1.setChecked(True)
                            self.FExhaust()
                            self.Wire1.setStyleSheet("background-color : #DE5D83") #set valve ON
                            self.ChannelSelection('Infuse', j)
                            rate = self.IRate.text()
                            self.dir = True
                            self.Frun(Infuse, rate)                 
                            #ser.read(size=30)
                            # Wait the specific time + 4 s buffer
                            Ti = float(self.Volume.text())/float(rate)*60 + 4
                            time.sleep(Ti)
                            w = w + 1
                            self.Wire1.setChecked(False)
                            self.FExhaust()
                            self.Wire1.setStyleSheet("background-color : white")
                            txt = self.clock() + ' Wire 1 Turned OFF again '
                            self.printandshow(txt)   
                            if (self.work == False):
                                j = 10
                    j = j + 1
                    stopcontrol = 0        
                    if (self.work == False):
                        j = 10
                        stopcontrol = 1
            o = o + 1
            print(str(o) + ' final')
            if o >= len(witems) and j >= len(items) and (l == (cycles - 1)):
                #self.x.join()
                self.reset()
                txt = self.clock() + ' Cleaning done.'
                self.printandshow(txt)
        return

    def FDiscard(self):   
        self.reset()
        self.set_MXII_dis_valve(waste_channel)
        # Wait 2 s for the vale to change
        time.sleep(2)
        self.getchannel()
        self.displaychannel()
        time.sleep(0.5)
        instruction = Volume + '0.02 ml' + CarriageReturn
        ser.write(instruction.encode())
        instruction = InfuseRate + '0.4 ml/min' + CarriageReturn
        ser.write(instruction.encode())
        instruction = Infuse + CarriageReturn
        ser.write(instruction.encode())
        txt = self.clock() + ' 20 microliters discarded to Waste'
        self.printandshow(txt)
        time.sleep(3)
        self.ChannelSelection('Infuse', 0)
        self.getchannel()
        self.displaychannel()
        return

    def closeEvent(self, event):
        # Close serial port connections
        ser.close()
        valve.ser.close()
        # Close log file
        f.close()
        # MUX_Destructor(byref(Instr_ID))
        self.close()
        event.accept() # Accept the close event            
        return
            
class InputDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Set log file name:")
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Enter filename:")
        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)
        layout = QVBoxLayout()
        layout.addWidget(self.input_field)
        layout.addWidget(self.ok_button)
        self.setLayout(layout)
        return        

    def selectFolderDialog(self):
        base_path = "D:\\daily_data\\fluidic_system_logs"
        folder_path = QFileDialog.getSaveFileName(self, "Save file", base_path, \
            "Text files (*.txt);;All files (*)")
        return folder_path[0]


#################### MAIN ##########################
#################### MAIN ##########################
#################### MAIN ##########################

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = InputDialog()
    log_file_path = dialog.selectFolderDialog()
    f = open(log_file_path, "a") # append mode
    f.write("Initializing")
    f.write("Valve ready")
    f.write("Volume reset, Pump ready")
    ex = Fluidicsys(log_file_path)
    ex.show()
    sys.exit(app.exec_())
       
        
