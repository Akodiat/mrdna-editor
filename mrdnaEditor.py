import numpy as np
from mrdna.readers import read_cadnano
from mrdna.coords import readArbdCoords
from mrdna.coords import rotationAboutAxis
#from mrdna.simulate import multiresolution_simulation as simulate

import pythreejs as three
from ipywidgets import HTML, VBox, HBox, Button

class BeadMesh(three.Mesh):
    def __init__(self, bead, color, **kwargs):
        super().__init__(
            geometry = three.SphereGeometry(
                    radius=3, widthSegments=10, heightSegments=10),
            material = three.MeshLambertMaterial(color=color),
            position = bead.position.tolist(),
            **kwargs)
        self.bead = bead

class ConnectionLine(three.LineSegments2):
    def __init__(self, segment, color, **kwargs):
        g = three.LineSegmentsGeometry(positions=self.getPositions(segment))
        m = three.LineMaterial(linewidth=10, color=color, light=True)
        super().__init__(g, m)
        self.segment = segment
        
    def getPositions(self, segment):
        positions = []
        # Intrahelical connections:
        if len(segment.beads) > 1:
            positions += [[
                p.position.tolist(),
                segment.beads[i+1].position.tolist()
            ] for i, p in enumerate(segment.beads) if i+1<len(segment.beads)]
        # Extrahelical connections:
        if len(segment.connections) > 0:
            positions += [[
                c.A.particle.position.tolist(), 
                c.B.particle.position.tolist()] for c in segment.connections]
        return positions        

    def update(self):
        self.geometry.positions = self.getPositions(self.segment)

class Editor():
    
    def __init__(self):
        self.beadColor = '#3d4d52'
        self.selectedBeadColor = '#dc5050'
        self.lineColor = '#99c9e7'
        self.view = None
        self.beadResArgs = {}
    
    def drawSegment(self, segment):
        beads = [BeadMesh(bead, self.beadColor) for bead in segment.beads]
        return three.Group(
                children = beads + [ConnectionLine(segment, self.lineColor)]
        )
    
    def increaseSelection(self, button):
        neigboursToSelected = [
                n for s in self.selected
                for n in s.bead.intrahelical_neighbors
        ]
        neigbourMeshes = [
                m for m in self.allMeshes 
                if m.bead in neigboursToSelected and m not in self.selected
        ]
        self.selected.update(neigbourMeshes)
        for beadMesh in neigbourMeshes:
            beadMesh.material.color = self.selectedBeadColor
        self.coord_label.value = "{} beads selected".format(len(self.selected))
    
    def decreaseSelection(self, button):
        selectedBeads = [s.bead for s in self.selected]
        frontier = [s for s in self.selected
                    if not set(s.bead.intrahelical_neighbors
                               ).issubset(selectedBeads)]
        for beadMesh in frontier:
            beadMesh.material.color = self.beadColor
            self.selected.remove(beadMesh)
        self.coord_label.value = "{} beads selected".format(len(self.selected))
    
    def clearSelection(self):
        for beadMesh in self.selected:
            beadMesh.material.color = self.beadColor
        self.selected.clear()
        self.coord_label.value = "{} beads selected".format(len(self.selected))
        
    def selectBeadByFunction(self, f):
        for m in self.allMeshes:
            if f(m.bead):
                self.selected.add(m)
                m.material.color = self.selectedBeadColor
    
    def updateLines(self):
        for x in sum(
                (segment.children for segment in self.selectable.children), ()
        ):
            if x.type is 'LineSegments2':
                x.update()
                
    def rotate(self, beads, rotAxis, rotAngle, about='itself'):
        R = rotationAboutAxis(np.array(rotAxis), rotAngle)
        
        if about is 'itself':
            # Calculate selection centre
            dr = (sum(bm.bead.position for bm in beads) 
                  / len(self.selected))
        elif about is None:
            dr = np.zeros(3)
        else:
            dr = np.array(about)
        for bm in self.selected:
            r = bm.bead.position
            bm.bead.position = R.dot(r-dr) + dr
            bm.position = bm.bead.position.tolist()
        self.updateLines()
    
    def translate(self, beads, translateVector):
        for beadMesh in beads:
            beadMesh.bead.position += np.array(translateVector)
            beadMesh.position = beadMesh.bead.position.tolist()
        self.updateLines()
        
    def translateSelected(self, translateVector):
        self.translate(self.selected, translateVector)
    
    # Called by the click_picker
    def selectBead(self, change):
        beadMesh = change.owner.object
        if beadMesh not in self.selected and beadMesh is not None:
            self.selected.add(beadMesh)
            beadMesh.material.color = self.selectedBeadColor
        else:
            self.selected.remove(beadMesh)
            beadMesh.material.color = self.beadColor
        self.coord_label.value = "Clicked on {}, {} beads selected".format(
                beadMesh.bead, len(self.selected))
    
    def regenerateBeads(self, **kwargs):
        self.beadResArgs = kwargs
        self.clearSelection()
        self.model.generate_bead_model(**kwargs)
        self.selectable.children = [
                self.drawSegment(s) for s in self.model.segments
        ]
        self.allMeshes[:] = [x for x in sum((
                segment.children for segment in self.selectable.children), ()
            ) if x.type is 'Mesh']
    
    def simulate(self):
        self.name = self.filename.split('.')[0]
        self.model.simulate(output_name = self.name, directory='sim_'+self.name,
                   num_steps=1e5, output_period=1e4)
        coords = readArbdCoords('{}/output/{}.restart'.format(
                'sim_'+self.name, self.name))
        print("Loaded a {}-by-{} numpy array of coordinates".format(
                *coords.shape)
        )
        self.model.update_splines(coords)
        self.model.generate_bead_model(**self.beadResArgs)
        self.selectable.children = [
                self.drawSegment(s) for s in self.model.segments
        ]
        self.allMeshes[:] = [x for x in sum((
                segment.children for segment in self.selectable.children), ()
            ) if x.type is 'Mesh']
    
    def loadCadnano(self, filename):
        self.filename = filename
        self.model = read_cadnano(filename)
        self.selectable = three.Group(children=[
                self.drawSegment(s) for s in self.model.segments
        ])
        self.allMeshes = [x for x in sum((
                segment.children for segment in self.selectable.children), ()
                ) if x.type is 'Mesh']
        self.selected = set()
    
    
    def getView(self, regenerateView = False,
                viewWidth = 600, viewHeight = 400):
        if regenerateView or self.view is None:
            center = self.model.get_center()
            camera = three.PerspectiveCamera(
                    position = (center + np.array([0,200,0])).tolist(),
                    aspect = viewWidth / viewHeight)
            key_light = three.DirectionalLight(position=[0, 10, 10])
            ambient_light = three.AmbientLight()
            
            scene = three.Scene(children = [
                    self.selectable, camera, key_light, ambient_light])
            
            three.Picker(controlling=scene, event='mousemove')
            controller = three.OrbitControls(
                    controlling=camera,
                    screenSpacePanning=True,
                    target=center.tolist())
            camera.lookAt(center.tolist())
            
            self.coord_label = HTML('Select beads by double-clicking')
            selIncrButton = Button(description='Increase selection')
            selIncrButton.on_click(self.increaseSelection)
            selDecrButton = Button(description='Decrease selection')
            selDecrButton.on_click(self.decreaseSelection)
            
            click_picker = three.Picker(
                    controlling=self.selectable, event='dblclick')
            click_picker.observe(self.selectBead, names=['point'])
            
            renderer = three.Renderer(
                    camera=camera, scene=scene, 
                    controls=[controller, click_picker],
                    width=viewWidth, height=viewHeight, antialias=True)
            
            self.view = VBox([
                    self.coord_label,
                    renderer,
                    HBox([selDecrButton, selIncrButton])
            ])
        return self.view

    def vmd(self, *args):
        import subprocess
        import sys
        cmd = ['vmd']
        for a in args:
            cmd.extend( a.split() )
        print("Calling '{}'".format( " ".join(cmd) ))
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
    
    def viewInVMD(self):
        self.vmd('-e','load-mrdna.tcl','-args','sim_'+self.name)