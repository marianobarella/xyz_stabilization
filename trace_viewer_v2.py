import sys
import os
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QPushButton, QLabel, QLineEdit, QFormLayout, QHBoxLayout,
    QScrollArea, QTextEdit, QListWidget
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector
from matplotlib.patches import Rectangle
from scipy.stats import pearsonr
import re


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Interactive 1D Array Visualizer")
        self.setGeometry(100, 100, 1200, 1000)

        # Create a central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add a label for instructions
        self.label = QLabel("Load .npy files to visualize the 1D arrays", self)
        layout.addWidget(self.label)

        # Add a form layout for the sampling rate input
        form_layout = QFormLayout()
        self.sampling_rate_input = QLineEdit(self)
        self.sampling_rate_input.setPlaceholderText("Enter sampling rate in Hz (e.g., 1000)")
        self.sampling_rate_input.setText("1000")  # Default value
        self.sampling_rate_input.textChanged.connect(self.update_sampling_rate)  # Connect to update method
        form_layout.addRow("Sampling Rate (Hz):", self.sampling_rate_input)
        layout.addLayout(form_layout)

        # Add a horizontal layout for buttons
        button_layout = QHBoxLayout()
        self.load_button1 = QPushButton("Load Trace 1 (Transmission)", self)
        self.load_button1.clicked.connect(lambda: self.load_file(1))
        button_layout.addWidget(self.load_button1)

        self.load_button2 = QPushButton("Load Trace 2 (Monitor)", self)
        self.load_button2.clicked.connect(lambda: self.load_file(2))
        button_layout.addWidget(self.load_button2)

        self.autorange_button = QPushButton("Autorange Y-axis", self)
        self.autorange_button.clicked.connect(self.autorange_y_axis)
        self.autorange_button.setEnabled(False)  # Disabled until files are loaded
        button_layout.addWidget(self.autorange_button)

        self.clear_roi_button = QPushButton("Clear ROI", self)
        self.clear_roi_button.clicked.connect(self.clear_roi)
        self.clear_roi_button.setEnabled(False)  # Disabled until an ROI is drawn
        button_layout.addWidget(self.clear_roi_button)

        self.scatter_button = QPushButton("Show Scatter Plot", self)
        self.scatter_button.clicked.connect(self.show_scatter_plot)
        self.scatter_button.setEnabled(False)  # Disabled until an ROI is selected
        button_layout.addWidget(self.scatter_button)

        layout.addLayout(button_layout)

        # Add a horizontal layout for plots
        plot_layout = QHBoxLayout()
        self.figure1 = Figure()
        self.canvas1 = FigureCanvas(self.figure1)
        plot_layout.addWidget(self.canvas1)

        self.figure2 = Figure()
        self.canvas2 = FigureCanvas(self.figure2)
        plot_layout.addWidget(self.canvas2)

        self.figure3 = Figure()
        self.canvas3 = FigureCanvas(self.figure3)
        plot_layout.addWidget(self.canvas3)

        layout.addLayout(plot_layout)

        # Add the matplotlib toolbar for zooming and panning
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        layout.addWidget(self.toolbar1)

        # Add a toolbar for the scatter plot
        self.toolbar3 = NavigationToolbar(self.canvas3, self)
        layout.addWidget(self.toolbar3)

        # Add a scrollable text box for measurements
        self.text_box = QTextEdit(self)
        self.text_box.setReadOnly(True)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.text_box)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Add a list widget to display files in the selected folder
        self.file_list = QListWidget(self)
        self.file_list.itemClicked.connect(self.load_selected_file)
        layout.addWidget(self.file_list)

        # Initialize variables
        self.data1 = None
        self.data2 = None
        self.ax1 = None
        self.ax2 = None
        self.ax3 = None
        self.selector1 = None
        self.selector2 = None
        self.sampling_rate = 1000  # Default sampling rate
        self.time_axis1 = None
        self.time_axis2 = None
        self.measurement_counter = 0
        self.synchronizing = False  # Flag to prevent recursive callback calls
        self.roi_rect1 = None  # Rectangle for ROI in Trace 1
        self.roi_rect2 = None  # Rectangle for ROI in Trace 2
        self.roi_bounds = None  # Bounds of the selected ROI
        self.folder_path = None  # Path to the folder containing the selected file

    def load_file(self, trace_number):
        """Open a file dialog to select a .npy file for the specified trace."""
        if trace_number == 1:
            file_filter = "Transmission files (*transmission*.npy)"
            title = "Open Trace 1 (Transmission)"
        elif trace_number == 2:
            file_filter = "Monitor files (*monitor*.npy)"
            title = "Open Trace 2 (Monitor)"

        file_path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if file_path:
            self.folder_path = os.path.dirname(file_path)
            self.update_file_list()
            self.load_data(file_path, trace_number)

    def update_file_list(self):
        """Update the file list box with transmission files in the selected folder."""
        if self.folder_path:
            self.file_list.clear()
            files = [f for f in os.listdir(self.folder_path) if f.endswith('.npy') and "transmission" in f.lower()]
            self.file_list.addItems(files)

    def load_selected_file(self, item):
        """Load a file selected from the list."""
        file_path = os.path.join(self.folder_path, item.text())
        if "transmission" in item.text().lower():
            self.clear_trace_plot(1)  # Clear the Transmission plot
            self.load_data(file_path, 1)

    def clear_trace_plot(self, trace_number):
        """Clear the plot for the specified trace."""
        if trace_number == 1:
            self.figure1.clear()
            self.ax1 = self.figure1.add_subplot(111)
            self.canvas1.draw()
            self.data1 = None
            self.time_axis1 = None
            self.selector1 = None
        elif trace_number == 2:
            self.figure2.clear()
            self.ax2 = self.figure2.add_subplot(111)
            self.canvas2.draw()
            self.data2 = None
            self.time_axis2 = None
            self.selector2 = None

    def load_data(self, file_path, trace_number):
        """Load data from a file into the specified trace."""
        try:
            # Load the data
            data = np.load(file_path)

            # Check if the data is 1D
            if data.ndim != 1:
                self.label.setText(f"Error: {file_path} must contain a 1D array.")
                return

            # Get the sampling rate from the input field
            try:
                self.sampling_rate = float(self.sampling_rate_input.text())
                if self.sampling_rate <= 0:
                    raise ValueError("Sampling rate must be positive.")
            except ValueError:
                self.label.setText("Error: Invalid sampling rate. Please enter a positive number.")
                return

            # Extract the filenumber from the filename
            filenumber = self.extract_filenumber(file_path)

            # Assign data to the appropriate trace
            if trace_number == 1:
                self.data1 = data
                self.time_axis1 = np.arange(len(self.data1)) / self.sampling_rate
                self.ax1 = self.figure1.add_subplot(111)
                self.ax1.plot(self.time_axis1, self.data1, linewidth=0.5, color='blue')
                self.ax1.set_title(f"Trace 1 (Transmission) - File {filenumber}")
                self.ax1.set_xlabel("Time (seconds)")
                self.ax1.set_ylabel("Intensity")
                self.selector1 = RectangleSelector(
                    self.ax1,
                    lambda eclick, erelease: self.on_select(eclick, erelease),
                    useblit=True,
                    button=[1],
                    minspanx=5,
                    spancoords='pixels',
                    interactive=True
                )
                self.canvas1.draw()
            elif trace_number == 2:
                self.data2 = data
                self.time_axis2 = np.arange(len(self.data2)) / self.sampling_rate
                self.ax2 = self.figure2.add_subplot(111)
                self.ax2.plot(self.time_axis2, self.data2, linewidth=0.5, color='orange')
                self.ax2.set_title(f"Trace 2 (Monitor) - File {filenumber}")
                self.ax2.set_xlabel("Time (seconds)")
                self.ax2.set_ylabel("Intensity")
                self.selector2 = RectangleSelector(
                    self.ax2,
                    lambda eclick, erelease: self.on_select(eclick, erelease),
                    useblit=True,
                    button=[1],
                    minspanx=5,
                    spancoords='pixels',
                    interactive=True
                )
                self.canvas2.draw()

            # Enable the autorange button if at least one trace is loaded
            if self.data1 is not None or self.data2 is not None:
                self.autorange_button.setEnabled(True)

            # Update the label
            self.label.setText(f"Loaded Trace {trace_number}: {file_path}\nArray shape: {data.shape}")

            # Synchronize zoom and pan between traces
            self.synchronize_axes()

            # Autorange the y-axis for both traces
            self.autorange_y_axis()

        except Exception as e:
            self.label.setText(f"Error: {str(e)}")

    def extract_filenumber(self, file_path):
        """Extract the filenumber from the filename."""
        filename = os.path.basename(file_path)
        match = re.search(r"(\d+)_(transmission|monitor)", filename)
        if match:
            return match.group(1)
        return "Unknown"

    def update_sampling_rate(self):
        """Update the x-axis of both trace plots when the sampling rate is changed."""
        try:
            self.sampling_rate = float(self.sampling_rate_input.text())
            if self.sampling_rate <= 0:
                raise ValueError("Sampling rate must be positive.")
        except ValueError:
            self.label.setText("Error: Invalid sampling rate. Please enter a positive number.")
            return

        # Update the time axes for both traces
        if self.data1 is not None:
            self.time_axis1 = np.arange(len(self.data1)) / self.sampling_rate
            self.ax1.clear()
            self.ax1.plot(self.time_axis1, self.data1, linewidth=0.5, color='blue')
            self.ax1.set_title(f"Trace 1 (Transmission) - File {self.extract_filenumber(self.folder_path)}")
            self.ax1.set_xlabel("Time (seconds)")
            self.ax1.set_ylabel("Intensity")
            self.canvas1.draw()

        if self.data2 is not None:
            self.time_axis2 = np.arange(len(self.data2)) / self.sampling_rate
            self.ax2.clear()
            self.ax2.plot(self.time_axis2, self.data2, linewidth=0.5, color='orange')
            self.ax2.set_title(f"Trace 2 (Monitor) - File {self.extract_filenumber(self.folder_path)}")
            self.ax2.set_xlabel("Time (seconds)")
            self.ax2.set_ylabel("Intensity")
            self.canvas2.draw()

    def on_select(self, eclick, erelease):
        # Get the selected region bounds in time (seconds)
        x1, x2 = sorted([eclick.xdata, erelease.xdata])
        x1 = max(0, x1)  # Ensure x1 is within bounds
        x2 = min(len(self.data1) / self.sampling_rate, x2)  # Ensure x2 is within bounds

        # Store the ROI bounds
        self.roi_bounds = (x1, x2)

        # Convert time bounds to sample indices
        sample1 = int(x1 * self.sampling_rate)
        sample2 = int(x2 * self.sampling_rate)

        # Extract the selected region for both traces
        selected_data1 = self.data1[sample1:sample2] if self.data1 is not None else None
        selected_data2 = self.data2[sample1:sample2] if self.data2 is not None else None

        # Calculate mean and standard deviation for both traces
        results = []
        if selected_data1 is not None:
            mean1 = np.mean(selected_data1)
            std1 = np.std(selected_data1)
            results.append(f"Trace 1 (Transmission): Mean = {mean1:.4f}, Std = {std1:.4f}")
        if selected_data2 is not None:
            mean2 = np.mean(selected_data2)
            std2 = np.std(selected_data2)
            results.append(f"Trace 2 (Monitor): Mean = {mean2:.4f}, Std = {std2:.4f}")

        # Increment the measurement counter
        self.measurement_counter += 1

        # Update the text box with the results
        self.text_box.append(
            f"Measurement {self.measurement_counter}:\n"
            f"Selected region: [{x1:.4f} s, {x2:.4f} s]\n"
            + "\n".join(results) + "\n"
        )

        # Draw the ROI rectangle on both plots
        self.draw_roi(x1, x2)

        # Enable the "Clear ROI" and "Show Scatter Plot" buttons
        self.clear_roi_button.setEnabled(True)
        self.scatter_button.setEnabled(True)

    def draw_roi(self, x1, x2):
        """Draw a red rectangle to highlight the selected region."""
        # Remove previous ROI rectangles if they exist
        self.clear_roi()

        # Draw new ROI rectangles
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

        # Disable the "Clear ROI" and "Show Scatter Plot" buttons
        self.clear_roi_button.setEnabled(False)
        self.scatter_button.setEnabled(False)

    def show_scatter_plot(self):
        """Show a scatter plot of Transmission vs Monitor values for the selected ROI."""
        if self.roi_bounds is None or self.data1 is None or self.data2 is None:
            return

        # Get the selected region bounds
        x1, x2 = self.roi_bounds

        # Convert time bounds to sample indices
        sample1 = int(x1 * self.sampling_rate)
        sample2 = int(x2 * self.sampling_rate)

        # Extract the selected region for both traces
        selected_data1 = self.data1[sample1:sample2]
        selected_data2 = self.data2[sample1:sample2]

        # Calculate Pearson's correlation coefficient
        correlation, _ = pearsonr(selected_data1, selected_data2)

        # Clear the third plot
        self.figure3.clear()
        self.ax3 = self.figure3.add_subplot(111)

        # Plot the scatter plot
        self.ax3.scatter(selected_data1, selected_data2, color='green', alpha=0.5)
        self.ax3.set_title(f"Scatter Plot (Correlation: {correlation:.4f})")
        self.ax3.set_xlabel("Transmission Intensity")
        self.ax3.set_ylabel("Monitor Intensity")

        # Autorange the scatter plot
        self.ax3.set_xlim(np.min(selected_data1), np.max(selected_data1))
        self.ax3.set_ylim(np.min(selected_data2), np.max(selected_data2))

        # Refresh the canvas
        self.canvas3.draw()

    def synchronize_axes(self):
        """Synchronize the x-axis limits of both plots."""
        if self.ax1 and self.ax2:
            self.ax1.callbacks.connect('xlim_changed', self.update_ax2_limits)
            self.ax2.callbacks.connect('xlim_changed', self.update_ax1_limits)

    def update_ax2_limits(self, ax):
        """Update the x-axis limits of ax2 to match ax1."""
        if not self.synchronizing and self.ax2:
            self.synchronizing = True
            x_min, x_max = ax.get_xlim()
            self.ax2.set_xlim(x_min, x_max)
            self.canvas2.draw()
            self.synchronizing = False

    def update_ax1_limits(self, ax):
        """Update the x-axis limits of ax1 to match ax2."""
        if not self.synchronizing and self.ax1:
            self.synchronizing = True
            x_min, x_max = ax.get_xlim()
            self.ax1.set_xlim(x_min, x_max)
            self.canvas1.draw()
            self.synchronizing = False

    def autorange_y_axis(self):
        """Adjust the y-axis to fit the currently displayed region for both traces."""
        for ax, data, time_axis in zip([self.ax1, self.ax2], [self.data1, self.data2], [self.time_axis1, self.time_axis2]):
            if ax and data is not None:
                # Get the current x-axis limits
                x_min, x_max = ax.get_xlim()

                # Find the corresponding data range
                sample_min = int(x_min * self.sampling_rate)
                sample_max = int(x_max * self.sampling_rate)
                sample_min = max(0, sample_min)
                sample_max = min(len(data) - 1, sample_max)

                # Get the y-values in the current view
                y_values = data[sample_min:sample_max]

                # Adjust the y-axis limits
                if len(y_values) > 0:
                    y_min = np.min(y_values)
                    y_max = np.max(y_values)
                    padding = (y_max - y_min) * 0.05  # Add 5% padding
                    ax.set_ylim(y_min - padding, y_max + padding)
        self.canvas1.draw()
        self.canvas2.draw()

    def closeEvent(self, event):
        # Clean up the RectangleSelectors to prevent hanging
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