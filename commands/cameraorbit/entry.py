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

    body_sel = inputs.addSelectionInput('body', "body", "select body")
    body_sel.addSelectionFilter(adsk.core.SelectionCommandInput.Bodies)
    body_sel.setSelectionLimits(minimum=1, maximum=1)

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.activate, command_activate, local_handlers=local_handlers)


def command_activate(args: adsk.core.CommandEventArgs):
    global markA_last, markB_last, markC_last, markD_last

    futil.log(f'{CMD_NAME}: Command Activate Event')


def generate_orbit_point(center: adsk.core.Point3D, point_on_circumference: adsk.core.Point3D, num_points: int=200) -> list[adsk.core.Point3D]:
    radius = center.distanceTo(point_on_circumference)

    # Calculate the vector from the center to the point on circumference
    vec = np.array(point_on_circumference.asArray()) - np.array(center.asArray())
    
    # Normalize the vector
    vec_normalized = vec / np.linalg.norm(vec)
    
    # Generate a basis vector orthogonal to vec
    if vec_normalized[0] != 0 or vec_normalized[1] != 0:
        ortho_vec = np.array([-vec_normalized[1], vec_normalized[0], 0])
    else:
        ortho_vec = np.array([1, 0, 0])
    
    # Normalize the orthogonal vector
    ortho_vec_normalized = ortho_vec / np.linalg.norm(ortho_vec)
    
    # Generate points on the circumference
    points: list[adsk.core.Point3D] = []
    for i in range(num_points):
        angle = 2 * np.pi * i / num_points
        point = center.asArray() + radius * (np.cos(angle) * vec_normalized + np.sin(angle) * ortho_vec_normalized)
        points.append(adsk.core.Point3D.create(*point))
    
    return points


def closest_point_on_line(line_point, line_direction, point):
    line_point = np.array(line_point)
    line_direction = np.array(line_direction)
    point = np.array(point)
    
    # Calculate the vector from line_point to point
    line_to_point = point - line_point
    
    # Project line_to_point onto the line direction vector
    t = np.dot(line_to_point, line_direction) / np.dot(line_direction, line_direction)
    
    # Closest point on the line is the projection of point onto the line
    closest_point = line_point + t * line_direction
    
    return closest_point

# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Execute Event')

    try:
        inputs = args.command.commandInputs

        selcomin = adsk.core.SelectionCommandInput.cast(inputs.itemById('body'))
        body = adsk.fusion.BRepBody.cast(selcomin.selection(0).entity)

        futil.log(f'body name: {body.name}')

        camera = _app.activeViewport.camera
        camera.target = body.physicalProperties.centerOfMass
        camera.isSmoothTransition = False

        animation_duration = 3
        frames = 1000

        cpol = closest_point_on_line(adsk.core.Point3D.create(0, 0, 0).asArray(), adsk.core.Vector3D.create(0,0,1).asArray(), camera.eye.asArray())
        circumference_points = generate_orbit_point(adsk.core.Point3D.create(*cpol), camera.eye, frames)

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
