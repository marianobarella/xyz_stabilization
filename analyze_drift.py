import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QFileDialog, QPushButton, QLabel, QHBoxLayout, QScrollArea, QTextEdit
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("Drift Curve Visualizer")
        self.setGeometry(100, 100, 1600, 1000)

        # Create a central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add a label for instructions
        self.label = QLabel("Load drift curve files to visualize X, Y, and Z drifts", self)
        layout.addWidget(self.label)

        # Add buttons for loading files
        button_layout = QHBoxLayout()
        self.load_xy_button = QPushButton("Load XY Drift File", self)
        self.load_xy_button.clicked.connect(lambda: self.load_file("xy"))
        button_layout.addWidget(self.load_xy_button)

        self.load_z_button = QPushButton("Load Z Drift File", self)
        self.load_z_button.clicked.connect(lambda: self.load_file("z"))
        button_layout.addWidget(self.load_z_button)

        layout.addLayout(button_layout)

        # Create three plots for X, Y, and Z drifts
        self.figure_x = Figure()
        self.canvas_x = FigureCanvas(self.figure_x)
        self.toolbar_x = NavigationToolbar(self.canvas_x, self)

        self.figure_y = Figure()
        self.canvas_y = FigureCanvas(self.figure_y)
        self.toolbar_y = NavigationToolbar(self.canvas_y, self)

        self.figure_z = Figure()
        self.canvas_z = FigureCanvas(self.figure_z)
        self.toolbar_z = NavigationToolbar(self.canvas_z, self)

        # Add plots and toolbars to the layout
        plot_layout = QHBoxLayout()
        plot_layout.addWidget(self.canvas_x)
        plot_layout.addWidget(self.canvas_y)
        plot_layout.addWidget(self.canvas_z)
        layout.addLayout(plot_layout)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.addWidget(self.toolbar_x)
        toolbar_layout.addWidget(self.toolbar_y)
        toolbar_layout.addWidget(self.toolbar_z)
        layout.addLayout(toolbar_layout)

        # Add a scrollable text box for logs
        self.text_box = QTextEdit(self)
        self.text_box.setReadOnly(True)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.text_box)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Initialize variables
        self.time_xy = None
        self.x_drift = None
        self.y_drift = None
        self.time_z = None
        self.z_drift = None

        # Rectangle selectors for interactive selection
        self.selector_x = None
        self.selector_y = None
        self.selector_z = None

    def load_file(self, file_type):
        # Open a file dialog to select the appropriate file
        if file_type == "xy":
            file_path, _ = QFileDialog.getOpenFileName(self, "Open XY Drift File", "", "Data files (*.dat)")
            if file_path and "drift_curve_xy" in file_path:
                self.load_xy_file(file_path)
        elif file_type == "z":
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Z Drift File", "", "Data files (*.dat)")
            if file_path and "drift_curve_z" in file_path:
                self.load_z_file(file_path)

    def load_xy_file(self, file_path):
        try:
            # Load the data, skipping the first 4 rows (comments)
            data = np.loadtxt(file_path, skiprows=4)
            self.time_xy = data[:, 0] / 60  # Convert time to minutes
            self.x_drift = data[:, 1]  # Second column: X drift
            self.y_drift = data[:, 2]  # Third column: Y drift

            # Plot X and Y drifts
            self.plot_data(self.figure_x, self.canvas_x, self.time_xy, self.x_drift, "X Drift", "blue")
            self.plot_data(self.figure_y, self.canvas_y, self.time_xy, self.y_drift, "Y Drift", "green")

            # Add rectangle selectors for interactive selection
            self.selector_x = RectangleSelector(
                self.figure_x.axes[0],
                lambda eclick, erelease: self.on_select(eclick, erelease, "x"),
                useblit=True,
                button=[1],
                minspanx=5,
                spancoords='data',
                interactive=True
            )
            self.selector_y = RectangleSelector(
                self.figure_y.axes[0],
                lambda eclick, erelease: self.on_select(eclick, erelease, "y"),
                useblit=True,
                button=[1],
                minspanx=5,
                spancoords='data',
                interactive=True
            )

            # Log success
            self.text_box.append(f"Loaded XY drift file: {file_path}")
            self.text_box.append(f"Time range: {self.time_xy[0]:.2f} to {self.time_xy[-1]:.2f} minutes")
            self.text_box.append(f"X drift range: {np.min(self.x_drift):.2f} to {np.max(self.x_drift):.2f} nm")
            self.text_box.append(f"Y drift range: {np.min(self.y_drift):.2f} to {np.max(self.y_drift):.2f} nm\n")

            # Synchronize zoom if Z data is already loaded
            if self.time_z is not None:
                self.synchronize_axes()

        except Exception as e:
            self.text_box.append(f"Error loading XY drift file: {str(e)}\n")

    def load_z_file(self, file_path):
        try:
            # Load the data, skipping the first 4 rows (comments)
            data = np.loadtxt(file_path, skiprows=4)
            self.time_z = data[:, 0] / 60  # Convert time to minutes
            self.z_drift = data[:, 1]  # Second column: Z drift

            # Plot Z drift
            self.plot_data(self.figure_z, self.canvas_z, self.time_z, self.z_drift, "Z Drift", "red")

            # Add rectangle selector for interactive selection
            self.selector_z = RectangleSelector(
                self.figure_z.axes[0],
                lambda eclick, erelease: self.on_select(eclick, erelease, "z"),
                useblit=True,
                button=[1],
                minspanx=5,
                spancoords='data',
                interactive=True
            )

            # Log success
            self.text_box.append(f"Loaded Z drift file: {file_path}")
            self.text_box.append(f"Time range: {self.time_z[0]:.2f} to {self.time_z[-1]:.2f} minutes")
            self.text_box.append(f"Z drift range: {np.min(self.z_drift):.2f} to {np.max(self.z_drift):.2f} nm\n")

            # Synchronize zoom if XY data is already loaded
            if self.time_xy is not None:
                self.synchronize_axes()

        except Exception as e:
            self.text_box.append(f"Error loading Z drift file: {str(e)}\n")

    def plot_data(self, figure, canvas, time, data, title, color):
        # Clear the previous plot
        figure.clear()

        # Create a new plot
        ax = figure.add_subplot(111)
        ax.plot(time, data, linewidth=0.5, color=color)
        ax.set_title(title)
        ax.set_xlabel("Time (minutes)")
        ax.set_ylabel("Drift (nm)")

        # Redraw the canvas
        canvas.draw()

    def on_select(self, eclick, erelease, trace):
        # Get the selected region bounds in time (minutes)
        x1, x2 = sorted([eclick.xdata, erelease.xdata])

        # Ensure the selection is within bounds
        x1 = max(0, x1)
        if trace == "x" or trace == "y":
            x2 = min(np.max(self.time_xy), x2)
        elif trace == "z":
            x2 = min(np.max(self.time_z), x2)

        # Calculate mean and standard deviation for the selected region
        if trace == "x":
            selected_data = self.x_drift[(self.time_xy >= x1) & (self.time_xy <= x2)]
        elif trace == "y":
            selected_data = self.y_drift[(self.time_xy >= x1) & (self.time_xy <= x2)]
        elif trace == "z":
            selected_data = self.z_drift[(self.time_z >= x1) & (self.time_z <= x2)]

        mean = np.mean(selected_data)
        std = np.std(selected_data)

        # Log the results
        self.text_box.append(
            f"Selected region for {trace.upper()} Drift: [{x1:.2f} min, {x2:.2f} min]\n"
            f"Mean = {mean:.4f} nm, Std = {std:.4f} nm\n"
        )

    def synchronize_axes(self):
        """Synchronize the x-axis limits of all three plots."""
        if self.time_xy is not None and self.time_z is not None:
            # Get the minimum and maximum time range
            time_min = min(np.min(self.time_xy), np.min(self.time_z))
            time_max = max(np.max(self.time_xy), np.max(self.time_z))

            # Set the x-axis limits for all plots
            for ax in [self.figure_x.axes[0], self.figure_y.axes[0], self.figure_z.axes[0]]:
                ax.set_xlim(time_min, time_max)

            # Redraw the canvases
            self.canvas_x.draw()
            self.canvas_y.draw()
            self.canvas_z.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
