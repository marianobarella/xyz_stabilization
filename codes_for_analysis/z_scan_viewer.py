import sys
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QListWidget, QFileDialog, 
                             QLabel, QSplitter, QMessageBox)
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import re

class NPYViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NPY File Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_directory = ""
        self.current_data = None
        
        self.init_ui()
        
    def init_ui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for file operations
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(300)
        
        # Directory selection
        self.dir_label = QLabel("No directory selected")
        self.open_dir_btn = QPushButton("Open Directory")
        self.open_dir_btn.clicked.connect(self.open_directory)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self.load_selected_file)
        
        left_layout.addWidget(self.dir_label)
        left_layout.addWidget(self.open_dir_btn)
        left_layout.addWidget(QLabel("Files:"))
        left_layout.addWidget(self.file_list)
        
        # Right panel for plots
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create matplotlib figures
        self.fig1 = Figure(figsize=(10, 4))
        self.canvas1 = FigureCanvas(self.fig1)
        self.ax1 = self.fig1.add_subplot(111)
        self.ax1.set_xlabel('Z Scan')
        self.ax1.set_ylabel('Z Intensity')
        self.ax1.grid(True)
        
        self.fig2 = Figure(figsize=(10, 4))
        self.canvas2 = FigureCanvas(self.fig2)
        self.ax2 = self.fig2.add_subplot(111)
        self.ax2.set_xlabel('Z Scan')
        self.ax2.set_ylabel('Std Dev')
        self.ax2.grid(True)
        
        right_layout.addWidget(QLabel("Z Intensity vs Z Scan:"))
        right_layout.addWidget(self.canvas1)
        right_layout.addWidget(QLabel("Z Scan vs Std Dev:"))
        right_layout.addWidget(self.canvas2)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        
    def open_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.current_directory = directory
            self.dir_label.setText(f"Directory: {os.path.basename(directory)}")
            self.load_file_list(directory)
    
    def load_file_list(self, directory):
        self.file_list.clear()
        
        # Pattern to match files with "_z_scan_%04d" pattern
        pattern = re.compile(r".*_z_scan_\d{4}\.npy$")
        
        try:
            files = [f for f in os.listdir(directory) 
                    if f.endswith('.npy') and pattern.match(f)]
            files.sort()  # Sort files for better organization
            
            for file in files:
                self.file_list.addItem(file)
                
            if not files:
                QMessageBox.information(self, "No Files", 
                                      "No matching .npy files found in the selected directory.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reading directory: {str(e)}")
    
    def load_selected_file(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
            
        filename = selected_items[0].text()
        filepath = os.path.join(self.current_directory, filename)
        
        try:
            # Load the .npy file
            data = np.load(filepath)
            
            # Check if data has the expected structure (3 columns)
            if data.ndim != 2 or data.shape[1] != 3:
                QMessageBox.warning(self, "Invalid Format", 
                                  "File does not contain 3 columns as expected.")
                return
            
            self.current_data = data
            self.update_plots()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading file: {str(e)}")
    
    def update_plots(self):
        if self.current_data is None:
            return
            
        # Extract columns
        z_scan = self.current_data[:, 0]
        z_intensity = self.current_data[:, 1]
        std_dev = self.current_data[:, 2]
        
        # Clear previous plots
        self.ax1.clear()
        self.ax2.clear()
        
        # Plot 1: Z Intensity vs Z Scan
        self.ax1.plot(z_scan, z_intensity, 'b-', linewidth=2)
        self.ax1.set_xlabel('Z Scan')
        self.ax1.set_ylabel('Z Intensity')
        self.ax1.grid(True)
        self.ax1.set_title('Z Intensity vs Z Scan')
        
        # Plot 2: Z Scan vs Std Dev
        self.ax2.plot(z_scan, std_dev, 'r-', linewidth=2)
        self.ax2.set_xlabel('Z Scan')
        self.ax2.set_ylabel('Std Dev')
        self.ax2.grid(True)
        self.ax2.set_title('Z Scan vs Standard Deviation')
        
        # Refresh canvases
        self.canvas1.draw()
        self.canvas2.draw()

def main():
    app = QApplication(sys.argv)
    viewer = NPYViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()