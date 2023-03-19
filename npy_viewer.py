# -*- coding: utf-8 -*-
"""
Created on Sun Mar 19 15:37:09 2023

@author: Mariano Barella and chatGPT
"""

import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QGraphicsScene, QGraphicsView, QInputDialog
# from PyQt5.QtGui import QImage, QPixmap, QInputDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle("Numpy Viewer")
        self.file_path = None
        self.image = None
        self.create_menu()
        self.create_graphics_view()

    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_file = file_menu.addAction("Open")
        open_file.triggered.connect(self.open_file_dialog)

    def create_graphics_view(self):
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)

    def open_file_dialog(self):
        self.file_path, _ = QFileDialog.getOpenFileName(self, "Open file", "", "Numpy files (*.npy)")
        if self.file_path:
            self.image = np.load(self.file_path)
            self.display_image()

    def display_image(self):
        if len(self.image.shape) == 2:
            # If the array is two-dimensional, plot it directly as y vs. x
            x = np.arange(self.image.shape[1])
            y = self.image.flatten()
        else:
            # If the array is not two-dimensional, ask for the sampling frequency of x
            x_sampling_frequency, _ = QInputDialog.getDouble(self, "X Sampling Frequency", "Enter the sampling frequency of the x variable:")
            if x_sampling_frequency:
                # Build the x array based on the length and sampling frequency
                x_sampling_period = 1/x_sampling_frequency
                x = np.arange(0, self.image.shape[0], x_sampling_period)
                y = self.image
            else:
                # If the user cancels or enters an invalid value, return without plotting
                return
        # Plot the data as y vs. x
        self.scene.clear()
        self.scene.addLine(0, 0, x[-1], 0)  # Draw a horizontal axis
        self.scene.addLine(0, 0, 0, y.max())  # Draw a vertical axis
        for i in range(len(x)-1):
            self.scene.addLine(x[i], y[i], x[i+1], y[i+1])  # Plot the data as a line
        self.view.setSceneRect(0, 0, x[-1], y.max())
        self.view.fitInView(self.view.sceneRect(), 1)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
