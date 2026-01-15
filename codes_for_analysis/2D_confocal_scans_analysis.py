import sys
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QGroupBox, QGridLayout,
    QListWidget, QListWidgetItem, QSplitter, QMessageBox,
    QAbstractItemView, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QScrollArea, QCheckBox, QSpinBox, QFormLayout
)
from PyQt5.QtCore import Qt, QTimer
import matplotlib
matplotlib.use('Qt5Agg')


class ConfocalDataAnalyzer:
    """Class to handle confocal data loading and processing"""
    
    def __init__(self):
        self.folder_path = None
        self.data_loaded = False
        self.file_prefix = None
        self.scan_number = None
        
        # Data containers
        self.apd_traces = None  # Shape: (time_points, num_positions)
        self.monitor_traces = None  # Shape: (time_points, num_positions)
        self.coordinates = None  # Shape: (num_positions, 2) for (x, y)
        self.image_data = None  # Shape: (height, width)
        
        # Downsampled data containers
        self.apd_traces_downsampled = None  # Downsampled along time points (axis 0)
        self.monitor_traces_downsampled = None  # Downsampled along time points (axis 0)
        
    def load_specific_file(self, folder_path, file_prefix):
        """Load all files with a specific prefix"""
        self.folder_path = Path(folder_path)
        self.file_prefix = file_prefix
        self.data_loaded = False
        
        print(f"Loading files with prefix: {file_prefix}")
        
        try:
            # Load APD traces - shape: (time_points, num_positions)
            apd_pattern = f"{file_prefix}_confocal_apd_traces_*.npy"
            apd_files = list(self.folder_path.glob(apd_pattern))
            if apd_files:
                self.apd_traces = np.load(apd_files[0])
                print(f"Loaded APD traces from: {apd_files[0].name}")
                print(f"  Shape: {self.apd_traces.shape} (time_points × positions)")
            else:
                self.apd_traces = None
                print(f"No APD trace files found for pattern: {apd_pattern}")
            
            # Load monitor traces - shape: (time_points, num_positions)
            monitor_pattern = f"{file_prefix}_confocal_monitor_traces_*.npy"
            monitor_files = list(self.folder_path.glob(monitor_pattern))
            if monitor_files:
                self.monitor_traces = np.load(monitor_files[0])
                print(f"Loaded monitor traces from: {monitor_files[0].name}")
                print(f"  Shape: {self.monitor_traces.shape} (time_points × positions)")
            else:
                self.monitor_traces = None
                print(f"No monitor trace files found for pattern: {monitor_pattern}")
            
            # Load coordinates - shape: (num_positions, 2)
            coord_pattern = f"{file_prefix}_xy_coords_*.npy"
            coord_files = list(self.folder_path.glob(coord_pattern))
            if coord_files:
                self.coordinates = np.load(coord_files[0])
                print(f"Loaded coordinates from: {coord_files[0].name}")
                print(f"  Shape: {self.coordinates.shape} (positions × (x,y))")
            else:
                self.coordinates = None
                print(f"No coordinate files found for pattern: {coord_pattern}")
            
            # Load image - shape: (height, width)
            image_pattern = f"{file_prefix}_image_*.npy"
            image_files = list(self.folder_path.glob(image_pattern))
            if image_files:
                self.image_data = np.load(image_files[0])
                print(f"Loaded image from: {image_files[0].name}")
                print(f"  Shape: {self.image_data.shape} (height × width)")
            else:
                self.image_data = None
                print(f"No image files found for pattern: {image_pattern}")
            
            self.data_loaded = True
            return True
            
        except Exception as e:
            raise Exception(f"Error loading data for prefix {file_prefix}: {str(e)}")
    
    def downsample_traces(self, downsampling_factor=100):
        """
        Create downsampled versions of the traces by selecting every nth TIME POINT (row)
        
        For APD traces with shape (time_points, num_positions):
        - axis 0: time points (downsampled by selecting every nth row)
        - axis 1: positions (preserved - ALL positions kept)
        
        This reduces the number of time points displayed while keeping all positions.
        """
        if self.apd_traces is not None:
            # Downsample by selecting every nth row (time point)
            # Shape is (time_points, num_positions)
            original_time_points = self.apd_traces.shape[0]
            # Select every nth time point starting from 0
            self.apd_traces_downsampled = self.apd_traces[::downsampling_factor, :]
            downsampled_time_points = self.apd_traces_downsampled.shape[0]
            print(f"Downsampled APD traces along time points (axis 0):")
            print(f"  Original shape: {self.apd_traces.shape}")
            print(f"  Downsampled shape: {self.apd_traces_downsampled.shape}")
            print(f"  Factor: {downsampling_factor}x (kept {downsampled_time_points}/{original_time_points} time points)")
            print(f"  Positions preserved: {self.apd_traces.shape[1]}")
        
        if self.monitor_traces is not None:
            # Downsample by selecting every nth row (time point)
            # Shape is (time_points, num_positions)
            original_time_points = self.monitor_traces.shape[0]
            self.monitor_traces_downsampled = self.monitor_traces[::downsampling_factor, :]
            downsampled_time_points = self.monitor_traces_downsampled.shape[0]
            print(f"Downsampled monitor traces along time points (axis 0):")
            print(f"  Original shape: {self.monitor_traces.shape}")
            print(f"  Downsampled shape: {self.monitor_traces_downsampled.shape}")
            print(f"  Factor: {downsampling_factor}x (kept {downsampled_time_points}/{original_time_points} time points)")
            print(f"  Positions preserved: {self.monitor_traces.shape[1]}")
    
    def calculate_statistics(self):
        """Calculate mean, std, and SNR for APD traces"""
        if self.apd_traces is None:
            return None, None, None
        
        # Calculate statistics for each trace (each column)
        # axis=0 means average over time (rows), giving one value per position (column)
        means = np.mean(self.apd_traces, axis=0)
        stds = np.std(self.apd_traces, axis=0)
        snr = means / stds
        
        # Replace inf and nan values in SNR
        snr = np.nan_to_num(snr, nan=0.0, posinf=0.0, neginf=0.0)
        
        return means, stds, snr
    
    def create_2d_maps(self):
        """Create 2D maps from statistics using coordinates"""
        if self.coordinates is None or self.apd_traces is None:
            return None, None, None
        
        means, stds, snr = self.calculate_statistics()
        
        # Get unique coordinates
        unique_x = np.unique(self.coordinates[:, 0])
        unique_y = np.unique(self.coordinates[:, 1])
        
        # Create 2D grid
        mean_map = np.full((len(unique_y), len(unique_x)), np.nan)
        std_map = np.full((len(unique_y), len(unique_x)), np.nan)
        snr_map = np.full((len(unique_y), len(unique_x)), np.nan)
        
        # Map values to grid
        coord_dict = {}
        for i, (x, y) in enumerate(self.coordinates):
            coord_dict[(x, y)] = i
        
        for i, x in enumerate(unique_x):
            for j, y in enumerate(unique_y):
                if (x, y) in coord_dict:
                    idx = coord_dict[(x, y)]
                    mean_map[j, i] = means[idx]
                    std_map[j, i] = stds[idx]
                    snr_map[j, i] = snr[idx]
        
        return mean_map, std_map, snr_map


class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for embedding plots in PyQt"""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
    
    def clear(self):
        self.axes.clear()
        self.draw()


class FileBrowser(QWidget):
    """Widget for browsing and selecting files"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.available_scans = []
        
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Folder selection
        folder_group = QGroupBox("Folder Selection")
        folder_layout = QVBoxLayout()
        
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setStyleSheet("border: 1px solid gray; padding: 5px;")
        
        browse_btn = QPushButton("Browse Folder")
        browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(QLabel("Data Folder:"))
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(browse_btn)
        folder_group.setLayout(folder_layout)
        
        layout.addWidget(folder_group)
        
        # File list
        file_group = QGroupBox("Available Scans")
        file_layout = QVBoxLayout()
        
        self.file_list = QTreeWidget()
        self.file_list.setHeaderLabels(["Scan ID", "APD Traces", "Monitor", "Coordinates", "Image"])
        self.file_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.file_list.setAlternatingRowColors(True)
        self.file_list.header().setStretchLastSection(False)
        self.file_list.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_list.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_list.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.file_list.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.file_list.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        file_layout.addWidget(self.file_list)
        file_group.setLayout(file_layout)
        
        layout.addWidget(file_group, 1)
        
        # Selected scan info
        info_group = QGroupBox("Selected Scan Information")
        info_layout = QVBoxLayout()
        
        self.selected_scan_label = QLabel("No scan selected")
        self.selected_scan_label.setStyleSheet("font-weight: bold; padding: 5px;")
        
        self.scan_info_label = QLabel("")
        self.scan_info_label.setWordWrap(True)
        self.scan_info_label.setStyleSheet("padding: 5px;")
        
        info_layout.addWidget(QLabel("Selected Scan:"))
        info_layout.addWidget(self.selected_scan_label)
        info_layout.addWidget(QLabel("Available Files:"))
        info_layout.addWidget(self.scan_info_label)
        info_group.setLayout(info_layout)
        
        layout.addWidget(info_group)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Data Folder")
        if folder:
            self.folder_label.setText(folder)
            self.scan_files(folder)
    
    def scan_files(self, folder_path):
        """Scan folder for available confocal scan files"""
        self.file_list.clear()
        self.available_scans = []
        
        folder = Path(folder_path)
        npy_files = list(folder.glob("*.npy"))
        
        if not npy_files:
            self.selected_scan_label.setText("No .npy files found")
            return
        
        # Extract unique scan prefixes
        scan_prefixes = set()
        for file in npy_files:
            filename = file.stem
            # Try to extract scan prefix (e.g., "A1" from "A1_confocal_apd_traces_0001")
            parts = filename.split('_')
            if len(parts) >= 3:
                scan_prefix = parts[0]
                if scan_prefix and any(c.isalpha() for c in scan_prefix) and any(c.isdigit() for c in scan_prefix):
                    scan_prefixes.add(scan_prefix)
        
        # Sort scan prefixes
        scan_prefixes = sorted(list(scan_prefixes), key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
        
        # Populate file list
        for prefix in scan_prefixes:
            # Check which files are available for this prefix
            apd_files = list(folder.glob(f"{prefix}_confocal_apd_traces_*.npy"))
            monitor_files = list(folder.glob(f"{prefix}_confocal_monitor_traces_*.npy"))
            coord_files = list(folder.glob(f"{prefix}_xy_coords_*.npy"))
            image_files = list(folder.glob(f"{prefix}_image_*.npy"))
            
            # Create tree widget item
            item = QTreeWidgetItem(self.file_list)
            item.setText(0, prefix)
            item.setText(1, "✓" if apd_files else "✗")
            item.setText(2, "✓" if monitor_files else "✗")
            item.setText(3, "✓" if coord_files else "✗")
            item.setText(4, "✓" if image_files else "✗")
            
            # Store the prefix in the item
            item.setData(0, Qt.UserRole, prefix)
            
            self.available_scans.append({
                'prefix': prefix,
                'apd': apd_files[0] if apd_files else None,
                'monitor': monitor_files[0] if monitor_files else None,
                'coords': coord_files[0] if coord_files else None,
                'image': image_files[0] if image_files else None
            })
        
        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.selected_scan_label.setText(f"Found {len(scan_prefixes)} scan(s)")
    
    def on_selection_changed(self):
        """Handle selection change in file list"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        prefix = item.data(0, Qt.UserRole)
        
        folder = Path(self.folder_label.text())
        
        # Get file information
        apd_files = list(folder.glob(f"{prefix}_confocal_apd_traces_*.npy"))
        monitor_files = list(folder.glob(f"{prefix}_confocal_monitor_traces_*.npy"))
        coord_files = list(folder.glob(f"{prefix}_xy_coords_*.npy"))
        image_files = list(folder.glob(f"{prefix}_image_*.npy"))
        
        self.selected_scan_label.setText(f"Scan: {prefix}")
        
        info_text = []
        if apd_files:
            info_text.append(f"• APD traces: {apd_files[0].name}")
        if monitor_files:
            info_text.append(f"• Monitor traces: {monitor_files[0].name}")
        if coord_files:
            info_text.append(f"• Coordinates: {coord_files[0].name}")
        if image_files:
            info_text.append(f"• Image: {image_files[0].name}")
        
        self.scan_info_label.setText("\n".join(info_text) if info_text else "No complete scan data found")
    
    def get_selected_scan(self):
        """Get the currently selected scan prefix"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return None
        
        item = selected_items[0]
        return item.data(0, Qt.UserRole)
    
    def get_folder_path(self):
        """Get the current folder path"""
        return self.folder_label.text()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.analyzer = ConfocalDataAnalyzer()
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('2D Confocal Scan Analyzer')
        self.setGeometry(100, 100, 1600, 900)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: File browser
        self.file_browser = FileBrowser()
        splitter.addWidget(self.file_browser)
        
        # Right panel: Plots
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Control panel with downsampling options
        control_panel = QGroupBox("Plot Controls")
        control_layout = QVBoxLayout()
        
        # First row: Load/Refresh buttons
        button_layout = QHBoxLayout()
        
        self.load_btn = QPushButton("Load Selected Scan")
        self.load_btn.clicked.connect(self.load_selected_scan)
        self.load_btn.setEnabled(False)
        
        self.refresh_btn = QPushButton("Refresh Plots")
        self.refresh_btn.clicked.connect(self.refresh_plots)
        self.refresh_btn.setEnabled(False)
        
        button_layout.addWidget(self.load_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        
        control_layout.addLayout(button_layout)
        
        # Second row: Downsampling options
        downsample_layout = QHBoxLayout()
        
        # Downsampling checkbox
        self.downsample_checkbox = QCheckBox("Downsample Time Points for Display")
        self.downsample_checkbox.setChecked(True)  # Default to True as requested
        self.downsample_checkbox.stateChanged.connect(self.on_downsample_changed)
        
        # Downsampling factor input
        downsample_factor_layout = QHBoxLayout()
        downsample_factor_layout.addWidget(QLabel("Downsampling Factor:"))
        self.downsample_spinbox = QSpinBox()
        self.downsample_spinbox.setMinimum(1)
        self.downsample_spinbox.setMaximum(1000)
        self.downsample_spinbox.setValue(100)  # Default to 100 as requested
        self.downsample_spinbox.setSuffix("x")
        self.downsample_spinbox.setEnabled(self.downsample_checkbox.isChecked())
        downsample_factor_layout.addWidget(self.downsample_spinbox)
        downsample_factor_layout.addStretch()
        
        downsample_layout.addWidget(self.downsample_checkbox)
        downsample_layout.addLayout(downsample_factor_layout)
        
        control_layout.addLayout(downsample_layout)
        
        # Add explanation label
        explanation_label = QLabel(
            "Downsampling selects every nth TIME POINT for display while keeping ALL positions. "
            "Statistics calculations always use full time resolution for accuracy."
        )
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet("font-style: italic; color: #666; padding: 5px;")
        control_layout.addWidget(explanation_label)
        
        # Third row: Status
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("border: 1px solid gray; padding: 5px;")
        
        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(self.status_label, 1)
        
        control_layout.addLayout(status_layout)
        
        control_panel.setLayout(control_layout)
        right_layout.addWidget(control_panel)
        
        # Create a scroll area for plots
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.plots_layout = QGridLayout(scroll_content)
        
        # Initialize plot canvases
        self.plot_canvases = {}
        plot_titles = [
            "APD Intensity Traces",
            "Monitor Intensity Traces",
            "2D Confocal Scan Image",
            "Mean APD Intensity Map",
            "Std Dev APD Intensity Map",
            "APD SNR Map"
        ]
        
        for i, title in enumerate(plot_titles):
            canvas = MatplotlibCanvas(width=4, height=3.5)
            self.plot_canvases[title] = canvas
            # Create a group box for each plot
            plot_box = QGroupBox(title)
            plot_box_layout = QVBoxLayout()
            plot_box_layout.addWidget(canvas)
            plot_box.setLayout(plot_box_layout)
            
            # Arrange in grid: 2 columns
            row = i // 2
            col = i % 2
            self.plots_layout.addWidget(plot_box, row, col)
        
        scroll_area.setWidget(scroll_content)
        right_layout.addWidget(scroll_area, 1)
        
        splitter.addWidget(right_panel)
        
        # Set initial splitter sizes
        splitter.setSizes([400, 1200])
        
        main_layout.addWidget(splitter)
        
        # Connect file browser signals
        self.file_browser.file_list.itemSelectionChanged.connect(self.on_scan_selected)
    
    def on_downsample_changed(self):
        """Enable/disable downsampling factor input based on checkbox"""
        self.downsample_spinbox.setEnabled(self.downsample_checkbox.isChecked())
    
    def on_scan_selected(self):
        """Enable load button when a scan is selected"""
        selected_scan = self.file_browser.get_selected_scan()
        self.load_btn.setEnabled(selected_scan is not None)
    
    def load_selected_scan(self):
        """Load the currently selected scan"""
        folder_path = self.file_browser.get_folder_path()
        selected_scan = self.file_browser.get_selected_scan()
        
        if not folder_path or not selected_scan:
            return
        
        try:
            self.status_label.setText("Loading data...")
            QApplication.processEvents()
            
            success = self.analyzer.load_specific_file(folder_path, selected_scan)
            if success:
                # Apply downsampling if enabled
                if self.downsample_checkbox.isChecked():
                    factor = self.downsample_spinbox.value()
                    self.status_label.setText(f"Loading data and downsampling time points {factor}x...")
                    QApplication.processEvents()
                    self.analyzer.downsample_traces(factor)
                
                self.status_label.setText(f"Loaded scan: {selected_scan}")
                self.refresh_btn.setEnabled(True)
                self.generate_all_plots()
            else:
                self.status_label.setText("Failed to load data")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{str(e)}")
            self.status_label.setText("Error loading data")
    
    def refresh_plots(self):
        """Refresh all plots with current data"""
        # Reapply downsampling if enabled
        if self.downsample_checkbox.isChecked():
            factor = self.downsample_spinbox.value()
            self.analyzer.downsample_traces(factor)
        
        self.generate_all_plots()
        self.status_label.setText("Plots refreshed")
    
    def generate_all_plots(self):
        """Generate all the requested plots"""
        if not self.analyzer.data_loaded:
            return
        
        try:
            # Clear all plots first
            for canvas in self.plot_canvases.values():
                canvas.clear()
            
            # Check if downsampling is enabled
            use_downsampled = self.downsample_checkbox.isChecked()
            factor = self.downsample_spinbox.value() if use_downsampled else 1
            
            # 1. APD Intensity Traces
            if self.analyzer.apd_traces is not None:
                # Use downsampled data if available and enabled
                if use_downsampled and self.analyzer.apd_traces_downsampled is not None:
                    data_to_plot = self.analyzer.apd_traces_downsampled
                    original_time_points = self.analyzer.apd_traces.shape[0]
                    downsampled_time_points = self.analyzer.apd_traces_downsampled.shape[0]
                    num_positions = self.analyzer.apd_traces.shape[1]
                    downsampled_info = f" (Time points downsampled {factor}x: {downsampled_time_points}/{original_time_points} points)"
                else:
                    data_to_plot = self.analyzer.apd_traces
                    original_time_points = self.analyzer.apd_traces.shape[0]
                    num_positions = self.analyzer.apd_traces.shape[1]
                    downsampled_info = ""
                
                self.plot_traces(
                    self.plot_canvases["APD Intensity Traces"],
                    data_to_plot,
                    f"APD Intensity Traces (Scan: {self.analyzer.file_prefix}){downsampled_info}",
                    "Time Points",
                    "Normalized Intensity",
                    num_positions,
                    original_time_points,
                    use_downsampled,
                    factor
                )
            
            # 2. Monitor Intensity Traces
            if self.analyzer.monitor_traces is not None:
                # Use downsampled data if available and enabled
                if use_downsampled and self.analyzer.monitor_traces_downsampled is not None:
                    data_to_plot = self.analyzer.monitor_traces_downsampled
                    original_time_points = self.analyzer.monitor_traces.shape[0]
                    downsampled_time_points = self.analyzer.monitor_traces_downsampled.shape[0]
                    num_positions = self.analyzer.monitor_traces.shape[1]
                    downsampled_info = f" (Time points downsampled {factor}x: {downsampled_time_points}/{original_time_points} points)"
                else:
                    data_to_plot = self.analyzer.monitor_traces
                    original_time_points = self.analyzer.monitor_traces.shape[0]
                    num_positions = self.analyzer.monitor_traces.shape[1]
                    downsampled_info = ""
                
                self.plot_traces(
                    self.plot_canvases["Monitor Intensity Traces"],
                    data_to_plot,
                    f"Monitor Intensity Traces (Scan: {self.analyzer.file_prefix}){downsampled_info}",
                    "Time Points",
                    "Normalized Intensity",
                    num_positions,
                    original_time_points,
                    use_downsampled,
                    factor
                )
            
            # 3. 2D Confocal Scan Image
            if self.analyzer.image_data is not None:
                self.plot_2d_image(
                    self.plot_canvases["2D Confocal Scan Image"],
                    self.analyzer.image_data,
                    f"2D Confocal Scan (Scan: {self.analyzer.file_prefix})",
                    "X Position",
                    "Y Position"
                )
            
            # 4-6. Statistics maps (NOT downsampled - use full data for statistics)
            if self.analyzer.apd_traces is not None and self.analyzer.coordinates is not None:
                mean_map, std_map, snr_map = self.analyzer.create_2d_maps()
                
                if mean_map is not None:
                    self.plot_2d_map(
                        self.plot_canvases["Mean APD Intensity Map"],
                        mean_map,
                        f"Mean APD Intensity (Scan: {self.analyzer.file_prefix})",
                        "X Position",
                        "Y Position",
                        cmap='viridis'
                    )
                
                if std_map is not None:
                    self.plot_2d_map(
                        self.plot_canvases["Std Dev APD Intensity Map"],
                        std_map,
                        f"Std Dev APD Intensity (Scan: {self.analyzer.file_prefix})",
                        "X Position",
                        "Y Position",
                        cmap='plasma'
                    )
                
                if snr_map is not None:
                    self.plot_2d_map(
                        self.plot_canvases["APD SNR Map"],
                        snr_map,
                        f"APD SNR (Mean/Std Dev) (Scan: {self.analyzer.file_prefix})",
                        "X Position",
                        "Y Position",
                        cmap='coolwarm'
                    )
            
            QTimer.singleShot(100, lambda: self.status_label.setText("All plots generated"))
            
        except Exception as e:
            QMessageBox.warning(self, "Plot Error", f"Error generating plots:\n{str(e)}")
            self.status_label.setText("Error generating plots")
    
    def plot_traces(self, canvas, data, title, xlabel, ylabel, num_positions, original_time_points, is_downsampled=False, factor=1):
        """Plot multiple traces"""
        canvas.axes.clear()
        
        # Create time axis based on number of time points in the data
        time_axis = np.arange(data.shape[0])
        
        # Limit to plotting max 50 positions to avoid overcrowding
        max_positions_to_plot = 50
        positions_to_plot = min(num_positions, max_positions_to_plot)
        
        # Plot traces for the first N positions
        for i in range(positions_to_plot):
            trace = data[:, i]
            if np.max(trace) - np.min(trace) > 0:
                trace_norm = (trace - np.min(trace)) / (np.max(trace) - np.min(trace))
                # Add vertical offset for each trace
                canvas.axes.plot(time_axis, trace_norm + i*0.1, linewidth=0.5, alpha=0.7)
        
        canvas.axes.set_title(title)
        canvas.axes.set_xlabel(xlabel)
        canvas.axes.set_ylabel(ylabel)
        canvas.axes.grid(True, alpha=0.3)
        
        # Add legend with information
        if is_downsampled:
            current_time_points = data.shape[0]
            info_text = f"Total positions: {num_positions}\n"
            info_text += f"Displayed positions: {positions_to_plot}\n"
            info_text += f"Original time points: {original_time_points}\n"
            info_text += f"Displayed time points: {current_time_points} ({factor}x downsampled)"
        else:
            info_text = f"Positions: {num_positions}\n"
            info_text += f"Displayed positions: {positions_to_plot}\n"
            info_text += f"Time points: {original_time_points}"
        
        if positions_to_plot < num_positions:
            info_text += f"\n(Showing first {positions_to_plot} positions)"
        
        canvas.axes.text(0.02, 0.98, info_text, 
                        transform=canvas.axes.transAxes,
                        verticalalignment='top',
                        fontsize=8,
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        canvas.fig.tight_layout()
        canvas.draw()
    
    def plot_2d_image(self, canvas, image, title, xlabel, ylabel):
        """Plot 2D image"""
        canvas.axes.clear()
        
        im = canvas.axes.imshow(image, cmap='gray', aspect='auto', 
                                interpolation='nearest', origin='lower')
        cbar = canvas.fig.colorbar(im, ax=canvas.axes)
        cbar.set_label('Intensity')
        canvas.axes.set_title(title)
        canvas.axes.set_xlabel(xlabel)
        canvas.axes.set_ylabel(ylabel)
        canvas.fig.tight_layout()
        canvas.draw()
    
    def plot_2d_map(self, canvas, data, title, xlabel, ylabel, cmap='viridis'):
        """Plot 2D map with colorbar"""
        canvas.axes.clear()
        
        # Mask NaN values
        data_masked = np.ma.array(data, mask=np.isnan(data))
        
        im = canvas.axes.imshow(data_masked, cmap=cmap, aspect='auto', 
                                interpolation='nearest', origin='lower')
        cbar = canvas.fig.colorbar(im, ax=canvas.axes)
        
        # Set appropriate colorbar label based on plot type
        if "Mean" in title:
            cbar.set_label('Mean Intensity')
        elif "Std" in title:
            cbar.set_label('Standard Deviation')
        elif "SNR" in title:
            cbar.set_label('SNR')
        
        canvas.axes.set_title(title)
        canvas.axes.set_xlabel(xlabel)
        canvas.axes.set_ylabel(ylabel)
        canvas.fig.tight_layout()
        canvas.draw()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()