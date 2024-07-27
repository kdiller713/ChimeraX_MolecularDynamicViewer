from chimerax.ui import HtmlToolInstance
from chimerax.atomic import AtomicStructure, Atoms
from chimerax.core.commands import run
# Note the following API is still marked as Experimental
from chimerax.movie.moviecmd import movie_record, movie_encode
from chimerax.surface.surfacecmds import surface

from Qt.QtWidgets import QFileDialog

from numpy import array, float64

import os.path
import pathlib

DISPLAY_NAME = "Molecular Dynamics Viewer"

class MolecularDynamicsTool(HtmlToolInstance):
    
    '''
     # Properties for the tool
    '''
    SESSION_ENDURING = False
    SESSION_SAVE = False
    CUSTOM_SCHEME = "kmd"
    
    def __init__(self, session, tool_name):
        super().__init__(session, tool_name, size_hint=(500, 500), show_http_in_help=False)
        self.display_name = DISPLAY_NAME
        self._build_ui()
        
        self.atomStruct = None
        self.atomLocation = []
        self.surfacePositions = []
        self.attributeFile = False
        
    # Loads the html view to be shown
    def _build_ui(self):
        html_file = os.path.join(os.path.dirname(__file__), "dynamics.html")
        self.html_view.setUrl(pathlib.Path(html_file).as_uri())
        
    # This is to delete the model from the view
    def delete(self):
        super(HtmlToolInstance, self).delete()
        self.deleteModel()
        
    '''
     # This handles when a window.location becomes kmd:<command>
     #
     # @param url - The command
    '''
    def handle_scheme(self, url):
        command = url.path()
        
        if command.startswith("log"):
            self.session.logger.info(command[len("log_"):])
        elif command == "Open":
            self.openFile()
        elif command.startswith("FrameChange"):
            frame = int(command[len("FrameChange_T_"):])
            self.changeModel(frame, command[12] == 'T')
        elif command == "MovieDone":
            movie_encode(self.session, output=[self.movieName], format="h264")
        elif command == "MovieStart":
            fileName, filt = QFileDialog.getSaveFileName(caption="Save Movie", filter="MP4 File (*.mp4)")
            
            if fileName == "":
                return
            
            if fileName[-4:] != ".mp4":
                fileName = fileName + ".mp4"
            
            self.movieName = fileName
            movie_record(self.session)
            self.html_view.runJavaScript("startMovie()")
        elif command == "Attribute":
            self.loadAttributeFile();
        else:
            self.session.logger.info("Unknown Command: " + str(url))
        
    def loadAttributeFile(self):
        fileName, filt = QFileDialog.getOpenFileName(caption="Open Attribute File", filter="Attribute File (*.dat)")
        
        if fileName == "":
            return
        
        fileObj = open(fileName)
        lines = fileObj.readlines()[3:]
        fileObj.close()
        mapVals = {}
        
        for line in lines:
            parts = line.split('\t')[1:]
            mapVals[int(parts[0][1:])] = float(parts[1])
        
        maxValue = max(mapVals.values())
        minValue = min(mapVals.values())
        midValue = (maxValue + minValue) / 2
        
        # Color from min (blue) to mid (white) to max (red)
        
        for key in mapVals.keys():
            value = mapVals[key]
            per = (value - minValue) / (midValue - minValue) - 1
            color = abs(per) * 255
            colorSet = [255, 255 - color, 255 - color, 255] if per > 0 else [255 - color, 255 - color, 255, 255]
            colorSet = array(colorSet)
            
            self.atomStruct.residues[key - 1].ribbon_color = colorSet
            self.atomStruct.residues[key - 1].atoms.colors = colorSet
        
        js = "attributeName = '" + fileName.split("/")[-1] + "';updateDisplay()"
        self.html_view.runJavaScript(js)
        self.attributeFile = True
        
        if self.atomStruct.surfaces() != []:
            run(self.session, "color #" + self.atomStruct.surfaces()[0].id_string + " fromatoms", log=False)
    
    # This is to remove model for changing
    def deleteModel(self):
        if self.atomStruct == None:
            return
        
        if self.atomStruct.deleted:
            return
        
        if self.atomStruct.surfaces() != []:
            self.session.models.remove([self.atomStruct.surfaces()[0]])
            
        self.session.models.remove([self.atomStruct])
        self.attributeFile = False
        self.atomStruct = None
        self.atomLocation = []
        self.surfacePositions = []
        js = "modelName = null; frameCount = 0; reset();"
        self.html_view.runJavaScript(js)
    
    # This is to move the atoms
    def changeModel(self, frame, surf):
        if self.atomStruct.deleted:
            js = "modelName = null; frameCount = 0; reset();"
            self.html_view.runJavaScript(js)
            return
        
        locs = self.atomLocation[frame]
        atms = self.atomStruct.atoms
        
        if(len(locs) != len(atms.coords)):
            newLocs = []
            for ind in range(len(atms.coords)):
                newLocs.append(locs[atms.coord_indices[ind]])
            locs = newLocs
                
        # Update the final locs
        atms.coords = locs
        
        if surf:
            ### Need to recalculate the surfce here
            if self.atomStruct.surfaces() == []:
                surface(self.session, atoms=self.atomStruct.atoms)
            else:
                surfPos = self.surfacePositions[frame]
                
                if surfPos is None:
                    self.session.models.remove([self.atomStruct.surfaces()[0]])
                    surface(self.session, atoms=self.atomStruct.atoms)
                    self.surfacePositions[frame] = self.atomStruct.surfaces()[0]
                else:
                    self.session.models.remove([self.atomStruct.surfaces()[0]])
                    self.atomStruct.add([surfPos])
            ###
            run(self.session, "color #" + self.atomStruct.surfaces()[0].id_string + " fromatoms", log=False)
        elif self.atomStruct.surfaces() != []:
            self.session.models.remove([self.atomStruct.surfaces()[0]])
    
    # This opens a file
    def openFile(self):
        fileName, filt = QFileDialog.getOpenFileName(caption="Open PDB Trajectory File", filter="PDB File (*.pdb)")
        
        if fileName == "":
            return
        
        if self.atomStruct != None:
            self.deleteModel()
        
        # This creates a simple Oxygen atom
        # Need to get this to display
        self.atomStruct = AtomicStructure(self.session)
        
        myFile = open(fileName)
        
        coords = []
        prevRes = None
        res = None
        modelNum = -1
        
        for line in myFile:
            if line.startswith("MODEL"):
                modelNum = modelNum + 1
                coords = []
                prevRes = None
                res = None
            elif line.startswith("ENDMDL"):
                self.atomLocation.append(array(coords))
            elif line.startswith("ATOM") or line.startswith("HETATM"):
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
                
                name = line[12:16].strip()
                resName = line[17:20].strip()
                chain = line[21]
                resSeq = line[22:26].strip()
                element = line[76:78].strip()
                
                if element == "H":
                    continue
                
                coords.append([x, y, z])
                
                if modelNum != 0:
                    continue
                
                if resName + resSeq != prevRes:
                    prevRes = resName + resSeq
                    res = self.atomStruct.new_residue(resName, chain, int(resSeq))
                    
                atom = self.atomStruct.new_atom(name, element)
                atom.coord = array([x, y, z], dtype=float64)
                res.add_atom(atom)
        
        myFile.close()
        self.atomStruct.connect_structure()
        
        self.session.models.add([self.atomStruct])
        
        for i in range(len(self.atomLocation)):
            self.surfacePositions.append(None)
        
        self.atomStruct.atoms.coords = self.atomLocation[0]
        fileName = fileName.split("/")[-1]
        
        js = "modelName = '" + fileName + "'; frameCount = " + str(len(self.atomLocation)) + "; reset();"
        self.html_view.runJavaScript(js)
        run(self.session, "lighting full", log=False)
