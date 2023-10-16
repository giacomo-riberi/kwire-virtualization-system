import adsk.core, adsk.fusion
import os
import traceback
from ...lib import fusion360utils as futil
from ... import config

import numpy as np

_app = adsk.core.Application.get()
_ui = _app.userInterface
_product = _app.activeProduct
_design = adsk.fusion.Design.cast(_product)
_rootComp = _design.rootComponent

# *** Specify the command identity information. ***
CMD_ID = f'kwirevirtsys'
CMD_NAME = 'kwire virtualization system'
CMD_Description = 'Calculate kwire position relative to 4 markers and 8 distances'

# Specify that the command will be promoted to the panel.
IS_PROMOTED = True

# *** Define the location where the command button will be created. ***
# This is done by specifying the workspace, the tab, and the panel, and the 
# command it will be inserted beside. Not providing the command to position it
# will insert it at the end.
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

markA_last: adsk.fusion.ConstructionPoint = None
markB_last: adsk.fusion.ConstructionPoint = None
markC_last: adsk.fusion.ConstructionPoint = None
markD_last: adsk.fusion.ConstructionPoint = None

# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = _ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Define an event handler for the command created event. It will be called when the button is clicked.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******** Add a button into the UI so the user can run the command. ********
    # Get the target workspace the button will be created in.
    workspace = _ui.workspaces.itemById(WORKSPACE_ID)

    # Get the panel the button will be created in.
    panel = workspace.toolbarPanels.itemById(PANEL_ID)

    # Create the button command control in the UI after the specified existing command.
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)

    # Specify if the command is promoted to the main toolbar. 
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # Get the various UI elements for this command
    workspace = _ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = _ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()


# Function that is called when a user clicks the corresponding button in the UI.
# This defines the contents of the command dialog and connects to the command related events.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Created Event')

    # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
    inputs = args.command.commandInputs

    markA_sel = inputs.addSelectionInput('marker_a', "marker A", "select point")
    markA_sel.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionPoints)
    markA_sel.setSelectionLimits(minimum=1, maximum=1)

    markB_sel = inputs.addSelectionInput('marker_b', "marker B", "select point")
    markB_sel.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionPoints)
    markB_sel.setSelectionLimits(minimum=1, maximum=1)

    markC_sel = inputs.addSelectionInput('marker_c', "marker C", "select point")
    markC_sel.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionPoints)
    markC_sel.setSelectionLimits(minimum=1, maximum=1)

    markD_sel = inputs.addSelectionInput('marker_d', "marker D", "select point")
    markD_sel.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionPoints)
    markD_sel.setSelectionLimits(minimum=1, maximum=1)

    _ = inputs.addValueInput('distP1A', 'P1 - A', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    _ = inputs.addValueInput('distP1B', 'P1 - B', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    _ = inputs.addValueInput('distP1C', 'P1 - C', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    _ = inputs.addValueInput('distP1D', 'P1 - D', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    
    _ = inputs.addValueInput('distP2A', 'P2 - A', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    _ = inputs.addValueInput('distP2B', 'P2 - B', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    _ = inputs.addValueInput('distP2C', 'P2 - C', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))
    _ = inputs.addValueInput('distP2D', 'P2 - D', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0))

    _ = inputs.addValueInput('kwirer', 'kwire radius', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(0.08))
    _ = inputs.addValueInput('kwirel', 'kwire lenght', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(11.0))

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.activate, command_activate, local_handlers=local_handlers)


def command_activate(args: adsk.core.CommandEventArgs):
    global markA_last, markB_last, markC_last, markD_last

    futil.log(f'{CMD_NAME}: Command Activate Event')

    inputs = args.command.commandInputs
    if markA_last != None:
        futil.log(f'\tReset markA selection to last one used: x,y,z -> {markA_last.geometry.asArray()}')
        markA_com: adsk.core.SelectionCommandInput = inputs.itemById('marker_a')
        markA_com.addSelection(markA_last)
        
    if markB_last != None:
        futil.log(f'\tReset markB selection to last one used: x,y,z -> {markB_last.geometry.asArray()}')
        markB_com: adsk.core.SelectionCommandInput = inputs.itemById('marker_b')
        markB_com.addSelection(markB_last)
    
    if markC_last != None:
        futil.log(f'\tReset markC selection to last one used: x,y,z -> {markC_last.geometry.asArray()}')
        markC_com: adsk.core.SelectionCommandInput = inputs.itemById('marker_c')
        markC_com.addSelection(markC_last)
    
    if markD_last != None:
        futil.log(f'\tReset markD selection to last one used: x,y,z -> {markD_last.geometry.asArray()}')
        markD_com: adsk.core.SelectionCommandInput = inputs.itemById('marker_d')
        markD_com.addSelection(markD_last)
        

# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Execute Event')

    try:
        def getCoord(cp):
            selcomin = adsk.core.SelectionCommandInput.cast(cp)
            cpcoord = adsk.fusion.ConstructionPoint.cast(selcomin.selection(0).entity).geometry.asArray()
            cpcoord = list(cpcoord)
            return cpcoord

        inputs = args.command.commandInputs
        markAcoord = getCoord(inputs.itemById('marker_a'))
        markBcoord = getCoord(inputs.itemById('marker_b'))
        markCcoord = getCoord(inputs.itemById('marker_c'))
        markDcoord = getCoord(inputs.itemById('marker_d'))

        P1 = trilaterate3D([markAcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP1A')).value],
                            markBcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP1B')).value],
                            markCcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP1C')).value],
                            markDcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP1D')).value]])
        
        P2 = trilaterate3D([markAcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP2A')).value],
                            markBcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP2B')).value],
                            markCcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP2C')).value],
                            markDcoord + [adsk.core.ValueCommandInput.cast(inputs.itemById('distP2D')).value]])

        create_cylinder(_rootComp,
                        P1,
                        P2,
                        adsk.core.ValueCommandInput.cast(inputs.itemById('kwirer')).value,
                        adsk.core.ValueCommandInput.cast(inputs.itemById('kwirel')).value)
        
    except:
        if _ui:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# funziona al 99%
def trilaterate3D(distances) -> adsk.core.Point3D:
    p1=np.array(distances[0][:3])
    p2=np.array(distances[1][:3])
    p3=np.array(distances[2][:3])       
    p4=np.array(distances[3][:3])
    r1=distances[0][-1]
    r2=distances[1][-1]
    r3=distances[2][-1]
    r4=distances[3][-1]
    e_x=(p2-p1)/np.linalg.norm(p2-p1)
    i=np.dot(e_x,(p3-p1))
    e_y=(p3-p1-(i*e_x))/(np.linalg.norm(p3-p1-(i*e_x)))
    e_z=np.cross(e_x,e_y)
    d=np.linalg.norm(p2-p1)
    j=np.dot(e_y,(p3-p1))
    x=((r1**2)-(r2**2)+(d**2))/(2*d)
    y=(((r1**2)-(r3**2)+(i**2)+(j**2))/(2*j))-((i/j)*(x))
    z1=np.sqrt(r1**2-x**2-y**2)
    z2=np.sqrt(r1**2-x**2-y**2)*(-1)
    ans1=p1+(x*e_x)+(y*e_y)+(z1*e_z)
    ans2=p1+(x*e_x)+(y*e_y)+(z2*e_z)
    dist1=np.linalg.norm(p4-ans1)
    dist2=np.linalg.norm(p4-ans2)
    if np.abs(r4-dist1)<np.abs(r4-dist2):
        return adsk.core.Point3D.create(ans1[0], ans1[1], ans1[2])
    else:
        return adsk.core.Point3D.create(ans2[0], ans2[1], ans2[2])


def create_cylinder(rootComp: adsk.fusion.Component, p1, p2, r, lenght):
    try:
        planes = rootComp.constructionPlanes
        planeInput = adsk.fusion.ConstructionPlaneInput.cast(planes.createInput())
        planeInput.setByPlane(adsk.core.Plane.create(p1, p1.vectorTo(p2)))   
        plane1 = rootComp.constructionPlanes.add(planeInput)
        sketch1 = rootComp.sketches.add(plane1)
        
        circles = sketch1.sketchCurves.sketchCircles
        circle1 = circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r)
        profile0 = sketch1.profiles.item(0)

        extrudes = adsk.fusion.ExtrudeFeatures.cast(rootComp.features.extrudeFeatures)
        dist = adsk.core.ValueInput.createByReal(lenght)
        extInput = extrudes.createInput(profile0, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(dist), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        extInput.isSolid = True
        ext = extrudes.add(extInput)

        cilinder = ext.bodies.item(0).createComponent()

        plane1.deleteMe()
        sketch1.deleteMe()
        # ext.dissolve() //!!!

        # axes = rootComp.constructionAxes
        # axisInput = axes.createInput()  
        # axisInput.setByLine(adsk.core.InfiniteLine3D.create(p1, p2))
        # axes.add(axisInput) 
        
    except:
        _ui.messageBox("couldn't extrude body")


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Preview Event')
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global markA_last, markB_last, markC_last, markD_last

    # futil.log(f'{CMD_NAME}: Changed input: {args.input.id}')

    def getCurrentSelectedMarker(id: str) -> adsk.fusion.ConstructionPoint:
        mark_comm = adsk.core.SelectionCommandInput.cast(args.input.commandInputs.itemById(id))
        if mark_comm.selectionCount < 1:
            futil.log(f'\tremoved {id} selection')
            return None
        else:
            futil.log(f'\tnew {id}: x,y,z -> {mark_comm.selection(0).entity.geometry.asArray()}')
            return mark_comm.selection(0).entity
    
    if args.input.id == "marker_a":
        markA_last = getCurrentSelectedMarker(args.input.id)
    if args.input.id == "marker_b":
        markB_last = getCurrentSelectedMarker(args.input.id)
    if args.input.id == "marker_c":
        markC_last = getCurrentSelectedMarker(args.input.id)
    if args.input.id == "marker_d":
        markD_last = getCurrentSelectedMarker(args.input.id)


# This event handler is called when the user interacts with any of the inputs in the dialog
# which allows you to verify that all of the inputs are valid and enables the OK button.
def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Validate Input Event')

    inputs = args.inputs
    
    # Verify the validity of the input values. This controls if the OK button is enabled or not.
    valueInput = inputs.itemById('value_input')
    if args.areInputsValid or valueInput.value >= 0:
        args.areInputsValid = True
    else:
        args.areInputsValid = False
        

# This event handler is called when the command terminates.
def command_destroy(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Destroy Event')

    global local_handlers
    local_handlers = []
