import os
import unittest
import numpy
import vtk, qt, ctk, slicer
import SimpleITK as sitk
from slicer.ScriptedLoadableModule import *
import logging

#
# ImageStacks
#

class ImageStacks(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "ImageStacks" # TODO make this more human readable by adding spaces
    self.parent.categories = ["Wizards"]
    self.parent.dependencies = []
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This is an example of scripted loadable module bundled in an extension.
It performs a simple thresholding on the input volume and optionally captures a screenshot.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.

#
# ImageStacksWidget
#

class ImageStacksWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModuleWidget.__init__(self,parent)
    self.logic = ImageStacksLogic()

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # Instantiate and connect widgets ...


    #
    # File area
    #
    filesCollapsibleButton = ctk.ctkCollapsibleButton()
    filesCollapsibleButton.text = "Files"
    filesCollapsibleButton.collapsed = False
    self.layout.addWidget(filesCollapsibleButton)
    # Layout within the files collapsible button
    filesFormLayout = qt.QFormLayout(filesCollapsibleButton)

    self.fileModel = qt.QStandardItemModel()
    self.fileTable = qt.QTableView()
    self.fileTable.horizontalHeader().stretchLastSection = True
    self.fileTable.horizontalHeader().visible = False
    self.fileTable.setModel(self.fileModel)
    filesFormLayout.addRow(self.fileTable)

    buttonLayout = qt.QHBoxLayout()
    self.addByBrowsingButton = qt.QPushButton("Browse for files")
    self.clearFilesButton = qt.QPushButton("Clear files")
    buttonLayout.addWidget(self.addByBrowsingButton)
    buttonLayout.addWidget(self.clearFilesButton)
    filesFormLayout.addRow(buttonLayout)

    #
    # output area
    #
    outputCollapsibleButton = ctk.ctkCollapsibleButton()
    outputCollapsibleButton.text = "Output"
    outputCollapsibleButton.collapsed = False
    self.layout.addWidget(outputCollapsibleButton)
    outputFormLayout = qt.QFormLayout(outputCollapsibleButton)

    #
    # output volume selector
    #
    #self.outputSelector = slicer.qMRMLSubjectHierarchyComboBox()
    self.outputSelector = slicer.qMRMLNodeComboBox()

    self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode",]
    #self.outputSelector.setNodeTypes(["vtkMRMLScalarVolumeNode",]) ; TODO: make nodeTypes property for SH box


    """
    TODO: which are supported and needed for SubjectHierarchy combo box.
    TODO: can we delete/rename/create as with SH
    self.outputSelector.defaultText = "Create new volume." ; # TODO any way to reset value?
    """
    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.showHidden = False
    self.outputSelector.showChildNodeTypes = False
    self.outputSelector.selectNodeUponCreation = False
    self.outputSelector.noneEnabled = True
    self.outputSelector.removeEnabled = True
    self.outputSelector.renameEnabled = True
    self.outputSelector.addEnabled = True
    self.outputSelector.setMRMLScene( slicer.mrmlScene )
    self.outputSelector.setToolTip( "Pick the output volume to populate or None to autogenerate." )
    outputFormLayout.addRow("Output Volume: ", self.outputSelector)

    self.spacing = ctk.ctkCoordinatesWidget()
    self.spacing.coordinates = "1,1,1"
    self.spacing.toolTip = "Set the colunm, row, slice spacing in mm"
    outputFormLayout.addRow("Spacing: ", self.spacing)


    self.loadButton = qt.QPushButton("Load files")
    outputFormLayout.addRow(self.loadButton)

    #
    # Add by name area
    #
    addByNameCollapsibleButton = ctk.ctkCollapsibleButton()
    addByNameCollapsibleButton.text = "Add files by name"
    addByNameCollapsibleButton.collapsed = True
    addByNameFormLayout = qt.QFormLayout(addByNameCollapsibleButton)
    # Don't enable Add by name for now - let's see if it's actually needed
    # self.layout.addWidget(addByNameCollapsibleButton)

    forExample = """
    directoryPath = '/Volumes/SSD2T/data/SlicerMorph/Sample_for_steve/1326_Rec'
    pathFormat = '%s/1326__rec%04d.png'
    start, end =  (50, 621)
    """

    self.archetypePathEdit = ctk.ctkPathLineEdit()
    addByNameFormLayout.addRow("Archetype file", self.archetypePathEdit)

    self.archetypeFormat = qt.QLineEdit()
    addByNameFormLayout.addRow("Name format", self.archetypeFormat)

    self.indexRange = ctk.ctkRangeWidget()
    self.indexRange.decimals = 0
    self.indexRange.maximum = 0
    addByNameFormLayout.addRow("Index range", self.indexRange)

    self.generateNamesButton = qt.QPushButton("Apply")
    self.generateNamesButton.toolTip = "Run the algorithm."
    self.generateNamesButton.enabled = False
    addByNameFormLayout.addRow(self.generateNamesButton)

    # connections
    self.addByBrowsingButton.connect('clicked()', self.addByBrowsing)
    self.clearFilesButton.connect('clicked()', self.fileTable.model().clear)
    self.archetypePathEdit.connect('currentPathChanged(QString)', self.validateInput)
    self.archetypePathEdit.connect('currentPathChanged(QString)', self.updateGUIFromArchetype)
    self.archetypeFormat.connect('textChanged(QString)', self.validateInput)
    self.generateNamesButton.connect('clicked()', self.onGenerateNames)
    # self.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.validateInput) # TODO - this is missing
    self.loadButton.connect('clicked()', self.onLoadButton)

    # refill last selection
    self.archetypePathEdit.currentPath = slicer.util.settingsValue("ImageStacks/lastArchetypePath", "")


    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.validateInput()

  def cleanup(self):
    pass

  def addByBrowsing(self):
    filePaths = qt.QFileDialog().getOpenFileNames()
    for filePath in filePaths:
      item = qt.QStandardItem()
      item.setText(filePath)
      self.fileModel.setItem(self.fileModel.rowCount(), 0, item)

  def currentNode(self):
    # TODO: this should be moved to qMRMLSubjectHierarchyComboBox::currentNode()
    if self.outputSelector.className() == "qMRMLSubjectHierarchyComboBox":
      shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
      selectedItem = self.outputSelector.currentItem()
      outputNode = shNode.GetItemDataNode(selectedItem)
    else:
      return self.outputSelector.currentNode()

  def validateInput(self):
    self.indexRange.enabled = len(self.archetypePathEdit.currentPath)
    self.generateNamesButton.enabled = len(self.archetypePathEdit.currentPath) and len(self.archetypeFormat.text)

  def updateGUIFromArchetype(self):
    properties = self.logic.propertiesFromArchetype(self.archetypePathEdit.currentPath)
    self.archetypeFormat.text = properties['fileName']
    self.indexRange.minimum = properties['minimum']
    self.indexRange.maximum = properties['maximum']
    self.indexRange.maximumValue = properties['maximum']

  def onGenerateNames(self):
    qt.QSettings().setValue("ImageStacks/lastArchetypePath", self.archetypePathEdit.currentPath)
    self.logic = ImageStacksLogic()
    self.logic.loadByArchetype(archetypePath = self.archetypePathEdit.currentPath,
                    archetypeFormat = self.archetypeFormat.text,
                    indexRange = (int(self.indexRange.minimumValue), int(self.indexRange.maximumValue + 1)),
                    outputNode = self.currentNode())

  def onLoadButton(self):
    paths = []
    for row in range(self.fileModel.rowCount()):
      item = self.fileModel.item(row)
      paths.append(item.text())

    properties = {}
    spacingString = self.spacing.coordinates
    properties['spacing'] = [float(element) for element in spacingString.split(",")]
    self.logic.loadByPaths(paths, self.currentNode(), properties)

#
# ImageStacksLogic
#

class ImageStacksLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def propertiesFromArchetype(self, archetypePath):
    properties = {}
    properties['directoryPath'] = os.path.dirname(archetypePath)
    properties['fileName'] = os.path.basename(archetypePath)
    properties['minimum'] = 0
    properties['maximum'] = len(os.listdir(properties['directoryPath']))
    return(properties)

  def loadByArchetype(self, archetypePath, archetypeFormat, indexRange, outputNode):

    dirName = os.path.dirname(archetypePath)
    pathFormat = os.path.join(dirName, archetypeFormat)
    paths = [ pathFormat % i for i in range(*indexRange) ]

    self.loadByPaths(paths, outputNode)

  def loadByPaths(self, paths, outputNode, properties={}):

    volumeArray = None
    sliceIndex = 0
    for path in paths:
      reader = sitk.ImageFileReader()
      reader.SetFileName(path)
      image = reader.Execute()
      sliceArray = sitk.GetArrayFromImage(image)
      if len(sliceArray.shape) == 3:
        sliceArray = sitk.GetArrayFromImage(image)[:,:,0]

      if volumeArray is None:
        shape = (len(paths), *sliceArray.shape)
        volumeArray = numpy.zeros(shape, dtype=sliceArray.dtype)
      volumeArray[sliceIndex] = sliceArray
      sliceIndex += 1

    if not outputNode:
      outputNode = slicer.vtkMRMLScalarVolumeNode()
      slicer.mrmlScene.AddNode(outputNode)

    if 'spacing' in properties:
      outputNode.SetSpacing(*properties['spacing'])

    slicer.util.updateVolumeFromArray(outputNode, volumeArray)
    slicer.util.setSliceViewerLayers(background=outputNode, fit=True)


class ImageStacksTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_ImageStacks1()

  def test_ImageStacks1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    directoryPath = '/Volumes/SSD2T/data/SlicerMorph/Sample_for_steve/1326_Rec'
    pathFormat = '%s/1326__rec%04d.png'
    start, end =  (50, 621)

    paths = [ pathFormat % (directoryPath, i) for i in range(start,end+1) ]
    collection = []

    slicer.modules.paths = paths
    slicer.modules.collection = collection

    import SimpleITK as sitk
    def readingTarget(paths=paths):
        for path in paths:
            reader = sitk.ImageFileReader()
            reader.SetFileName(path)
            image = reader.Execute()
            collection.append(image)


    import threading
    thread = threading.Thread(target=readingTarget)
    thread.start()

    qt.QTimer.singleShot(5000, lambda : print(len(collection)))
    qt.QTimer.singleShot(25000, thread.join)

    print(collection)
    slicer.modules.collection = collection

    self.delayDisplay('Test passed!')
