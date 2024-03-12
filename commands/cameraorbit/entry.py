import adsk.core, adsk.fusion
import os, time
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
CMD_ID = f'cameraorbit'
CMD_NAME = 'camera orbit'
CMD_Description = 'camera orbit around body'

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

    sel = inputs.addSelectionInput('pivot', "pivot", "select pivot")
    sel.addSelectionFilter(adsk.core.SelectionCommandInput.ConstructionLines)
    sel.addSelectionFilter(adsk.core.SelectionCommandInput.Bodies)
    sel.addSelectionFilter(adsk.core.SelectionCommandInput.Vertices)
    sel.setSelectionLimits(minimum=2, maximum=6)

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.activate, command_activate, local_handlers=local_handlers)


def command_activate(args: adsk.core.CommandEventArgs):
    global markA_last, markB_last, markC_last, markD_last

    futil.log(f'{CMD_NAME}: Command Activate Event')


def points_on_circle(center, start, line_direction, num_points) -> list[adsk.core.Point3D]:
    # Calculate radius
    radius = np.linalg.norm(np.array(start) - np.array(center))

    # Find a vector perpendicular to the line direction
    v1 = np.array([1, 0, 0]) if np.any(line_direction != np.array([1, 0, 0])) else np.array([1, 1, 0])
    perpendicular = np.cross(line_direction, v1)

    # Normalize the perpendicular vector
    perpendicular /= np.linalg.norm(perpendicular)

    # Generate points on the circle
    points = []
    for i in range(num_points):
        angle = 2 * np.pi * i / num_points
        # Calculate the point on the circle in the plane defined by perpendicular and line_direction
        point = center + radius * (np.cos(angle) * perpendicular + np.sin(angle) * np.cross(perpendicular, line_direction))
        points.append(point)

    return [adsk.core.Point3D.create(*cp) for cp in points]

def generate_circle(center: adsk.core.Point3D, normal: adsk.core.Vector3D, tangent_point: adsk.core.Point3D, num_points=200) -> list[adsk.core.Point3D]:
    """
    Generate points on a circle in 3D space.

    Args:
    - center: The center of the circle as a numpy array of shape (3,).
    - normal: The normal vector of the plane containing the circle as a numpy array of shape (3,).
    - tangent_point: The point tangent to the circle.
    - num_points: Number of points to generate on the circle.

    Returns:
    - points: A numpy array of shape (num_points, 3) containing the generated points.
    """
    radius = center.distanceTo(tangent_point)

    center = np.array(center.asArray(), dtype=float)
    normal = np.array(normal.asArray(), dtype=float)
    tangent_point = np.array(tangent_point.asArray(), dtype=float)

    # Normalize the normal vector
    normal = normal / np.linalg.norm(normal)

    # Generate an orthonormal basis for the plane containing the circle
    v1 = np.array([1.0, 0.0, 0.0], dtype=float)
    if np.allclose(v1, normal):
        v1 = np.array([0.0, 1.0, 0.0], dtype=float)
    v1 -= v1.dot(normal) * normal
    v1 /= np.linalg.norm(v1)
    v2 = np.cross(normal, v1)

    # Generate points on the circle using parametric equations
    theta = np.linspace(0, 2 * np.pi, num_points)
    points_on_plane = np.column_stack((np.cos(theta), np.sin(theta)))

    # Transform points to 3D
    points = center + radius * (np.outer(points_on_plane[:, 0], v1) + np.outer(points_on_plane[:, 1], v2))

    return [adsk.core.Point3D.create(*p) for p in points]


def project_point_on_line(vA, vB, vPoint) -> adsk.core.Point3D:
    vVector1 = vPoint - vA
    vVector2 = (vB - vA) / np.linalg.norm(vB - vA)

    d = np.linalg.norm(vA - vB)
    t = np.dot(vVector2, vVector1)

    vVector3 = vVector2 * t

    vClosestPoint = vA + vVector3

    return adsk.core.Point3D.create(*vClosestPoint)


def createPoint_by_point3D(occ: adsk.fusion.Occurrence, comp: adsk.fusion.Component, p: adsk.core.Point3D, name="") -> adsk.fusion.ConstructionPoint:
    "create visible construction point from a point 3D"
    if comp == None:
        comp = _rootComp
        points = _rootComp.constructionPoints
        
    points = comp.constructionPoints

    if occ == None:
        pointsInput = points.createInput()
    else:
        pointsInput = points.createInput(occ)

    pointsInput.setByPoint(p)
    pc = points.add(pointsInput)
    if name != "":
        pc.name = name
    return pc                                    


def createAxis_by_Line3D(occ: adsk.fusion.Occurrence, comp: adsk.fusion.Component, l: adsk.core.Line3D | adsk.core.InfiniteLine3D, name="") -> adsk.fusion.ConstructionAxis:
    "create visible construction axis from a line 3D"
    if comp == None:
        comp = _rootComp

    axes = comp.constructionAxes

    if occ == None:
        axisInput = axes.createInput()
    else:
        axisInput = axes.createInput(occ)
    
    if type(l) == adsk.core.Line3D:
        axisInput.setByLine(l.asInfiniteLine())
    elif type(l) == adsk.core.InfiniteLine3D:
        axisInput.setByLine(l)
    else:
        futil.log(f'createAxis_by_Line3D: input not supported')
    ca = axes.add(axisInput)
    if name != "":
        ca.name = name
    return ca


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Execute Event')

    try:
        inputs = args.command.commandInputs

        camera = _app.activeViewport.camera
        camera.isSmoothTransition = False
        animation_duration = 30
        frames = 3000

        selcomin = adsk.core.SelectionCommandInput.cast(inputs.itemById('pivot'))

        COMs = []
        for i in range(selcomin.selectionCount):
            entity = selcomin.selection(i).entity
            futil.log(f'entity type: {entity.classType()}')
            
            if entity.classType() == adsk.fusion.BRepBody.classType():
                # BODY
                body = adsk.fusion.BRepBody.cast(entity)
                futil.log(f'body name: {body.name}')
                
                COMs.append(body.physicalProperties.centerOfMass.asArray())
        
        for i in range(selcomin.selectionCount):
            entity = selcomin.selection(i).entity
            if entity.classType() == adsk.fusion.BRepVertex.classType():
                # VERTEX
                vertex = adsk.fusion.BRepVertex.cast(entity)
                futil.log(f'vertex geom: {vertex.geometry.asArray()}')
                
                COMs.append(vertex.geometry.asArray())

        camera.target = adsk.core.Point3D.create(*np.mean(COMs, axis=0))
        futil.log(f'COMs: {COMs} -  mean: {np.mean(COMs, axis=0)}')

        for i in range(selcomin.selectionCount):
            entity = selcomin.selection(i).entity
            if entity.classType() == adsk.fusion.ConstructionAxis.classType():
                # LINE
                line = adsk.fusion.ConstructionAxis.cast(entity)
                futil.log(f'line name: {line.name}')

                eye = createPoint_by_point3D(None, _rootComp, camera.eye, "eye")
                res = _app.measureManager.measureMinimumDistance(line, eye)
                eye_projection = res.positionOne
                # _ = createPoint_by_point3D(None, _rootComp, eye_projection, "eye_projection") # debug

                # need to create a line from axis_point to camera.target as line.geometry is in its own coordinate system
                line = createAxis_by_Line3D(None, _rootComp, adsk.core.Line3D.create(eye_projection, camera.target), "line")
                circumference_points = generate_circle(eye_projection, line.geometry.direction, camera.eye, frames)
                # for cp in circumference_points: # debug
                #     _ = createPoint_by_point3D(None, _rootComp, cp, "circumference_point")

                # eye.deleteMe()  # debug
                # line.deleteMe() # debug
                

        # prepare camera for recording
        camera.eye = circumference_points[0]
        _app.activeViewport.camera = camera
        _app.activeViewport.refresh()
        time.sleep(1)

        futil.log(f'starting orbit animation...')

        for p in circumference_points:
            start_time = time.time()
            camera.eye = p
            _app.activeViewport.camera = camera
            _app.activeViewport.refresh()
            adsk.doEvents()
            time_to_wait = (animation_duration/frames) - (time.time()-start_time)
            time.sleep(time_to_wait if time_to_wait > 0 else 0)
        
        futil.log(f'stopped orbit animation...')

    except Exception as e:
        if _ui:
            _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Preview Event')
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
    global markA_last, markB_last, markC_last, markD_last

    futil.log(f'{CMD_NAME}: Changed input: {args.input.id}')

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

    time.sleep(1)
