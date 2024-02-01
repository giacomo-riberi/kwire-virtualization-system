import adsk.core, adsk.fusion
import os, string
import traceback
from ...lib import fusion360utils as futil
from ... import config
import json
import pyperclip
from itertools import combinations
import math

import numpy as np
from . import data

_app = adsk.core.Application.get()
_ui = _app.userInterface
_product = _app.activeProduct
_design = adsk.fusion.Design.cast(_product)
_rootComp = _design.rootComponent

# *** Specify the command identity information. ***
CMD_ID = f'kwirevirtsys_fast'
CMD_NAME = 'kwire virtualization system - fast'
CMD_Description = 'Calculate kwire position relative to 4 markers and 8 distances - adapted for faster database manual operations'

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

kwirer: float = 0.08 # kwire radius in cm
kwirel: float = 10.8 # kwire lenght in cm

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

    _ = inputs.addStringValueInput('PA_data_str', 'import PA json data')

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.activate, command_activate, local_handlers=local_handlers)


def command_activate(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME}: Command Activate Event')
        

# This event handler is called when the command needs to compute a new preview in the graphics window.
def command_preview(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Preview Event')
    inputs = args.command.commandInputs


# This event handler is called when the user changes anything in the command dialog
# allowing you to modify values of other inputs based on that change.
def command_input_changed(args: adsk.core.InputChangedEventArgs):
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

    global local_handlers
    local_handlers = []


# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Execute Event')

    def get_markers(PA_data: data.PAdata) -> dict[str, adsk.core.Point3D] | None:
        found = {}

        for marker_letter, marker_name in PA_data.markers.items():
            # marker_letter = "A"
            # name          = "M:3"
            occ = _rootComp.allOccurrences.itemByName(marker_name)
            if occ == None:
                futil.log(f"getMarkers: {marker_name} not found")
                return None

            cp = occ.component.originConstructionPoint.geometry            
            cp.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis
            found[marker_letter] = cp
        
        return found

    def get_anatomy_structs(PA_data: data.PAdata) -> dict[str, adsk.fusion.BRepBody] | None:
        found = {}
        found_count = 0
        found_expected_count = len(PA_data.anatomy)

        for k, v in PA_data.anatomy.items():
            for occ in _rootComp.allOccurrences:
                for brb in occ.bRepBodies:
                    if brb.name == k:
                        # futil.log(f"\tfound anatomy struct {k} in {occ.name}") # debug
                        found[k] = brb
                        found_count += 1
        
        if found_count == found_expected_count:
            return found
        else:
            futil.log(f"\tfound unexpected number of anatomy structs")
            return None
    
    def get_skin() -> adsk.fusion.BRepBody | None:
        for occ in _rootComp.allOccurrences:
            for brb in occ.bRepBodies:
                if brb.name == "skin":
                    return brb
        
    def get_kwire_target(PA_data: data.PAdata) -> tuple[adsk.fusion.Occurrence, adsk.fusion.Component, adsk.fusion.BRepBody, adsk.core.Point3D, adsk.fusion.ConstructionAxis, adsk.core.Vector3D]:
        "returns normalized vector"
        
        for occ in _rootComp.allOccurrences:
            # futil.log(f'occurrence name: {occ.name}') # debug
            if occ.name == PA_data.target: # ECP:1
                target_occ = occ
                target_comp = target_occ.component

                target_brb = target_comp.bRepBodies.itemByName("target")

                p1 = target_comp.constructionPoints.itemByName("target P1").geometry
                p1.transformBy(target_occ.transform2) # must be transformed from the occurrence coordinate axis
                
                for occ in _rootComp.allOccurrences:
                    if occ.name == "kwires:1":
                        kwire_comp = occ.component
                        p2 = kwire_comp.constructionPoints.itemByName(f"{PA_data.target} target P2").geometry # ECP:1 target P2
                        p2.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis

                _, _, vector = target_comp.zConstructionAxis.geometry.getData()
                vector.transformBy(target_occ.transform2) # must be transformed from the occurrence coordinate axis
                vector.normalize()
                
                return target_occ, target_comp, target_brb, p1, p2, vector
    
    def get_kwire_PA(PA_data: data.PAdata) -> tuple[adsk.fusion.Occurrence, adsk.fusion.Component]:
        "returns normalized vector"
        
        for occ in _rootComp.allOccurrences:
            # futil.log(f'occurrence name: {occ.name}') # debug
            if occ.name == f"{PA_data.target} PA phase:{PA_data.phase}:1": # "ECP:1 PA phase:0:1"
                PA_occ = occ
                PA_comp = PA_occ.component
                
                return PA_occ, PA_comp

    def intersect_point(brb: adsk.fusion.BRepBody, P: adsk.core.Point3D, dir: adsk.core.Vector3D, maxtests: int, precision: int, precisionStart: int = None) -> adsk.core.Point3D | None:
        "estimate point of intersection of a vector starting from P through a body; dir should be normalized"
        
        # copy as the variable seems to be referenced by a sort of pointer
        # brb = brb.copy() # not this as it will fail (the original one must be used)
        P   = P.copy()
        dir = dir.copy()

        if precisionStart == None:
            precisionStart = precision
        
        pOut = P.copy()
        while True:
            maxtests -= 1
            P.translateBy(dir)
            # createPoint_by_point3D(P) # debug
            # futil.log(f"precision: {precision} - maxtests: {maxtests} - containment: {brb.pointContainment(P)}") # debug
            if maxtests < 0 and precision == precisionStart:
                # point was not found
                return None
            if maxtests < 0 and precision != precisionStart:
                return P
            if brb.pointContainment(P) == 0: # entered the body
                if precision == 0:
                    return P
                else:
                    dir.scaleBy(0.1)
                    return intersect_point(brb, pOut, dir, maxtests, precision-1)
            pOut = P.copy()
            
    try:
        inputs = args.command.commandInputs


        # -------------------------- DATA JSON ------------------------- #
        PA_data = data.PAdata(**json.loads(adsk.core.StringValueCommandInput.cast(inputs.itemById('PA_data_str')).value))
        markers           = get_markers(PA_data)
        bodies            = get_anatomy_structs(PA_data)
        skin_brb          = get_skin()


        # ------------------------ KWIRE TARGET ------------------------ #
        kwire_target_occ, kwire_target_comp, kwire_target_brb, kwire_target_P1, kwire_target_P2, kwire_target_vector = get_kwire_target(PA_data)
        kwire_target_P2_estimated = intersect_point(skin_brb, kwire_target_P1, kwire_target_vector, 200, 12)

        kwire_target_TIP = kwire_target_comp.originConstructionPoint.geometry
        kwire_target_TIP.transformBy(kwire_target_occ.transform2)

        kwire_target_P1P2_estimated = adsk.core.Line3D.create(kwire_target_P1, kwire_target_P2_estimated)
        kwire_target_P1TIP = adsk.core.Line3D.create(kwire_target_P1, kwire_target_TIP)

        # _ = createPoint_by_point3D(kwire_target_occ, kwire_target_comp, kwire_target_P1, f"debug target P1") # debug
        # _ = createPoint_by_point3D(kwire_target_occ, kwire_target_comp, kwire_target_P2_estimated, f"debug target P2_estimated") # debug
        # _ = createPoint_by_point3D(kwire_target_occ, kwire_target_comp, kwire_target_TIP, f"debug target TIP") # debug
        # _ = createAxis_by_Line3D(kwire_target_occ, kwire_target_comp, kwire_target_P1P2_estimated, f"debug target P1P2_estimated") # debug
        # _ = createAxis_by_Line3D(kwire_target_occ, kwire_target_comp, kwire_target_P1TIP, f"debug target P1TIP") # debug

        # -------------------------- KWIRE PA -------------------------- #

        kwire_PA_occ, kwire_PA_comp = get_kwire_PA(PA_data)

        kwire_PA_P1, kwire_PA_P1_mean = trilaterate3D_4spheres(
                        markers["A"], PA_data.P1A/10,
                        markers["B"], PA_data.P1B/10,
                        markers["C"], PA_data.P1C/10,
                        markers["D"], PA_data.P1D/10)
        
        kwire_PA_P2, kwire_PA_P2_mean = trilaterate3D_4spheres(
                        markers["A"], PA_data.P2A/10,
                        markers["B"], PA_data.P2B/10,
                        markers["C"], PA_data.P2C/10,
                        markers["D"], PA_data.P2D/10)
    
        # futil.log(f'kwire_PA_P1 - {kwire_PA_P1.asArray()}\n kwire_PA_P2 {kwire_PA_P2.asArray()}') # debug

        kwire_PA_P1P2 = adsk.core.Line3D.create(kwire_PA_P1, kwire_PA_P2)
        kwire_PA_vector = kwire_PA_P1.vectorTo(kwire_PA_P2)#  vector representing the direction of kwire (normalized)
        kwire_PA_vector.normalize()
        kwire_PA_P2_estimated = intersect_point(skin_brb, kwire_PA_P1, kwire_PA_vector, 200, 12)
        kwire_PA_P3 = adsk.core.Point3D.create(*kwire_PA_P1.asArray())
        kwire_PA_vector_lenght = kwire_PA_vector.copy() # vector representing the full lenght of kwire
        kwire_PA_vector_lenght.scaleBy(kwirel)
        kwire_PA_P3.translateBy(kwire_PA_vector_lenght)

        # futil.log(f'kwire_PA_P2_estimated: {kwire_PA_P2_estimated.asArray()}')

        _ = createPoint_by_point3D(kwire_PA_occ, kwire_PA_comp, kwire_PA_P1, f"{PA_data.id} P1")
        _ = createPoint_by_point3D(kwire_PA_occ, kwire_PA_comp, kwire_PA_P2, f"{PA_data.id} P2")
        _ = createPoint_by_point3D(kwire_PA_occ, kwire_PA_comp, kwire_PA_P2_estimated, f"{PA_data.id} P2 estimated")
        _ = createPoint_by_point3D(kwire_PA_occ, kwire_PA_comp, kwire_PA_P3, f"{PA_data.id} P3")
        _ = createAxis_by_Line3D(kwire_PA_occ, kwire_PA_comp, kwire_PA_P1P2, f"{PA_data.id} axis")
        
        kwire_PA_brb = create_cylinder(
                        kwire_PA_occ, kwire_PA_comp,
                        PA_data.id,
                        kwire_PA_P1,
                        kwire_PA_P2,
                        kwirer,
                        kwirel)

        # ---------------- KWIRE PA VIRTUAL CALCULATIONS --------------- #

        # ++++ register errors of measurement
        PA_data.P1_mean = kwire_PA_P1_mean
        PA_data.P2_mean = kwire_PA_P2_mean
        
        # ++++ measure distance from anatomical structures
        for name, anatomy_brb in bodies.items():
            # NOTWORKING!!!
            # distance_target_anatomybody_result = _app.measureManager.measureMinimumDistance(kwire_target_brb, anatomy_brb)
            # distance_target_anatomybody = distance_target_anatomybody_result.value * 10
            # distance_target_anatomybody = round(distance_target_anatomybody, 3)
            # futil.log(f'distance target - {anatomy_brb.name}: {distance_target_anatomybody:.3f} mm') # debug
            # _ = createPoint_by_point3D(None, None, distance_target_anatomybody_result.positionOne, f"position one") # debug
            # _ = createPoint_by_point3D(None, None, distance_target_anatomybody_result.positionTwo, f"position two") # debug

            distance_PA_anatomybody_result = _app.measureManager.measureMinimumDistance(kwire_PA_brb, anatomy_brb)
            distance_PA_anatomybody = distance_PA_anatomybody_result.value * 10
            PA_data.anatomy[anatomy_brb.name] = round(distance_PA_anatomybody, 3)
            # futil.log(f'distance PA     - {anatomy_brb.name}: {PA_data.anatomy[anatomy_brb.name]:.3f} mm') # debug
            # _ = createPoint_by_point3D(None, None, distance_PA_anatomybody_result.positionOne, f"position one") # debug
            # _ = createPoint_by_point3D(None, None, distance_PA_anatomybody_result.positionTwo, f"position two") # debug
        
        # ++++ measure delta angle between PA axis and target axis
        K_radang = 57.2958 # to convert from radians to degrees
        
        PA_data.angle_PA_target = round(_app.measureManager.measureAngle(kwire_PA_P1P2, kwire_target_P1P2_estimated).value * K_radang, 3)
        # futil.log(f'angle value is {PA_data.angle_PA_target}') # debug

        # ++++ measure distance between P1, P2, P2e and 4 markers

        PA_data.P1A_F = round(kwire_PA_P1.distanceTo(markers["A"])*10, 3)
        PA_data.P1B_F = round(kwire_PA_P1.distanceTo(markers["B"])*10, 3)
        PA_data.P1C_F = round(kwire_PA_P1.distanceTo(markers["C"])*10, 3)
        PA_data.P1D_F = round(kwire_PA_P1.distanceTo(markers["D"])*10, 3)
        PA_data.P2A_F = round(kwire_PA_P2.distanceTo(markers["A"])*10, 3)
        PA_data.P2B_F = round(kwire_PA_P2.distanceTo(markers["B"])*10, 3)
        PA_data.P2C_F = round(kwire_PA_P2.distanceTo(markers["C"])*10, 3)
        PA_data.P2D_F = round(kwire_PA_P2.distanceTo(markers["D"])*10, 3)

        PA_data.P2eA = round(kwire_PA_P2_estimated.distanceTo(markers["A"])*10, 3)
        PA_data.P2eB = round(kwire_PA_P2_estimated.distanceTo(markers["B"])*10, 3)
        PA_data.P2eC = round(kwire_PA_P2_estimated.distanceTo(markers["C"])*10, 3)
        PA_data.P2eD = round(kwire_PA_P2_estimated.distanceTo(markers["D"])*10, 3)

        # ++++ measure delta distance between kwire and target insertion point
        PA_data.distance_P1_PA_target = round(kwire_target_P1.distanceTo(kwire_PA_P1)*10, 3)
        PA_data.distance_P1_PA_target_X = round((kwire_target_P1.x - kwire_PA_P1.x)*10, 3)
        PA_data.distance_P1_PA_target_Y = round((kwire_target_P1.y - kwire_PA_P1.y)*10, 3)
        PA_data.distance_P1_PA_target_Z = round((kwire_target_P1.z - kwire_PA_P1.z)*10, 3)

        PA_data.distance_P2_PA_target = round(kwire_target_P2.distanceTo(kwire_PA_P2)*10, 3)
        PA_data.distance_P2_PA_target_X = round((kwire_target_P2.x - kwire_PA_P2.x)*10, 3)
        PA_data.distance_P2_PA_target_Y = round((kwire_target_P2.y - kwire_PA_P2.y)*10, 3)
        PA_data.distance_P2_PA_target_Z = round((kwire_target_P2.z - kwire_PA_P2.z)*10, 3)

        PA_data.distance_P2e_PA_target = round(kwire_target_P2_estimated.distanceTo(kwire_PA_P2_estimated)*10, 3)
        PA_data.distance_P2e_PA_target_X = round((kwire_target_P2_estimated.x - kwire_PA_P2_estimated.x)*10, 3)
        PA_data.distance_P2e_PA_target_Y = round((kwire_target_P2_estimated.y - kwire_PA_P2_estimated.y)*10, 3)
        PA_data.distance_P2e_PA_target_Z = round((kwire_target_P2_estimated.z - kwire_PA_P2_estimated.z)*10, 3)
        
        # ++++ measure delta depth of insertion (depth difference between PA and target)
        kwire_target_insertion_depth_mm = kwirel - (kwire_target_P2_estimated.distanceTo(kwire_target_P1)*10)
        kwire_PA_insertion_depth_mm = kwirel - (kwire_PA_P1.distanceTo(kwire_PA_P2_estimated)*10)
        
        PA_data.delta_id_PA_target = round(kwire_PA_insertion_depth_mm - kwire_target_insertion_depth_mm, 3)
        # futil.log(f'delta insertion (+ means more out of the skin ): {PA_data.delta_id_PA_target} mm') # debug
        
        PA_data.fusion_computed = True
        PA_data_str = PA_data.dumps()
        futil.log(f'import this into companion (already copied in clipboard): \n{PA_data_str}')
        pyperclip.copy(PA_data_str)
        
    except:
        _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


######################## TOOLS ########################

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

def trilaterate3D_4spheres(
        A:  adsk.core.Point3D,
        PA: float,
        B:  adsk.core.Point3D,
        PB: float,
        C:  adsk.core.Point3D,
        PC: float,
        D:  adsk.core.Point3D,
        PD: float
        ) -> tuple[adsk.core.Point3D, float]:
    "returns the trilateration midpoint and error statistics of all the possible combinations of 3 starting from 4 spheres"
    
    points: list[adsk.core.Point3D] = []
    try:
        # we have 4 markers and 4 distances, trilaterate each combination of them to get 4x2=8 sphere intersection points.
        # (3 intersecting spheres have 2 points in common, except for edgecases)
        points.extend(trilaterate3D(A, PA, B, PB, C, PC))
        points.extend(trilaterate3D(A, PA, B, PB, D, PD))
        points.extend(trilaterate3D(A, PA, C, PC, D, PD))
        points.extend(trilaterate3D(B, PB, C, PC, D, PD))

        # _ = [futil.log(f'point: {p.asArray()}') for p in points]    # debug
        # +_ = [createPoint_by_point3D(None, None, p) for p in points] # debug

        # make all possible combination groups of 4 out of 8 intersection points
        # (the objective is to find the group (cluster) of which points are the closest to eachother)
        groups = list(combinations(points, 4))

        def calc_group_dist(
                group: tuple[adsk.core.Point3D, adsk.core.Point3D, adsk.core.Point3D, adsk.core.Point3D]
                ) -> float:
            return  group[0].distanceTo(group[1])*10 + \
                    group[0].distanceTo(group[2])*10 + \
                    group[0].distanceTo(group[3])*10 + \
                    group[1].distanceTo(group[2])*10 + \
                    group[1].distanceTo(group[3])*10 + \
                    group[2].distanceTo(group[3])*10

        # run through all combination groups to find the one with the most grouped points
        cluster = groups[0]
        for group in groups:
            if calc_group_dist(group) < calc_group_dist(cluster):
                cluster = group
                
        # _ = [createPoint_by_point3D(None, None, p) for p in cluster] # debug
        
        # compute the cluster center point
        cluster_center = adsk.core.Point3D.create(
            (cluster[0].x + cluster[1].x + cluster[2].x + cluster[3].x)/4,
            (cluster[0].y + cluster[1].y + cluster[2].y + cluster[3].y)/4,
            (cluster[0].z + cluster[1].z + cluster[2].z + cluster[3].z)/4
        )
        # _ = createPoint_by_point3D(None, None, cluster_center, "cluster_center") # debug

        # compute measurement error statistics
        cluster_center_dists = [cluster_center.distanceTo(cluster[0])*10, cluster_center.distanceTo(cluster[1])*10, cluster_center.distanceTo(cluster[2])*10, cluster_center.distanceTo(cluster[3])*10]
        mean = sum(cluster_center_dists) / len(cluster_center_dists)
        squared_diff = [(x - mean) ** 2 for x in cluster_center_dists]
        variance = sum(squared_diff) / (len(cluster_center_dists) - 1)
        std_deviation = math.sqrt(variance)
        std_error = std_deviation / math.sqrt(len(cluster_center_dists))

        mean = round(mean, 3)

        # debug
        futil.log(f"Mean: {mean} mm")

        return cluster_center, mean
        

    except Exception as e:
        _ui.messageBox(f"trilaterate3D_4spheres: {e.__traceback__.tb_lineno}\n\nerror: {e}")

    return None, None, None, None

def trilaterate3D(
        m1:  adsk.core.Point3D, # marker point
        m1P: float,             # marker point distance to trilateration point
        m2:  adsk.core.Point3D,
        m2P: float,
        m3:  adsk.core.Point3D,
        m3P: float
) -> list[adsk.core.Point3D]:
    "returns the 2 intersection points of the 3 spheres"
    
    # futil.log(f"before: {m1P, m2P, m3P}") # debug
    # futil.log(f"before: {m1P+m2P, m2P+m3P, m3P+m1P}") # debug

    # check if the spheres intersect, if they don't, increase the radius
    while m1P + m2P <= m1.distanceTo(m2) or m2P + m3P <= m2.distanceTo(m3) or m3P + m1P <= m3.distanceTo(m1):
        if m1P + m2P <= m1.distanceTo(m2):
            m1P += 0.01
            m2P += 0.01
        if m2P + m3P <= m2.distanceTo(m3):
            m2P += 0.01
            m3P += 0.01
        if m3P + m1P <= m3.distanceTo(m1):
            m3P += 0.01
            m1P += 0.01
    
    # futil.log(f"after:  {m1P, m2P, m3P}") # debug
    # futil.log(f"after:  {m1P+m2P, m2P+m3P, m3P+m1P}") # debug
    # futil.log(f"m1-m2..:{m1.distanceTo(m2), m2.distanceTo(m3), m3.distanceTo(m1)}") # debug
    # futil.log(f"-----------------------------------------") # debug

    # edge case in which each couple of the 3 spheres intersects, but the 3 spheres don't intersect in the same area
    # look at: 3 spheres intersection edge case.png
    ans1 = np.full(3, np.nan)
    ans2 = np.full(3, np.nan)
    while np.isnan(ans1).any() or np.isnan(ans2).any():
        try:
            m1np=np.array(m1.asArray())
            m2np=np.array(m2.asArray())
            m3np=np.array(m3.asArray())
            e_x=(m2np-m1np)/np.linalg.norm(m2np-m1np)
            i=np.dot(e_x,(m3np-m1np))
            e_y=(m3np-m1np-(i*e_x))/(np.linalg.norm(m3np-m1np-(i*e_x)))
            e_z=np.cross(e_x,e_y)
            d=np.linalg.norm(m2np-m1np)
            j=np.dot(e_y,(m3np-m1np))
            x=((m1P**2)-(m2P**2)+(d**2))/(2*d)
            y=(((m1P**2)-(m3P**2)+(i**2)+(j**2))/(2*j))-((i/j)*(x))
            z1=np.sqrt(m1P**2-x**2-y**2)
            z2=np.sqrt(m1P**2-x**2-y**2)*(-1)
            ans1=m1np+(x*e_x)+(y*e_y)+(z1*e_z)
            ans2=m1np+(x*e_x)+(y*e_y)+(z2*e_z)

            m1P += 0.01
            m2P += 0.01
            m3P += 0.01
        except Exception as e:
            _ui.messageBox(f"trilaterate3D: {e.__traceback__.tb_lineno}\n\nerror: {e}")

    return [adsk.core.Point3D.create(ans1[0], ans1[1], ans1[2]), adsk.core.Point3D.create(ans2[0], ans2[1], ans2[2])]

def create_cylinder(occ: adsk.fusion.Occurrence, comp: adsk.fusion.Component, id: str, P1: adsk.core.Point3D, P2: adsk.core.Point3D, r: float, lenght: float) -> adsk.fusion.BRepBody:
    # idea:
    # c = adsk.core.Cylinder.create(p1, kwire_PA_vector, kwirer)

    P1 = P1.copy()
    P2 = P2.copy()
    
    try:
        comp = _rootComp
        planes = comp.constructionPlanes
        planeInput = planes.createInput()

        planeInput.setByPlane(adsk.core.Plane.create(P1, P1.vectorTo(P2)))   
        plane1 = comp.constructionPlanes.add(planeInput)
        sketch1 = comp.sketches.add(plane1)

        # convert P1 coordinates to sketch coordinates
        P1sketch = sketch1.modelToSketchSpace(P1)
        
        circles = sketch1.sketchCurves.sketchCircles
        circle1 = circles.addByCenterRadius(P1sketch, r)
        profile0 = sketch1.profiles.item(0)

        extrudes = adsk.fusion.ExtrudeFeatures.cast(comp.features.extrudeFeatures)
        dist = adsk.core.ValueInput.createByReal(lenght)
        extInput = extrudes.createInput(profile0, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(dist), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        # extInput.isSolid = True
        ext = extrudes.add(extInput)

        cilinder = ext.bodies.item(0)
        cilinder.name = id

        plane1.deleteMe() # debug (comment out)
        sketch1.deleteMe() # debug (comment out)
        ext.dissolve() # debug (comment out)

        cilinder = cilinder.moveToComponent(occ)

        return cilinder
        
    except Exception as e:
        _ui.messageBox(f"create_cylinder: {e.__traceback__.tb_lineno}\n\nerror: {e}")
