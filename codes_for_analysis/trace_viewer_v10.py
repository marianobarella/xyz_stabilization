import sys
import os
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QPushButton, QLabel, QLineEdit, QHBoxLayout,
    QScrollArea, QTextEdit, QListWidget, QComboBox, QMessageBox, QTabWidget
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.widgets import RectangleSelector
from matplotlib.patches import Rectangle
import re
from datetime import datetime


##############################################################################
# Self-contained Gaussian time-domain filter.
# Same math as signal_filtering_functions.gaussian_filter_time_domain:
#   sigma = sample_rate / (2*pi*cutoff_freq)
#   window = 6*sigma (forced odd), normalized Gaussian, convolution mode='same'
# Reimplemented with numpy so the GUI has no external filter dependency and
# does not rely on scipy.signal.gaussian (removed in recent SciPy versions).
##############################################################################
def gaussian_filter_time_domain(signal, sample_rate, cutoff_freq):
    sigma = sample_rate / (2.0 * np.pi * cutoff_freq)
    window_size = int(6 * sigma)
    if window_size % 2 == 0:
        window_size += 1  # make sure it's odd
    if window_size < 1:
        window_size = 1
    # Build a centered Gaussian window
    n = np.arange(window_size) - (window_size - 1) / 2.0
    gaussian_window = np.exp(-0.5 * (n / sigma) ** 2)
    gaussian_window /= np.sum(gaussian_window)  # normalize
    return np.convolve(signal, gaussian_window, mode='same')


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Interactive 1D Array Visualizer")
        self.setGeometry(100, 100, 1750, 1000)

        # Create a central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add a label for instructions (slim status line, full width)
        self.label = QLabel("Load a transmission .npy file (its monitor pair loads automatically)", self)
        layout.addWidget(self.label)

        # ------------------------------------------------------------------
        # Top area: control rows on the left, message box + file list stacked
        # vertically on the right.
        # ------------------------------------------------------------------
        top_area = QHBoxLayout()
        controls_col = QVBoxLayout()  # left: all the control rows

        # ------------------------------------------------------------------
        # Row 1: compact sampling-rate input + load button + raw color picker
        # ------------------------------------------------------------------
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Sampling Rate (Hz):", self))
        self.sampling_rate_input = QLineEdit(self)
        self.sampling_rate_input.setPlaceholderText("e.g., 100000")
        self.sampling_rate_input.setText("100000")  # Default value
        self.sampling_rate_input.setFixedWidth(90)
        self.sampling_rate_input.textChanged.connect(self.update_sampling_rate)
        top_row.addWidget(self.sampling_rate_input)

        self.load_button = QPushButton("Load Transmission (+ Monitor)", self)
        self.load_button.clicked.connect(self.load_file)
        top_row.addWidget(self.load_button)

        top_row.addSpacing(20)
        top_row.addWidget(QLabel("Raw color:", self))
        self.raw_color_combo = QComboBox(self)
        self.raw_color_combo.addItems(['black', 'dimgray', 'gray', 'lightgray', 'C0', 'C1', 'C2', 'red', 'green'])
        self.raw_color_combo.setCurrentText('gray')
        self.raw_color_combo.setFixedWidth(100)
        self.raw_color_combo.currentTextChanged.connect(self.update_raw_color)
        top_row.addWidget(self.raw_color_combo)

        top_row.addStretch()
        controls_col.addLayout(top_row)

        # ------------------------------------------------------------------
        # Row 2: analysis buttons
        # ------------------------------------------------------------------
        button_layout = QHBoxLayout()
        self.autorange_button = QPushButton("Autorange Y-axis", self)
        self.autorange_button.clicked.connect(self.autorange_y_axis)
        self.autorange_button.setEnabled(False)
        button_layout.addWidget(self.autorange_button)

        self.clear_roi_button = QPushButton("Clear ROI", self)
        self.clear_roi_button.clicked.connect(self.clear_roi)
        self.clear_roi_button.setEnabled(False)
        button_layout.addWidget(self.clear_roi_button)

        self.fft_button = QPushButton("Show PSD", self)
        self.fft_button.clicked.connect(self.show_fft)
        self.fft_button.setEnabled(False)
        button_layout.addWidget(self.fft_button)

        self.log_scale_button = QPushButton("Toggle Log/Linear Scale", self)
        self.log_scale_button.clicked.connect(self.toggle_log_scale)
        self.log_scale_button.setEnabled(False)
        button_layout.addWidget(self.log_scale_button)

        button_layout.addStretch()
        controls_col.addLayout(button_layout)

        # ------------------------------------------------------------------
        # Row 3: filter controls (Gaussian, transmission, current x-range)
        # ------------------------------------------------------------------
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Cutoff f_c1 (Hz):", self))
        self.cutoff1_input = QLineEdit(self)
        self.cutoff1_input.setPlaceholderText("e.g., 500")
        self.cutoff1_input.setText("10")
        self.cutoff1_input.setFixedWidth(80)
        filter_layout.addWidget(self.cutoff1_input)

        self.filter1_color_combo = QComboBox(self)
        self.filter1_color_combo.addItems(['C0', 'C1', 'C2', 'C3', 'C4', 'blue', 'orange', 'green', 'red', 'purple', 'black'])
        self.filter1_color_combo.setCurrentText('black')
        self.filter1_color_combo.setFixedWidth(80)
        self.filter1_color_combo.currentTextChanged.connect(self.update_filter_colors)
        filter_layout.addWidget(self.filter1_color_combo)

        filter_layout.addWidget(QLabel("Cutoff f_c2 (Hz):", self))
        self.cutoff2_input = QLineEdit(self)
        self.cutoff2_input.setPlaceholderText("e.g., 5000")
        self.cutoff2_input.setText("1000")
        self.cutoff2_input.setFixedWidth(80)
        filter_layout.addWidget(self.cutoff2_input)

        self.filter2_color_combo = QComboBox(self)
        self.filter2_color_combo.addItems(['C0', 'C1', 'C2', 'C3', 'C4', 'blue', 'orange', 'green', 'red', 'purple', 'black'])
        self.filter2_color_combo.setCurrentText('C3')
        self.filter2_color_combo.setFixedWidth(80)
        self.filter2_color_combo.currentTextChanged.connect(self.update_filter_colors)
        filter_layout.addWidget(self.filter2_color_combo)

        self.apply_filter_button = QPushButton("Apply Filters (current view)", self)
        self.apply_filter_button.clicked.connect(self.apply_filters)
        self.apply_filter_button.setEnabled(False)
        filter_layout.addWidget(self.apply_filter_button)

        self.clear_filter_button = QPushButton("Clear Filters", self)
        self.clear_filter_button.clicked.connect(self.clear_filters)
        self.clear_filter_button.setEnabled(False)
        filter_layout.addWidget(self.clear_filter_button)

        filter_layout.addStretch()
        controls_col.addLayout(filter_layout)

        # ------------------------------------------------------------------
        # Row 4: export controls (images support PNG and SVG; data as NPY)
        # ------------------------------------------------------------------
        export_layout = QHBoxLayout()
        self.export_tra_png_button = QPushButton("Export Transmission (PNG/SVG)", self)
        self.export_tra_png_button.clicked.connect(self.export_transmission_image)
        self.export_tra_png_button.setEnabled(False)
        export_layout.addWidget(self.export_tra_png_button)

        self.export_mon_png_button = QPushButton("Export Monitor (PNG/SVG)", self)
        self.export_mon_png_button.clicked.connect(self.export_monitor_image)
        self.export_mon_png_button.setEnabled(False)
        export_layout.addWidget(self.export_mon_png_button)

        self.export_report_png_button = QPushButton("Export Report (PNG/SVG)", self)
        self.export_report_png_button.clicked.connect(self.export_report_image)
        self.export_report_png_button.setEnabled(False)
        export_layout.addWidget(self.export_report_png_button)

        self.export_npy_button = QPushButton("Export Data (NPY)", self)
        self.export_npy_button.clicked.connect(self.export_data_npy)
        self.export_npy_button.setEnabled(False)
        export_layout.addWidget(self.export_npy_button)

        export_layout.addStretch()
        controls_col.addLayout(export_layout)
        controls_col.addStretch()  # keep the control rows top-aligned

        top_area.addLayout(controls_col, stretch=0)  # buttons take only what they need

        # ------------------------------------------------------------------
        # Right side: message box and file list side by side (left | right)
        # ------------------------------------------------------------------
        side_row = QHBoxLayout()

        msg_col = QVBoxLayout()
        msg_col.addWidget(QLabel("Messages:", self))
        self.text_box = QTextEdit(self)
        self.text_box.setReadOnly(True)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.text_box)
        scroll_area.setWidgetResizable(True)
        msg_col.addWidget(scroll_area, stretch=1)
        side_row.addLayout(msg_col, stretch=1)

        files_col = QVBoxLayout()
        files_col.addWidget(QLabel("Transmission files:", self))
        self.file_list = QListWidget(self)
        self.file_list.itemClicked.connect(self.load_selected_file)
        files_col.addWidget(self.file_list, stretch=1)
        side_row.addLayout(files_col, stretch=1)

        side_container = QWidget()
        side_container.setLayout(side_row)
        side_container.setMinimumWidth(600)    # stay readable even on narrow windows
        side_container.setMaximumHeight(150)   # keep the top area compact
        top_area.addWidget(side_container, stretch=1)  # fill the space left next to the buttons

        layout.addLayout(top_area)

        # ------------------------------------------------------------------
        # Plots: transmission on the left; monitor + PSD share a tab widget on
        # the right (PSD sits as a tab behind the monitor plot).
        # ------------------------------------------------------------------
        plot_layout = QHBoxLayout()

        # Left column: transmission plot + its toolbar
        self.figure1 = Figure()
        self.canvas1 = FigureCanvas(self.figure1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        left_plot_col = QVBoxLayout()
        left_plot_col.addWidget(self.canvas1)
        left_plot_col.addWidget(self.toolbar1)
        plot_layout.addLayout(left_plot_col, stretch=1)

        # Right column: tab widget with Monitor and PSD tabs
        self.figure2 = Figure()
        self.canvas2 = FigureCanvas(self.figure2)
        self.figure3 = Figure()
        self.canvas3 = FigureCanvas(self.figure3)
        self.toolbar3 = NavigationToolbar(self.canvas3, self)

        self.plot_tabs = QTabWidget(self)

        monitor_tab = QWidget()
        monitor_tab_layout = QVBoxLayout(monitor_tab)
        monitor_tab_layout.addWidget(self.canvas2)
        self.plot_tabs.addTab(monitor_tab, "Monitor")

        psd_tab = QWidget()
        psd_tab_layout = QVBoxLayout(psd_tab)
        psd_tab_layout.addWidget(self.canvas3)
        psd_tab_layout.addWidget(self.toolbar3)
        self.psd_tab_index = self.plot_tabs.addTab(psd_tab, "PSD")

        plot_layout.addWidget(self.plot_tabs, stretch=1)

        layout.addLayout(plot_layout, stretch=1)

        # Initialize variables
        self.data1 = None
        self.data2 = None
        self.ax1 = None
        self.ax2 = None
        self.ax3 = None
        self.selector1 = None
        self.selector2 = None
        self.sampling_rate = 100000  # Default sampling rate
        self.time_axis1 = None
        self.time_axis2 = None
        self.measurement_counter = 0
        self.synchronizing = False  # Flag to prevent recursive callback calls
        self.roi_rect1 = None  # Rectangle for ROI in Trace 1
        self.roi_rect2 = None  # Rectangle for ROI in Trace 2
        self.roi_bounds = None  # Bounds of the selected ROI
        self.folder_path = None  # Path to the folder containing the selected file
        self.log_scale = False  # Flag for log/linear scale
        self.psd_data = None  # Store PSD data for toggling scale
        self.freq_data = None  # Store frequency data for toggling scale

        # Colors / handles
        self.raw_color = 'gray'           # color of the raw transmission trace (matches dropdown default)
        self.raw_line1 = None             # Line2D handle of the raw transmission trace
        # Filter colors come from self.filter1_color_combo / self.filter2_color_combo

        # Filtering state
        self.filter_lines = []  # matplotlib Line2D handles of filter overlays on ax1

        # Naming state (used to propose export filenames)
        self.current_id = None  # source stem, used as a suffix on saved files

    ##########################################################################
    # LOADING (transmission + matching monitor from the same folder)
    ##########################################################################
    def load_file(self):
        """Open a file dialog to select a transmission .npy file; the matching
        monitor file in the same folder is loaded automatically."""
        file_filter = "Transmission files (*transmission*.npy)"
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Transmission Trace", "", file_filter)
        if file_path:
            self.load_pair(file_path)

    def _monitor_path_for(self, tra_path):
        """Return the monitor file path matching a transmission file, or None."""
        base = os.path.basename(tra_path)
        if 'transmission' not in base.lower():
            return None
        # Replace the 'transmission' token with 'monitor' (case-insensitive on the token)
        mon_base = re.sub('transmission', 'monitor', base, flags=re.IGNORECASE)
        mon_path = os.path.join(os.path.dirname(tra_path), mon_base)
        return mon_path if os.path.exists(mon_path) else None

    def load_pair(self, tra_path):
        """Load a transmission trace and its matching monitor trace."""
        self.folder_path = os.path.dirname(tra_path)
        self.update_file_list()
        # Clear both plots before loading new data
        self.clear_trace_plot(1)
        self.clear_trace_plot(2)
        # Load transmission
        self.load_data(tra_path, 1)
        # Load matching monitor (if present)
        mon_path = self._monitor_path_for(tra_path)
        if mon_path:
            self.load_data(mon_path, 2)
        else:
            self.label.setText(self.label.text() + "\n(No matching monitor file found in the folder.)")

    def update_file_list(self):
        """Update the file list box with transmission files in the selected folder."""
        if self.folder_path:
            self.file_list.clear()
            files = [f for f in os.listdir(self.folder_path) if f.endswith('.npy') and "transmission" in f.lower()]
            files.sort()
            self.file_list.addItems(files)

    def load_selected_file(self, item):
        """Load a transmission file (and its monitor pair) selected from the list."""
        if "transmission" in item.text().lower():
            tra_path = os.path.join(self.folder_path, item.text())
            self.load_pair(tra_path)

    def clear_trace_plot(self, trace_number):
        """Clear the plot for the specified trace."""
        if trace_number == 1:
            self.figure1.clear()
            self.ax1 = None
            self.raw_line1 = None
            if self.selector1:
                self.selector1.set_active(False)
                self.selector1 = None
            if self.roi_rect1:
                self.roi_rect1 = None
            # Clear any filter overlays (their axes is gone)
            self.filter_lines = []
            self.clear_filter_button.setEnabled(False)
            self.data1 = None
            self.time_axis1 = None
            self.canvas1.draw()
        elif trace_number == 2:
            self.figure2.clear()
            self.ax2 = None
            if self.selector2:
                self.selector2.set_active(False)
                self.selector2 = None
            if self.roi_rect2:
                self.roi_rect2 = None
            self.data2 = None
            self.time_axis2 = None
            self.canvas2.draw()

    def load_data(self, file_path, trace_number):
        """Load data from a file into the specified trace."""
        try:
            data = np.load(file_path)

            if data.ndim != 1:
                self.label.setText(f"Error: {file_path} must contain a 1D array.")
                return

            try:
                self.sampling_rate = float(self.sampling_rate_input.text())
                if self.sampling_rate <= 0:
                    raise ValueError("Sampling rate must be positive.")
            except ValueError:
                self.label.setText("Error: Invalid sampling rate. Please enter a positive number.")
                return

            filename = os.path.basename(file_path)
            filenumber = self.extract_filenumber(filename)
            datetime_str = self.extract_datetime_string(filename)

            if trace_number == 1:
                # Store a naming id (strip trailing _transmission) for export filenames
                stem = os.path.splitext(filename)[0]
                self.current_id = re.sub(r'_transmission$', '', stem, flags=re.IGNORECASE)

                self.data1 = data
                self.time_axis1 = np.arange(len(self.data1)) / self.sampling_rate
                self.ax1 = self.figure1.add_subplot(111)
                (self.raw_line1,) = self.ax1.plot(
                    self.time_axis1, self.data1, linewidth=0.5, color=self.raw_color, alpha=0.7, label="Original")
                self.ax1.set_title(f"Trace 1 (Transmission) - File {filenumber} - {datetime_str}")
                self.ax1.set_xlabel("Time (seconds)")
                self.ax1.set_ylabel("Transmission (V)")
                self.selector1 = RectangleSelector(
                    self.ax1,
                    lambda eclick, erelease: self.on_select(eclick, erelease),
                    useblit=True, button=[1], minspanx=5, spancoords='pixels', interactive=True
                )
                self.canvas1.draw()
            elif trace_number == 2:
                self.data2 = data
                self.time_axis2 = np.arange(len(self.data2)) / self.sampling_rate
                self.ax2 = self.figure2.add_subplot(111)
                self.ax2.plot(self.time_axis2, self.data2, linewidth=0.5, color='orange')
                self.ax2.set_title(f"Trace 2 (Monitor) - File {filenumber} - {datetime_str}")
                self.ax2.set_xlabel("Time (seconds)")
                self.ax2.set_ylabel("Monitor signal (V)")
                self.selector2 = RectangleSelector(
                    self.ax2,
                    lambda eclick, erelease: self.on_select(eclick, erelease),
                    useblit=True, button=[1], minspanx=5, spancoords='pixels', interactive=True
                )
                self.canvas2.draw()

            if self.data1 is not None or self.data2 is not None:
                self.autorange_button.setEnabled(True)

            if self.data1 is not None:
                self.apply_filter_button.setEnabled(True)
                self.export_tra_png_button.setEnabled(True)
                self.export_report_png_button.setEnabled(True)
                self.export_npy_button.setEnabled(True)
            if self.data2 is not None:
                self.export_mon_png_button.setEnabled(True)

            self.label.setText(f"Loaded Trace {trace_number}: {file_path}\nArray shape: {data.shape}")

            self.synchronize_axes()
            self.autorange_y_axis()

        except Exception as e:
            self.label.setText(f"Error: {str(e)}")

    def extract_filenumber(self, filename):
        """Extract the filenumber from the filename."""
        match = re.search(r"(\d+)_(transmission|monitor)", filename)
        if match:
            return match.group(1)
        return "Unknown"

    def extract_datetime_string(self, filename):
        """Extract and format date/time from filename."""
        match = re.search(r"(\d{8})_(\d{6})", filename)
        if match:
            try:
                date_str = match.group(1)
                time_str = match.group(2)
                date_obj = datetime.strptime(date_str, "%Y%m%d")
                time_obj = datetime.strptime(time_str, "%H%M%S")
                formatted_time = time_obj.strftime("%H:%M:%S")
                formatted_date = date_obj.strftime("%d.%m.%Y")
                return f"{formatted_time} - {formatted_date}"
            except ValueError:
                pass
        return "Unknown time"

    def update_sampling_rate(self):
        """Update the x-axis of both trace plots when the sampling rate is changed."""
        try:
            self.sampling_rate = float(self.sampling_rate_input.text())
            if self.sampling_rate <= 0:
                raise ValueError("Sampling rate must be positive.")
        except ValueError:
            self.label.setText("Error: Invalid sampling rate. Please enter a positive number.")
            return

        if self.data1 is not None and self.ax1 is not None:
            self.time_axis1 = np.arange(len(self.data1)) / self.sampling_rate
            self.ax1.clear()
            (self.raw_line1,) = self.ax1.plot(
                self.time_axis1, self.data1, linewidth=0.5, color=self.raw_color, alpha=0.7, label="Original")
            self.ax1.set_xlabel("Time (seconds)")
            self.ax1.set_ylabel("Transmission (V)")
            # Filter overlays were removed by ax1.clear()
            self.filter_lines = []
            self.clear_filter_button.setEnabled(False)
            self.canvas1.draw()

        if self.data2 is not None and self.ax2 is not None:
            self.time_axis2 = np.arange(len(self.data2)) / self.sampling_rate
            self.ax2.clear()
            self.ax2.plot(self.time_axis2, self.data2, linewidth=0.5, color='orange')
            self.ax2.set_xlabel("Time (seconds)")
            self.ax2.set_ylabel("Monitor signal (V)")
            self.canvas2.draw()

    def update_raw_color(self):
        """Change the color of the raw transmission trace."""
        self.raw_color = self.raw_color_combo.currentText()
        if self.raw_line1 is not None:
            self.raw_line1.set_color(self.raw_color)
            self.canvas1.draw()

    def on_select(self, eclick, erelease):
        # Get the selected region bounds in time (seconds)
        x1, x2 = sorted([eclick.xdata, erelease.xdata])
        x1 = max(0, x1)
        x2 = min(len(self.data1) / self.sampling_rate, x2)

        self.roi_bounds = (x1, x2)

        sample1 = int(x1 * self.sampling_rate)
        sample2 = int(x2 * self.sampling_rate)

        selected_data1 = self.data1[sample1:sample2] if self.data1 is not None else None
        selected_data2 = self.data2[sample1:sample2] if self.data2 is not None else None

        results = []
        if selected_data1 is not None:
            mean1 = np.mean(selected_data1)
            std1 = np.std(selected_data1)
            results.append(f"Trace 1 (Transmission): N = {len(selected_data1)}, Mean = {mean1:.4f}, Std = {std1:.4f}")
        if selected_data2 is not None:
            mean2 = np.mean(selected_data2)
            std2 = np.std(selected_data2)
            results.append(f"Trace 2 (Monitor): N = {len(selected_data2)}, Mean = {mean2:.4f}, Std = {std2:.4f}")

        n_points = sample2 - sample1

        self.measurement_counter += 1

        self.text_box.append(
            f"Measurement {self.measurement_counter}:\n"
            f"Selected region: [{x1:.4f} s, {x2:.4f} s] ({n_points} points)\n"
            + "\n".join(results) + "\n"
        )

        self.draw_roi(x1, x2)

        self.clear_roi_button.setEnabled(True)
        self.fft_button.setEnabled(True)

    def draw_roi(self, x1, x2):
        """Draw a red rectangle to highlight the selected region."""
        self.clear_roi()

        if self.ax1:
            self.roi_rect1 = Rectangle((x1, self.ax1.get_ylim()[0]), x2 - x1, self.ax1.get_ylim()[1] - self.ax1.get_ylim()[0],
                                       edgecolor='red', facecolor='none', linewidth=2)
            self.ax1.add_patch(self.roi_rect1)
            self.canvas1.draw()
        if self.ax2:
            self.roi_rect2 = Rectangle((x1, self.ax2.get_ylim()[0]), x2 - x1, self.ax2.get_ylim()[1] - self.ax2.get_ylim()[0],
                                       edgecolor='red', facecolor='none', linewidth=2)
            self.ax2.add_patch(self.roi_rect2)
            self.canvas2.draw()

    def clear_roi(self):
        """Remove the ROI rectangles from both plots."""
        if self.roi_rect1:
            self.roi_rect1.remove()
            self.roi_rect1 = None
            self.canvas1.draw()
        if self.roi_rect2:
            self.roi_rect2.remove()
            self.roi_rect2 = None
            self.canvas2.draw()

        self.clear_roi_button.setEnabled(False)
        self.fft_button.setEnabled(False)
        self.log_scale_button.setEnabled(False)

    def show_fft(self):
        """Show the PSD of the Transmission signal for the selected ROI."""
        if self.roi_bounds is None or self.data1 is None:
            return

        x1, x2 = self.roi_bounds
        sample1 = int(x1 * self.sampling_rate)
        sample2 = int(x2 * self.sampling_rate)
        selected_data1 = self.data1[sample1:sample2]

        fft_values = np.fft.fft(selected_data1)
        n_samples = len(selected_data1)
        psd = (np.abs(fft_values) ** 2) / (n_samples * self.sampling_rate)
        freq_axis = np.fft.fftfreq(n_samples, 1 / self.sampling_rate)

        positive_freq_idx = freq_axis > 0
        freq_axis_positive = freq_axis[positive_freq_idx]
        psd_positive = 2 * psd[positive_freq_idx]

        self.freq_data = freq_axis_positive
        self.psd_data = psd_positive

        self.plot_psd()
        self.log_scale_button.setEnabled(True)
        # Bring the PSD tab to the front so the result is visible
        self.plot_tabs.setCurrentIndex(self.psd_tab_index)

    def plot_psd(self):
        """Plot the PSD with current scale setting."""
        if self.freq_data is None or self.psd_data is None:
            return

        self.figure3.clear()
        self.ax3 = self.figure3.add_subplot(111)

        self.ax3.plot(self.freq_data, self.psd_data, linewidth=0.5, color='purple')
        self.ax3.set_title("Power Spectral Density of Transmission Signal")
        self.ax3.set_xlabel("Frequency (Hz)")

        if self.log_scale:
            self.ax3.set_yscale('log')
            self.ax3.set_ylabel("PSD (log scale)")
        else:
            self.ax3.set_yscale('linear')
            self.ax3.set_ylabel("PSD")

        self.ax3.grid(True, alpha=0.3)
        self.canvas3.draw()

    def toggle_log_scale(self):
        """Toggle between logarithmic and linear y-scale for PSD plot."""
        self.log_scale = not self.log_scale
        self.plot_psd()

    def synchronize_axes(self):
        """Synchronize the x-axis limits of both plots."""
        if self.ax1 and self.ax2:
            self.ax1.callbacks.connect('xlim_changed', self.update_ax2_limits)
            self.ax2.callbacks.connect('xlim_changed', self.update_ax1_limits)

    def update_ax2_limits(self, ax):
        if not self.synchronizing and self.ax2:
            self.synchronizing = True
            x_min, x_max = ax.get_xlim()
            self.ax2.set_xlim(x_min, x_max)
            self.canvas2.draw()
            self.synchronizing = False

    def update_ax1_limits(self, ax):
        if not self.synchronizing and self.ax1:
            self.synchronizing = True
            x_min, x_max = ax.get_xlim()
            self.ax1.set_xlim(x_min, x_max)
            self.canvas1.draw()
            self.synchronizing = False

    def autorange_y_axis(self):
        """Adjust the y-axis to fit the currently displayed region for both traces."""
        for ax, data in zip([self.ax1, self.ax2], [self.data1, self.data2]):
            if ax and data is not None:
                x_min, x_max = ax.get_xlim()
                sample_min = int(x_min * self.sampling_rate)
                sample_max = int(x_max * self.sampling_rate)
                sample_min = max(0, sample_min)
                sample_max = min(len(data) - 1, sample_max)
                y_values = data[sample_min:sample_max]
                if len(y_values) > 0:
                    y_min = np.min(y_values)
                    y_max = np.max(y_values)
                    padding = (y_max - y_min) * 0.05
                    ax.set_ylim(y_min - padding, y_max + padding)
        self.canvas1.draw()
        self.canvas2.draw()

    ##########################################################################
    # FILTERING (Gaussian, transmission trace, current x-range only)
    ##########################################################################
    def _current_xrange_indices(self):
        """Return (i1, i2) sample indices spanned by the current transmission x-axis."""
        if self.data1 is None or self.ax1 is None:
            return None
        x_min, x_max = self.ax1.get_xlim()
        n = len(self.data1)
        i1 = max(0, int(x_min * self.sampling_rate))
        i2 = min(n, int(x_max * self.sampling_rate))
        if i2 - i1 < 2:
            return None
        return i1, i2

    def _filter_visible(self, i1, i2, fc):
        """Gaussian-filter the transmission over [i1, i2], but extend the segment
        by the filter support on each side so there are no edge artifacts inside
        the displayed range. Returns an array of length (i2 - i1)."""
        sigma = self.sampling_rate / (2.0 * np.pi * fc)
        pad = int(np.ceil(6 * sigma))  # full Gaussian support
        n = len(self.data1)
        e1 = max(0, i1 - pad)
        e2 = min(n, i2 + pad)
        filt_ext = gaussian_filter_time_domain(self.data1[e1:e2], self.sampling_rate, fc)
        # Crop back to the visible window
        return filt_ext[i1 - e1: i2 - e1]

    def _parse_cutoff(self, text):
        """Return a valid cutoff float, or None if empty/invalid/out of range."""
        text = text.strip()
        if not text:
            return None
        try:
            fc = float(text)
        except (ValueError, TypeError):
            return None
        nyquist = self.sampling_rate / 2.0
        if fc <= 0 or fc >= nyquist:
            return None
        return fc

    def _get_cutoffs(self):
        """Parse the two cutoff boxes. Empty or invalid boxes are skipped, so a
        single filter is applied if only one box is filled in. Each filter takes
        its color from its own dropdown."""
        cutoffs = []
        fields = [(self.cutoff1_input, self.filter1_color_combo),
                  (self.cutoff2_input, self.filter2_color_combo)]
        for inp, color_combo in fields:
            fc = self._parse_cutoff(inp.text())
            if fc is None:
                continue
            color = color_combo.currentText()
            cutoffs.append((fc, color, r"$f_c$ = %g Hz" % fc))
        return cutoffs

    def _remove_filter_lines(self):
        """Remove any filter overlays from ax1 (without redrawing)."""
        for line in self.filter_lines:
            try:
                line.remove()
            except Exception:
                pass
        self.filter_lines = []
        if self.ax1 is not None:
            leg = self.ax1.get_legend()
            if leg is not None:
                leg.remove()

    def apply_filters(self):
        """Compute and overlay Gaussian-filtered transmission for the current view."""
        idx = self._current_xrange_indices()
        if idx is None:
            self.label.setText("Cannot filter: load a transmission trace and select a valid view range.")
            return
        i1, i2 = idx

        cutoffs = self._get_cutoffs()
        if not cutoffs:
            nyq = self.sampling_rate / 2.0
            self.label.setText("Enter at least one valid cutoff frequency (0 < f_c < %g Hz)." % nyq)
            return

        t_slice = self.time_axis1[i1:i2]

        # Preserve the current view so re-applying (e.g. after a color change)
        # does not rescale the plot.
        cur_xlim = self.ax1.get_xlim()
        cur_ylim = self.ax1.get_ylim()

        self._remove_filter_lines()

        applied = []
        drawn = []  # (fc, line) to set draw order afterwards
        for fc, color, label in cutoffs:
            filtered = self._filter_visible(i1, i2, fc)
            line, = self.ax1.plot(t_slice, filtered, color=color, linewidth=1.2, label=label)
            self.filter_lines.append(line)
            drawn.append((fc, line))
            applied.append("f_c=%g Hz" % fc)

        # Draw the lowest-cutoff (smoothest) filter on top so it stays visible.
        # Raw line has zorder ~2; filters get higher zorder, lowest fc the highest.
        drawn.sort(key=lambda t: t[0])  # ascending cutoff
        n = len(drawn)
        for rank, (fc, line) in enumerate(drawn):
            line.set_zorder(3 + (n - rank))  # rank 0 (lowest fc) -> highest zorder

        # Restore the view (plotting may have triggered autoscale)
        self.ax1.set_xlim(cur_xlim)
        self.ax1.set_ylim(cur_ylim)

        self.ax1.legend(loc='upper right', fontsize=8)
        self.canvas1.draw()

        self.clear_filter_button.setEnabled(True)
        self.text_box.append(
            "Gaussian filter applied on transmission over [%.4f s, %.4f s]: %s\n"
            % (t_slice[0], t_slice[-1], ", ".join(applied))
        )

    def update_filter_colors(self):
        """Re-apply the filters so color changes take effect immediately (only if
        filters are currently displayed)."""
        if self.filter_lines:
            self.apply_filters()

    def clear_filters(self):
        """Remove filter overlays from the transmission plot."""
        self._remove_filter_lines()
        if self.canvas1:
            self.canvas1.draw()
        self.clear_filter_button.setEnabled(False)

    ##########################################################################
    # EXPORTS
    ##########################################################################
    def _default_save_dir(self):
        """Return the directory to propose for saving. Offers to create an
        'analyzed_data' subfolder inside the data folder the first time."""
        if not self.folder_path:
            return ""
        target = os.path.join(self.folder_path, 'analyzed_data')
        if not os.path.isdir(target):
            reply = QMessageBox.question(
                self, "Create folder",
                "Create folder 'analyzed_data' inside the data folder to store the results?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                try:
                    os.makedirs(target, exist_ok=True)
                    return target
                except Exception:
                    return self.folder_path
            return self.folder_path
        return target

    def _suffix(self):
        """Return the source-file suffix to append to saved filenames."""
        return ('_' + self.current_id) if self.current_id else ''

    def _save_figure(self, fig, title, default_stem):
        """Open a save dialog (PNG or SVG) with a proposed name, then save fig."""
        save_dir = self._default_save_dir()
        default_name = default_stem + self._suffix() + '.png'
        start = os.path.join(save_dir, default_name) if save_dir else default_name
        path, selected = QFileDialog.getSaveFileName(
            self, title, start, "PNG image (*.png);;SVG image (*.svg)")
        if not path:
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext not in ('.png', '.svg'):
            ext = '.svg' if 'svg' in selected.lower() else '.png'
            path = path + ext
        try:
            fig.savefig(path, dpi=300, bbox_inches='tight')
            self.label.setText("Saved: %s" % path)
            return path
        except Exception as e:
            self.label.setText("Error saving image: %s" % str(e))
            return None

    def export_transmission_image(self):
        """Save a high-resolution copy of the current transmission view (PNG/SVG)."""
        if self.data1 is None:
            return
        self._save_figure(self.figure1, "Export Transmission View", "transmission_view")

    def export_monitor_image(self):
        """Save a high-resolution copy of the current monitor view (PNG/SVG)."""
        if self.data2 is None:
            return
        self._save_figure(self.figure2, "Export Monitor View", "monitor_view")

    def export_report_image(self):
        """Build and save a publication-style figure from the current x-range:
        transmission (original + filtered overlays) and monitor, each with a
        horizontal histogram on the right. Self-contained for easy extension."""
        idx = self._current_xrange_indices()
        if idx is None:
            self.label.setText("Cannot build report: load a transmission trace and select a valid view range.")
            return
        i1, i2 = idx

        t_slice = self.time_axis1[i1:i2]
        tra_slice = self.data1[i1:i2]

        # Recompute filtered curves (edge-safe) for the current range
        filt_list = []
        for fc, color, label in self._get_cutoffs():
            filt_list.append((fc, color, label, self._filter_visible(i1, i2, fc)))

        # Monitor slice aligned to the same window (if loaded)
        mon_slice = None
        t_mon = None
        if self.data2 is not None:
            j2 = min(len(self.data2), i2)
            j1 = min(i1, j2)
            mon_slice = self.data2[j1:j2]
            t_mon = self.time_axis2[j1:j2] if self.time_axis2 is not None else t_slice[:len(mon_slice)]

        gray = self.raw_color
        ff = 20  # base font size (adjustable)

        fig = Figure(figsize=(20, 11))
        FigureCanvasAgg(fig)  # attach an Agg canvas so savefig works headlessly

        if mon_slice is not None:
            gs = GridSpec(2, 2, figure=fig, width_ratios=[4, 1])
            gs.update(hspace=0.25, wspace=0.02)
            ax1 = fig.add_subplot(gs[0, 0])
            ax1h = fig.add_subplot(gs[0, 1], sharey=ax1)
            ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
            ax2h = fig.add_subplot(gs[1, 1], sharey=ax2)
        else:
            gs = GridSpec(1, 2, figure=fig, width_ratios=[4, 1])
            gs.update(wspace=0.02)
            ax1 = fig.add_subplot(gs[0, 0])
            ax1h = fig.add_subplot(gs[0, 1], sharey=ax1)
            ax2 = None
            ax2h = None

        # --- Transmission panel ---
        ax1.plot(t_slice, tra_slice, color=gray, linewidth=1.5, label='Original')
        _report_drawn = []
        for fc, color, label, filt in filt_list:
            (rline,) = ax1.plot(t_slice, filt, color=color, linewidth=2, label=label)
            _report_drawn.append((fc, rline))
        # Lowest cutoff on top
        _report_drawn.sort(key=lambda t: t[0])
        _nrep = len(_report_drawn)
        for rank, (fc, rline) in enumerate(_report_drawn):
            rline.set_zorder(3 + (_nrep - rank))
        ax1.set_ylabel('Transmission (V)', fontsize=ff)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right', fontsize=int(ff * 0.7), ncol=max(1, len(filt_list) + 1))

        y0, y1 = ax1.get_ylim()
        ax1h.hist(tra_slice, bins=40, range=(y0, y1), rwidth=0.8, histtype='bar',
                  orientation='horizontal', density=True, color=gray)
        for fc, color, label, filt in filt_list:
            ax1h.hist(filt, bins=40, range=(y0, y1), rwidth=0.8, histtype='bar',
                      orientation='horizontal', density=True, color=color, alpha=0.7)
        ax1h.get_yaxis().set_visible(False)
        ax1h.grid(True, alpha=0.3)

        # --- Monitor panel ---
        if mon_slice is not None:
            ax2.plot(t_mon, mon_slice, color='dimgray', linewidth=1.5, label='Monitor')
            ax2.set_ylabel('Monitor signal (V)', fontsize=ff)
            ax2.set_xlabel('Time (s)', fontsize=ff)
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='upper right', fontsize=int(ff * 0.7))

            yy0, yy1 = ax2.get_ylim()
            ax2h.hist(mon_slice, bins=40, range=(yy0, yy1), rwidth=0.8, histtype='bar',
                      orientation='horizontal', density=True, color='dimgray')
            ax2h.get_yaxis().set_visible(False)
            ax2h.grid(True, alpha=0.3)
        else:
            ax1.set_xlabel('Time (s)', fontsize=ff)

        for ax in fig.axes:
            ax.tick_params(axis='both', which='major', labelsize=int(ff * 0.8))

        self._save_figure(fig, "Export Report", "report")

    def export_data_npy(self):
        """Export the current x-range slice as .npy files: transmission, monitor,
        time axis, and the recomputed (edge-safe) filtered curve(s)."""
        idx = self._current_xrange_indices()
        if idx is None:
            self.label.setText("Cannot export: load a transmission trace and select a valid view range.")
            return
        i1, i2 = idx

        t_slice = self.time_axis1[i1:i2]
        tra_slice = self.data1[i1:i2]

        save_dir = self._default_save_dir()
        default_name = 'data' + self._suffix() + '.npy'
        start = os.path.join(save_dir, default_name) if save_dir else default_name
        path, _ = QFileDialog.getSaveFileName(self, "Export Data (NPY base name)", start, "NumPy (*.npy)")
        if not path:
            return
        base = path[:-4] if path.lower().endswith('.npy') else path

        saved = []
        try:
            np.save(base + '_transmission.npy', tra_slice)
            saved.append(os.path.basename(base) + '_transmission.npy')
            np.save(base + '_time.npy', t_slice)
            saved.append(os.path.basename(base) + '_time.npy')

            if self.data2 is not None:
                j2 = min(len(self.data2), i2)
                j1 = min(i1, j2)
                np.save(base + '_monitor.npy', self.data2[j1:j2])
                saved.append(os.path.basename(base) + '_monitor.npy')

            for fc, color, label in self._get_cutoffs():
                filt = self._filter_visible(i1, i2, fc)
                fname = base + ('_filtered_fc%g.npy' % fc)
                np.save(fname, filt)
                saved.append(os.path.basename(fname))

            self.label.setText("Saved: " + ", ".join(saved))
        except Exception as e:
            self.label.setText("Error saving NPY: %s" % str(e))

    def closeEvent(self, event):
        if self.selector1:
            self.selector1.set_active(False)
        if self.selector2:
            self.selector2.set_active(False)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
