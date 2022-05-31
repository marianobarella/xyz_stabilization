# -*- coding: utf-8 -*-
"""
Created on Mon Dec 14 19:52:49 2015

@author: Federico Barabas
"""

import numpy as np
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

class linePlotWidget_pixel(QtGui.QWidget):
        
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        graphicsLayout = pg.GraphicsLayoutWidget()
        grid = QtGui.QGridLayout()
        
        self.setLayout(grid)
        self.linePlot = graphicsLayout.addPlot(row=0, col=0, 
                                               title="Line profile")
        self.linePlot.setLabels(bottom=('Pixel'),
                                left=('Counts'))
        
        grid.addWidget(graphicsLayout, 0, 0)

class linePlotWidget_spectrum(QtGui.QWidget):
        
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        graphicsLayout = pg.GraphicsLayoutWidget()
        grid = QtGui.QGridLayout()
        
        self.setLayout(grid)
        self.linePlot = graphicsLayout.addPlot(row=0, col=0, 
                                               title="Spectrum line profile")
        self.linePlot.setLabels(bottom=('Wavelength (nm)'),
                                left=('Counts'))
        
        grid.addWidget(graphicsLayout, 0, 0)
        
class linePlotWidget_max_spectrum(QtGui.QWidget):
        
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        graphicsLayout = pg.GraphicsLayoutWidget()
        grid = QtGui.QGridLayout()
        
        self.setLayout(grid)
        self.linePlot = graphicsLayout.addPlot(row=0, col=0, 
                                               title="Find peak max Spectrum")
        self.linePlot.setLabels(bottom=('Time (s)'),
                                left=('Wavelength max (nm)'))
        
        grid.addWidget(graphicsLayout, 0, 0)
        
class linePlotWidget_integrate(QtGui.QWidget):
        
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        
        graphicsLayout = pg.GraphicsLayoutWidget()
        grid = QtGui.QGridLayout()
        
        self.setLayout(grid)
        self.linePlot = graphicsLayout.addPlot(row=0, col=0, 
                                               title="Integrate Spectrum")
        self.linePlot.setLabels(bottom=('Time (s)'),
                                left=('Integrate Spectrum (counts)'))
        
        grid.addWidget(graphicsLayout, 0, 0)
        

# taken from https://www.mrao.cam.ac.uk/~dag/CUBEHELIX/cubehelix.py
def cubehelix(gamma=1.0, s=0.5, r=-1.5, h=1.0):
    def get_color_function(p0, p1):
        def color(x):
            xg = x ** gamma
            a = h * xg * (1 - xg) / 2
            phi = 2 * np.pi * (s / 3 + r * x)
            return xg + a * (p0 * np.cos(phi) + p1 * np.sin(phi))
        return color

    array = np.empty((256, 3))
    abytes = np.arange(0, 1, 1/256.)
    array[:, 0] = get_color_function(-0.14861, 1.78277)(abytes) * 255
    array[:, 1] = get_color_function(-0.29227, -0.90649)(abytes) * 255
    array[:, 2] = get_color_function(1.97294, 0.0)(abytes) * 255
    return array


class Grid():

    def __init__(self, viewBox, shape):

        self.showed = False
        self.vb = viewBox
        self.shape = shape

        pen = pg.mkPen(color=(255, 255, 0), width=1.5,
                       style=QtCore.Qt.DotLine, antialias=True)
        pen2 = pg.mkPen(color=(255, 255, 0), width=1,
                        style=QtCore.Qt.SolidLine, antialias=True)

        self.yline3 = pg.InfiniteLine(pen=pen2)
        self.xline3 = pg.InfiniteLine(pen=pen2, angle=0)
        self.rect0 = QtGui.QGraphicsRectItem()
        self.rect0.setPen(pen)
        self.rect1 = QtGui.QGraphicsRectItem()
        self.rect1.setPen(pen)
        self.rect2 = QtGui.QGraphicsRectItem()
        self.rect2.setPen(pen)
        self.circle = QtGui.QGraphicsEllipseItem()
        self.circle.setPen(pen)

        self.update(self.shape)

    def update(self, shape):
        self.yline3.setPos(0.5*shape[0])
        self.xline3.setPos(0.5*shape[1])
        self.rect0.setRect(0.5*(shape[0] - 82), 0.5*(shape[1] - 82), 82, 82)
        self.rect1.setRect(0.5*shape[0] - 64, 0.5*shape[1] - 64, 128, 128)
        self.rect2.setRect(0.5*shape[0] - 128, 0.5*shape[1] - 128, 255, 255)
        self.circle.setRect(0.5*shape[0] - np.sqrt(2)*128,
                            0.5*shape[1] - np.sqrt(2)*128,
                            np.sqrt(2)*255, np.sqrt(2)*255)

    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.addItem(self.xline3)
        self.vb.addItem(self.yline3)
        self.vb.addItem(self.rect0)
        self.vb.addItem(self.rect1)
        self.vb.addItem(self.rect2)
        self.vb.addItem(self.circle)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.xline3)
        self.vb.removeItem(self.yline3)
        self.vb.removeItem(self.rect0)
        self.vb.removeItem(self.rect1)
        self.vb.removeItem(self.rect2)
        self.vb.removeItem(self.circle)
        self.showed = False


class TwoColorGrid():

    def __init__(self, viewBox, side, pxs=512):

        self.showed = False
        self.vb = viewBox
        self.side = side              # side is 128 or 82, the grid size
        self.pxs = pxs

        pen = pg.mkPen(color=(255, 255, 0), width=1,
                       style=QtCore.Qt.SolidLine, antialias=True)
        pen2 = pg.mkPen(color=(255, 255, 0), width=0.75,
                        style=QtCore.Qt.DotLine, antialias=True)

        self.rectT = QtGui.QGraphicsRectItem()
        self.rectT.setPen(pen)
        self.rectR = QtGui.QGraphicsRectItem()
        self.rectR.setPen(pen)
        self.sqrT = QtGui.QGraphicsRectItem()
        self.sqrT.setPen(pen2)
        self.sqrR = QtGui.QGraphicsRectItem()
        self.sqrR.setPen(pen2)
        self.yLine = pg.InfiniteLine(pen=pen2)
        self.xLine = pg.InfiniteLine(pen=pen2, angle=0)
        self.xLineR = pg.InfiniteLine(pen=pen2, angle=0)

        self.setDimensions()

    def setDimensions(self):
        self.rectT.setRect(0.5*self.pxs - self.side,
                           0.5*(self.pxs - self.side), 2*self.side, self.side)
        self.rectR.setRect(0.5*self.pxs - self.side,
                           0.5*(self.pxs - (self.side*3 + 20)), 2*self.side,
                           self.side)
        self.sqrT.setRect(0.5*(self.pxs - self.side),
                          0.5*(self.pxs - self.side), self.side, self.side)
        self.sqrR.setRect(0.5*(self.pxs - self.side),
                          0.5*(self.pxs - (self.side*3 + 20)), self.side,
                          self.side)
        self.yLine.setPos(0.5*self.pxs)
        self.xLine.setPos(0.5*self.pxs)
        self.xLineR.setPos(0.5*self.pxs - self.side - 10)

#     def changeToSmall(self):
#         # shape is 128 or 82, the view size
#         self.rectT.setRect(0, self.side + 10, 2*self.side + 8.5, self.side - 1)
#         self.rectR.setRect(self.side - shape, self.side - shape,
#                            2*self.side + 8.5, self.side - 1)
#         self.sqrT.setRect(shape + 5 - 0.5*self.size, 2*self.side + 10 - shape,
#                           self.side - 1, self.side - 1)
# #        self.sqrR.setRect(0.5*(self.side - shape), 0.5*self.side - shape,
# #                          self.side - 1, self.side - 1)
#         self.yLine.setPos(0.5*shape + 5)
#         self.xLine.setPos(1.5*self.side + 10 + self.side - shape)
#         self.xLineR.setPos(0.5*self.side + self.side - shape)

    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.addItem(self.rectT)
        self.vb.addItem(self.rectR)
        self.vb.addItem(self.sqrT)
        self.vb.addItem(self.sqrR)
        self.vb.addItem(self.yLine)
        self.vb.addItem(self.xLine)
        self.vb.addItem(self.xLineR)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.rectT)
        self.vb.removeItem(self.rectR)
        self.vb.removeItem(self.sqrT)
        self.vb.removeItem(self.sqrR)
        self.vb.removeItem(self.yLine)
        self.vb.removeItem(self.xLine)
        self.vb.removeItem(self.xLineR)
        self.showed = False


class Crosshair():

    def __init__(self, viewBox):

        self.showed = False

        self.vLine = pg.InfiniteLine(pos=0, angle=90, movable=False)
        self.hLine = pg.InfiniteLine(pos=0, angle=0,  movable=False)
        self.vb = viewBox

    def mouseMoved(self, pos):
        if self.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.vb.mapSceneToView(pos)
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())

    def mouseClicked(self):
        try:
            self.vb.scene().sigMouseMoved.disconnect(self.mouseMoved)
        except:
            pass

    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.scene().sigMouseClicked.connect(self.mouseClicked)
        self.vb.scene().sigMouseMoved.connect(self.mouseMoved)
        self.vb.addItem(self.vLine, ignoreBounds=False)
        self.vb.addItem(self.hLine, ignoreBounds=False)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.vLine)
        self.vb.removeItem(self.hLine)
        self.showed = False


class Twolines():

    def __init__(self, viewBox, center, size):

        self.showed = False
        
        self.center = center
        self.size = size
        self.hLine_up = pg.InfiniteLine(pos  =  self.center + int((self.size-1)/2) + 1  , angle=0,  movable=False)
        self.hLine_down = pg.InfiniteLine(pos = self.center- int((self.size-1)/2), angle=0,  movable=False)
        self.vb = viewBox

    def mouseMoved(self, pos):
        
        if self.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.vb.mapSceneToView(pos)
            self.hLine_up.setPos(mousePoint.x()+ self.size) 
            self.hLine_down.setPos(mousePoint.x())

    def mouseClicked(self):
        try:
            self.vb.scene().sigMouseMoved.disconnect(self.mouseMoved)
        except:
            pass

    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.scene().sigMouseClicked.connect(self.mouseClicked)
        self.vb.scene().sigMouseMoved.connect(self.mouseMoved)
        self.vb.addItem(self.hLine_up, ignoreBounds=False)
        self.vb.addItem(self.hLine_down, ignoreBounds=False)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.hLine_up)
        self.vb.removeItem(self.hLine_down)
        self.showed = False
        
class TwolinesHorizontal_fixed():

    def __init__(self, viewBox, center, size):

        self.showed = False
        
        self.center = center
        self.size = size
        self.hLine_up = pg.InfiniteLine(pos  =  self.center + int((self.size-1)/2) + 1  , angle=0,  movable=False, pen='g')
        self.hLine_down = pg.InfiniteLine(pos = self.center- int((self.size-1)/2), angle=0,  movable=False, pen='g')
        self.vb = viewBox


    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.addItem(self.hLine_up, ignoreBounds=False)
        self.vb.addItem(self.hLine_down, ignoreBounds=False)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.hLine_up)
        self.vb.removeItem(self.hLine_down)
        self.showed = False

class TwolinesVertical_fixed():

    def __init__(self, viewBox, center, size):

        self.showed = False
        
        self.center = center
        self.size = size
        self.vLine_rigth = pg.InfiniteLine(pos  =  self.center + int((self.size-1)/2) + 1  , angle=90,  movable=False)
        self.vLine_left = pg.InfiniteLine(pos = self.center- int((self.size-1)/2), angle=90,  movable=False)
        self.vb = viewBox

    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.addItem(self.vLine_rigth, ignoreBounds=False)
        self.vb.addItem(self.vLine_left, ignoreBounds=False)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.vLine_rigth)
        self.vb.removeItem(self.vLine_left)
        self.showed = False
        
class Twolines_vertical():

    def __init__(self, viewBox, size):

        self.showed = False
        
        self.size = size
        self.vLine_up = pg.InfiniteLine(pos  = 3*self.size, angle=90,  movable=False)
        self.vLine_down = pg.InfiniteLine(pos = 2*self.size, angle=90,  movable=False)
        self.vb = viewBox

    def mouseMoved(self, pos):
        
        if self.vb.sceneBoundingRect().contains(pos):
            mousePoint = self.vb.mapSceneToView(pos)
            self.vLine_up.setPos(mousePoint.y()+ self.size) 
            self.vLine_down.setPos(mousePoint.y())

    def mouseClicked(self):
        try:
            self.vb.scene().sigMouseMoved.disconnect(self.mouseMoved)
        except:
            pass

    def toggle(self):
        if self.showed:
            self.hide()
        else:
            self.show()

    def show(self):
        self.vb.scene().sigMouseClicked.connect(self.mouseClicked)
        self.vb.scene().sigMouseMoved.connect(self.mouseMoved)
        self.vb.addItem(self.vLine_up, ignoreBounds=False)
        self.vb.addItem(self.vLine_down, ignoreBounds=False)
        self.showed = True

    def hide(self):
        self.vb.removeItem(self.vLine_up)
        self.vb.removeItem(self.vLine_down)
        self.showed = False


class ROI(pg.ROI):

    def __init__(self, shape, vb, pos, handlePos, handleCenter, *args,
                 **kwargs):

        self.mainShape = shape

        pg.ROI.__init__(self, pos, size=(shape, shape), pen='y', *args, **kwargs)
        self.addScaleHandle(handlePos, handleCenter, lockAspect=True)
        vb.addItem(self)

        self.label = pg.TextItem()
        self.label.setPos(self.pos()[0] + self.size()[0],
                          self.pos()[1] + self.size()[1])
        self.label.setText('{}x{}'.format(shape, shape))

        self.sigRegionChanged.connect(self.updateText)

        vb.addItem(self.label)

    def updateText(self):
        self.label.setPos(self.pos()[0] + self.size()[0],
                          self.pos()[1] + self.size()[1])
        size = np.round(self.size()).astype(np.int)
        self.label.setText('{}x{}'.format(size[0], size[0]))

    def hide(self, *args, **kwargs):
        super().hide(*args, **kwargs)
        self.label.hide()


class cropROI(pg.ROI):

    def __init__(self, shape, vb, *args, **kwargs):

        self.mainShape = shape

        pg.ROI.__init__(self, pos=(shape[0], shape[1]), size=(128, 128),
                        scaleSnap=True, translateSnap=True, movable=False,
                        pen='y', *args, **kwargs)
        self.addScaleHandle((0, 1), (1, 0))


