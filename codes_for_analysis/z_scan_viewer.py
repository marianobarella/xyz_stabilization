import sys
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QListWidget, QFileDialog, 
                             QLabel, QSplitter, QMessageBox, QTabWidget,
                             QCheckBox, QLineEdit, QFormLayout, QGroupBox)
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import colors
from mpl_toolkits.axes_grid1 import make_axes_locatable
import re

class NPYViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NPY File Viewer")
        self.setGeometry(100, 100, 1600, 800)  # Increased width to 1600
        
        self.current_directory = ""
        self.current_data = None
        self.current_traces_data = None
        self.colorbar = None  # Store colorbar reference
        
        self.init_ui()
        
    def init_ui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for file operations and settings
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(400)  # Slightly wider to accommodate new controls
        
        # Directory selection
        self.dir_label = QLabel("No directory selected")
        self.open_dir_btn = QPushButton("Open Directory")
        self.open_dir_btn.clicked.connect(self.open_directory)
        
        # Processing settings group (combining downsampling and rolling average)
        processing_group = QGroupBox("Processing Settings")
        processing_layout = QFormLayout(processing_group)
        
        # Downsampling option
        self.downsample_checkbox = QCheckBox("Enable Downsampling")
        self.downsample_checkbox.setChecked(True)  # Enabled by default
        self.downsample_checkbox.stateChanged.connect(self.on_downsample_changed)
        
        self.downsample_edit = QLineEdit("100")
        self.downsample_edit.setPlaceholderText("Downsampling factor")
        self.downsample_edit.textChanged.connect(self.update_traces_plot_if_visible)
        
        # Rolling average option
        self.rolling_avg_checkbox = QCheckBox("Enable Rolling Average")
        self.rolling_avg_checkbox.setChecked(False)
        self.rolling_avg_checkbox.stateChanged.connect(self.on_rolling_avg_changed)
        
        self.rolling_avg_edit = QLineEdit("11")
        self.rolling_avg_edit.setPlaceholderText("Window size (points)")
        self.rolling_avg_edit.textChanged.connect(self.update_traces_plot_if_visible)
        
        processing_layout.addRow(self.downsample_checkbox)
        processing_layout.addRow("Downsample Factor:", self.downsample_edit)
        processing_layout.addRow(self.rolling_avg_checkbox)
        processing_layout.addRow("Rolling Avg Window:", self.rolling_avg_edit)
        
        # Sampling frequency settings group
        sampling_group = QGroupBox("Sampling Settings")
        sampling_layout = QFormLayout(sampling_group)
        
        self.sampling_freq_edit = QLineEdit("100")
        self.sampling_freq_edit.setPlaceholderText("Sampling frequency (kHz)")
        self.sampling_freq_edit.textChanged.connect(self.update_traces_plot_if_visible)
        
        sampling_layout.addRow("Sampling Freq (kHz):", self.sampling_freq_edit)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self.load_selected_file)
        
        left_layout.addWidget(self.dir_label)
        left_layout.addWidget(self.open_dir_btn)
        left_layout.addWidget(processing_group)
        left_layout.addWidget(sampling_group)
        left_layout.addWidget(QLabel("Files:"))
        left_layout.addWidget(self.file_list)
        
        # Right panel with tabs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Tab 1: Z Scan Plots
        z_scan_tab = QWidget()
        z_scan_layout = QVBoxLayout(z_scan_tab)
        
        self.fig1 = Figure(figsize=(12, 4))  # Slightly larger figures
        self.canvas1 = FigureCanvas(self.fig1)
        self.ax1 = self.fig1.add_subplot(111)
        self.ax1.set_xlabel('Z Scan')
        self.ax1.set_ylabel('Z Intensity')
        self.ax1.grid(True)
        
        self.fig2 = Figure(figsize=(12, 4))
        self.canvas2 = FigureCanvas(self.fig2)
        self.ax2 = self.fig2.add_subplot(111)
        self.ax2.set_xlabel('Z Scan')
        self.ax2.set_ylabel('Std Dev')
        self.ax2.grid(True)
        
        z_scan_layout.addWidget(QLabel("Z Intensity vs Z Scan:"))
        z_scan_layout.addWidget(self.canvas1)
        z_scan_layout.addWidget(QLabel("Z Scan vs Std Dev:"))
        z_scan_layout.addWidget(self.canvas2)
        
        # Tab 2: Intensity Traces
        traces_tab = QWidget()
        traces_layout = QVBoxLayout(traces_tab)
        
        # Create larger figure for better visibility
        self.fig3 = Figure(figsize=(12, 8))
        self.canvas3 = FigureCanvas(self.fig3)
        self.ax3 = self.fig3.add_subplot(111)
        self.ax3.set_xlabel('Time (ms)')
        self.ax3.set_ylabel('Intensity')
        self.ax3.grid(True)
        
        traces_layout.addWidget(QLabel("Intensity Traces:"))
        traces_layout.addWidget(self.canvas3)
        
        # Add tabs to tab widget
        self.tab_widget.addTab(z_scan_tab, "Z Scan")
        self.tab_widget.addTab(traces_tab, "Intensity Traces")
        
        right_layout.addWidget(self.tab_widget)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        
    def on_downsample_changed(self, state):
        """Handle downsampling checkbox change - make exclusive with rolling average"""
        if state == Qt.Checked:
            self.rolling_avg_checkbox.setChecked(False)
        self.update_traces_plot_if_visible()
    
    def on_rolling_avg_changed(self, state):
        """Handle rolling average checkbox change - make exclusive with downsampling"""
        if state == Qt.Checked:
            self.downsample_checkbox.setChecked(False)
        self.update_traces_plot_if_visible()
        
    def open_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.current_directory = directory
            self.dir_label.setText(f"Directory: {os.path.basename(directory)}")
            self.load_file_list(directory)
    
    def load_file_list(self, directory):
        self.file_list.clear()
        
        # Patterns to match both types of files
        z_scan_pattern = re.compile(r".*_z_scan_\d{4}\.npy$")
        traces_pattern = re.compile(r".*_z_scan_traces_\d{4}\.npy$")
        
        try:
            all_files = os.listdir(directory)
            z_scan_files = [f for f in all_files if f.endswith('.npy') and z_scan_pattern.match(f)]
            traces_files = [f for f in all_files if f.endswith('.npy') and traces_pattern.match(f)]
            
            # Combine and sort files
            files = sorted(z_scan_files + traces_files)
            
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
            # Check if it's a traces file or z_scan file
            if "_z_scan_traces_" in filename:
                self.load_traces_file(filepath, filename)
            else:
                self.load_z_scan_file(filepath, filename)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading file: {str(e)}")
    
    def load_z_scan_file(self, filepath, filename):
        """Load and display Z scan data"""
        # Load the .npy file
        data = np.load(filepath)
        
        # Check if data has the expected structure (3 columns)
        if data.ndim != 2 or data.shape[1] != 3:
            QMessageBox.warning(self, "Invalid Format", 
                              "Z scan file does not contain 3 columns as expected.")
            return
        
        self.current_data = data
        self.current_traces_data = None
        self.update_z_scan_plots()
        self.tab_widget.setCurrentIndex(0)  # Switch to Z Scan tab
    
    def load_traces_file(self, filepath, filename):
        """Load and display intensity traces data"""
        # Load the .npy file
        data = np.load(filepath)
        
        # Check if data has the expected structure (2D array)
        if data.ndim != 2:
            QMessageBox.warning(self, "Invalid Format", 
                              "Traces file is not a 2D array as expected.")
            return
        
        self.current_traces_data = data
        self.current_data = None
        self.update_traces_plot()
        self.tab_widget.setCurrentIndex(1)  # Switch to Intensity Traces tab
    
    def update_z_scan_plots(self):
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
    
    def get_downsampling_factor(self):
        """Get the downsampling factor from the text field with validation"""
        try:
            factor = int(self.downsample_edit.text())
            if factor < 1:
                return 1  # Minimum factor is 1 (no downsampling)
            return factor
        except ValueError:
            return 100  # Default value if invalid input
    
    def get_rolling_avg_window(self):
        """Get the rolling average window size with validation"""
        try:
            window = int(self.rolling_avg_edit.text())
            if window < 1:
                return 1  # Minimum window size is 1
            return window
        except ValueError:
            return 11  # Default value if invalid input
    
    def get_sampling_frequency(self):
        """Get the sampling frequency with validation"""
        try:
            freq = float(self.sampling_freq_edit.text())
            if freq <= 0:
                return 100.0  # Default value if invalid
            return freq
        except ValueError:
            return 100.0  # Default value if invalid input
    
    def downsample_trace(self, trace, factor):
        """Downsample a single trace by selecting every nth point"""
        if factor <= 1:
            return trace
        return trace[::factor]
    
    def rolling_average(self, trace, window):
        """Apply rolling average to a trace"""
        if window <= 1:
            return trace
        
        # Use convolution to compute rolling average
        window_array = np.ones(window) / window
        smoothed = np.convolve(trace, window_array, mode='same')
        
        # Handle edges by using valid convolution and padding
        if len(trace) > window:
            # For the beginning and end, use smaller windows
            half_window = window // 2
            for i in range(half_window):
                smoothed[i] = np.mean(trace[:i + half_window + 1])
            for i in range(len(trace) - half_window, len(trace)):
                smoothed[i] = np.mean(trace[i - half_window:])
        
        return smoothed
    
    def update_traces_plot_if_visible(self):
        """Update traces plot only if the traces tab is currently visible"""
        if (self.tab_widget.currentIndex() == 1 and 
            self.current_traces_data is not None):
            self.update_traces_plot()
    
    def update_traces_plot(self):
        if self.current_traces_data is None:
            return
            
        # Clear previous plot
        self.ax3.clear()
        
        # Remove old colorbar if it exists
        if self.colorbar:
            try:
                self.colorbar.remove()
            except:
                pass  # If colorbar is already removed or invalid
            self.colorbar = None
        
        # Get processing settings
        downsample_enabled = self.downsample_checkbox.isChecked()
        downsample_factor = self.get_downsampling_factor()
        rolling_avg_enabled = self.rolling_avg_checkbox.isChecked()
        rolling_avg_window = self.get_rolling_avg_window()
        sampling_freq = self.get_sampling_frequency()  # in kHz
        
        # Calculate sampling period in milliseconds
        sampling_period_ms = (1.0 / sampling_freq)  # period in ms (since freq is in kHz)
        
        # Get array dimensions - columns represent traces, rows represent time points
        n_time_points = self.current_traces_data.shape[0]  # Number of time points (rows)
        n_traces = self.current_traces_data.shape[1]       # Number of traces (columns)
        
        # Create time axis in milliseconds
        time_axis_ms = np.arange(n_time_points) * sampling_period_ms
        
        # Apply processing based on user selection
        if downsample_enabled:
            # Downsample each trace (column) individually
            downsampled_traces = []
            for i in range(n_traces):
                # Extract column i (trace i) and downsample it
                trace = self.current_traces_data[:, i]
                downsampled_trace = self.downsample_trace(trace, downsample_factor)
                downsampled_traces.append(downsampled_trace)
            
            # Convert back to array and transpose so each row is a trace
            traces_data = np.array(downsampled_traces).T
            downsampled_length = traces_data.shape[0]  # Number of time points after downsampling
            processed_time_axis = np.arange(downsampled_length) * downsample_factor * sampling_period_ms
            title_suffix = f" (downsampled {downsample_factor}x, {downsampled_length} points)"
            
        elif rolling_avg_enabled:
            # Apply rolling average to each trace
            smoothed_traces = []
            for i in range(n_traces):
                trace = self.current_traces_data[:, i]
                smoothed_trace = self.rolling_average(trace, rolling_avg_window)
                smoothed_traces.append(smoothed_trace)
            
            traces_data = np.array(smoothed_traces).T
            processed_time_axis = time_axis_ms
            title_suffix = f" (rolling avg {rolling_avg_window} pts, {n_time_points} points)"
            
        else:
            # No processing - use original data
            traces_data = self.current_traces_data
            processed_time_axis = time_axis_ms
            title_suffix = f" (original, {n_time_points} points)"
        
        # Plot all traces with different colors
        for i in range(n_traces):
            # Use a colormap to get different colors for each trace
            color = plt.cm.viridis(i / max(1, n_traces - 1))
            self.ax3.plot(processed_time_axis, traces_data[:, i], 
                         color=color, alpha=0.7, linewidth=1)
        
        self.ax3.set_xlabel('Time (ms)')
        self.ax3.set_ylabel('Intensity')
        self.ax3.grid(True)
        self.ax3.set_title(f'Intensity Traces ({n_traces} traces){title_suffix}')
        
        # Add a colorbar to indicate trace order (only if multiple traces)
        if n_traces > 1:
            # Create a normalized color map
            norm = colors.Normalize(vmin=0, vmax=n_traces-1)
            sm = plt.cm.ScalarMappable(cmap='viridis', norm=norm)
            sm.set_array([])
            
            # Create colorbar using axes_grid1 for better layout control
            divider = make_axes_locatable(self.ax3)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            self.colorbar = self.fig3.colorbar(sm, cax=cax)
            self.colorbar.set_label('Trace Index')
        
        # Adjust layout
        self.fig3.tight_layout()
        
        # Refresh canvas
        self.canvas3.draw()

def main():
    app = QApplication(sys.argv)
    viewer = NPYViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()