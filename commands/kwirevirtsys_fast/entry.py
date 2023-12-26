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
                        futil.log(f"\tfound anatomy struct {k} in {occ.name}")
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
        
    def get_kwire_target(PA_data: data.PAdata) -> tuple[adsk.fusion.Component, adsk.fusion.BRepBody, adsk.core.Point3D, adsk.core.Vector3D] | None:
        "returns normalized vector"
        
        for occ in _rootComp.allOccurrences:
            if occ.name == PA_data.ktarget:
                kwire = occ.component

                p1 = kwire.constructionPoints.itemByName("p1").geometry
                p1.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis

                _, _, vector = kwire.xConstructionAxis.geometry.getData()
                vector.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis
                vector.normalize()
                
                return kwire, kwire.bRepBodies.itemByName("filo"), p1, vector
        return None

    def intersect_point(brb: adsk.fusion.BRepBody, P: adsk.core.Point3D, dir: adsk.core.Vector3D, maxtests: int, precision: int, precisionStart: int = None) -> adsk.core.Point3D | None:
        "estimate point of intersection of a vector starting from P through a body; dir should be normalized"

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
        kwire_target_comp, kwire_target_brb, kwire_target_P1, kwire_target_vector = get_kwire_target(PA_data)
        kwire_target_P2_estimated = intersect_point(skin_brb, kwire_target_P1, kwire_target_vector, 200, 8)
        kwire_target_P1P2 = adsk.core.Line3D.create(kwire_target_P1, kwire_target_comp.originConstructionPoint.geometry)


        # -------------------------- KWIRE PA -------------------------- #

        kwire_PA_P1, kwire_PA_P1_mean, kwire_PA_P1_SD, kwire_PA_P1_SE = trilaterate3D_4spheres(
                        markers["A"], PA_data.P1A/10,
                        markers["B"], PA_data.P1B/10,
                        markers["C"], PA_data.P1C/10,
                        markers["D"], PA_data.P1D/10)
        
        # kwire_PA_cpe (construction point (skin) entrance)
        kwire_PA_P2, kwire_PA_P2_mean, kwire_PA_P2_SD, kwire_PA_P2_SE = trilaterate3D_4spheres(
                        markers["A"], PA_data.P2A/10,
                        markers["B"], PA_data.P2B/10,
                        markers["C"], PA_data.P2C/10,
                        markers["D"], PA_data.P2D/10)

        kwire_PA_P1P2 = adsk.core.Line3D.create(kwire_PA_P1, kwire_PA_P2)
        kwire_PA_vector = adsk.core.Vector3D.create(kwire_PA_P2.x-kwire_PA_P1.x, kwire_PA_P2.y-kwire_PA_P1.y, kwire_PA_P2.z-kwire_PA_P1.z)
        kwire_PA_vector.normalize()
        kwire_PA_P2_estimated = intersect_point(skin_brb, kwire_PA_P1P2.startPoint, kwire_PA_vector, 200, 8)
        _ = createPoint_by_point3D(kwire_PA_P2_estimated, f"{PA_data.id} P2 estimated")

        kwire_PA_brb = create_cylinder(
                        PA_data.id,
                        kwire_PA_P1,
                        kwire_PA_P2,
                        kwirer,
                        kwirel)

        _ = createPoint_by_point3D(kwire_PA_P1, f"{PA_data.id} P1")
        _ = createPoint_by_point3D(kwire_PA_P2, f"{PA_data.id} P2")
        

        # ---------------- KWIRE PA VIRTUAL CALCULATIONS --------------- #

        # ++++ register errors of measurement
        PA_data.P1_mean = kwire_PA_P1_mean
        PA_data.P1_SD   = kwire_PA_P1_SD
        PA_data.P1_SE   = kwire_PA_P1_SE
        PA_data.P2_mean = kwire_PA_P2_mean
        PA_data.P2_SD   = kwire_PA_P2_SD
        PA_data.P2_SE   = kwire_PA_P2_SE
        
        # ++++ measure distance from anatomical structures
        tmpMgr: adsk.fusion.TemporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        for name, anatomy_brb in bodies.items():
            distance_PA_anatomybody = _app.measureManager.measureMinimumDistance(tmpMgr.copy(kwire_PA_brb), tmpMgr.copy(anatomy_brb)).value*10            
            PA_data.anatomy[anatomy_brb.name] = round(distance_PA_anatomybody, 3)
            futil.log(f'dist value {anatomy_brb.name}: {PA_data.anatomy[anatomy_brb.name]:.3f} mm')

            distance_target_anatomybody = _app.measureManager.measureMinimumDistance(tmpMgr.copy(kwire_target_brb), tmpMgr.copy(anatomy_brb)).value*10 # NOTWORKING
            futil.log(f'dist value {anatomy_brb.name}: {distance_target_anatomybody:.3f} mm') #!!!

        # ++++ measure delta angle between kwire and target axis
        K_radang = 57.296 # to convert from radians to degrees
        
        PA_data.angle_kPA_ktarget = _app.measureManager.measureAngle(kwire_PA_P1P2, kwire_target_P1P2).value * K_radang

        futil.log(f'angle value is {PA_data.angle_kPA_ktarget}')

        # ++++ measure delta distance between kwire and target insertion point        
        PA_data.distance_ep_kPA_ktarget = kwire_target_P2_estimated.distanceTo(kwire_PA_P2_estimated)*10
        futil.log(f'distance PA entrance point to target entrance point: {PA_data.distance_ep_kPA_ktarget} mm')
        
        PA_data.distance_ep_kPA_ktarget_X = (kwire_target_P2_estimated.x - kwire_PA_P2_estimated.x)*10
        futil.log(f'distance PA entrance to target entrance X: {PA_data.distance_ep_kPA_ktarget_X} mm')

        PA_data.distance_ep_kPA_ktarget_Y = (kwire_target_P2_estimated.y - kwire_PA_P2_estimated.y)*10
        futil.log(f'distance PA entrance to target entrance Y: {PA_data.distance_ep_kPA_ktarget_Y} mm')
        
        PA_data.distance_ep_kPA_ktarget_Z = (kwire_target_P2_estimated.z - kwire_PA_P2_estimated.z)*10
        futil.log(f'distance PA entrance to target entrance Z: {PA_data.distance_ep_kPA_ktarget_Z} mm')
        
        # ++++ measure delta depth of insertion (depth difference between PA and target)
        kwire_target_insertion_depth_mm = kwirel - (kwire_target_P2_estimated.distanceTo(kwire_target_P1)*10)
        kwire_PA_insertion_depth_mm = kwirel - (kwire_PA_P1.distanceTo(kwire_PA_P2_estimated)*10)
        
        PA_data.delta_id_kPA_ktarget = kwire_PA_insertion_depth_mm - kwire_target_insertion_depth_mm
        futil.log(f'delta insertion (+ means more out of the skin ): {PA_data.delta_id_kPA_ktarget} mm')
        
        PA_data.fusion_computed = True
        PA_data_str = PA_data.dumps()
        futil.log(f'import this into companion (already copied in clipboard): \n{PA_data_str}')
        pyperclip.copy(PA_data_str)
        
    except:
        _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


######################## TOOLS ########################

def createAxis_by_Line3D(l: adsk.core.Line3D) -> adsk.fusion.ConstructionAxis:
        "create visible construction axis from a line 3D"
        if _design.designType == adsk.fusion.DesignTypes.DirectDesignType:
            axes = _rootComp.constructionAxes
            axisInput = axes.createInput()
            axisInput.setByLine(l.asInfiniteLine())
            return axes.add(axisInput)
    
def createPoint_by_point3D(p: adsk.core.Point3D, name="") -> adsk.fusion.ConstructionPoint:
    "create visible construction point from a point 3D"
    points = _rootComp.constructionPoints
    pointsInput = points.createInput()
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
        ) -> tuple[adsk.core.Point3D, float, float, float]:
    "returns the trilateration midpoint and error statistics of all the possible combinations of 3 starting from 4 spheres"
    
    points: list[adsk.core.Point3D] = []
    try:
        # we have 4 markers and 4 distances, trilaterate each combination of them to get 4x2=8 sphere intersection points.
        # (3 intersecting spheres have 2 points in common, except for edgecases)
        points.extend(trilaterate3D(A, PA, B, PB, C, PC))
        points.extend(trilaterate3D(A, PA, B, PB, D, PD))
        points.extend(trilaterate3D(A, PA, C, PC, D, PD))
        points.extend(trilaterate3D(B, PB, C, PC, D, PD))

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
                
        # _ = [createPoint_by_point3D(point) for point in cluster] # debug
        
        # compute the cluster center point
        cluster_center = adsk.core.Point3D.create(
            (cluster[0].x + cluster[1].x + cluster[2].x + cluster[3].x)/4,
            (cluster[0].y + cluster[1].y + cluster[2].y + cluster[3].y)/4,
            (cluster[0].z + cluster[1].z + cluster[2].z + cluster[3].z)/4
        )
        # _ = createPoint_by_point3D(cluster_center, "cluster_center") # debug

        # compute measurement error statistics
        cluster_center_dists = [cluster_center.distanceTo(cluster[0])*10, cluster_center.distanceTo(cluster[1])*10, cluster_center.distanceTo(cluster[2])*10, cluster_center.distanceTo(cluster[3])*10]
        mean = sum(cluster_center_dists) / len(cluster_center_dists)
        squared_diff = [(x - mean) ** 2 for x in cluster_center_dists]
        variance = sum(squared_diff) / (len(cluster_center_dists) - 1)
        std_deviation = math.sqrt(variance)
        std_error = std_deviation / math.sqrt(len(cluster_center_dists))

        # debug
        futil.log(f"Mean: {mean} mm")
        futil.log(f"Standard Deviation: {std_deviation} mm")
        futil.log(f"Standard Error: {std_error} mm")

        return cluster_center, round(mean, 3), round(std_deviation, 3), round(std_error, 3)
        

    except Exception as e:
        _ui.messageBox(f"trilaterate3D_err: {e.__traceback__.tb_lineno}\n\nerror: {e}")

    return 

def trilaterate3D(
        m1:  adsk.core.Point3D, # marker point
        m1P: float,             # marker point distance to trilateration point
        m2:  adsk.core.Point3D,
        m2P: float,
        m3:  adsk.core.Point3D,
        m3P: float
) -> list[adsk.core.Point3D]:
    "returns the 2 intersection points of the 3 spheres"

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
    except Exception as e:
        _ui.messageBox(f"trilaterate3D: {e.__traceback__.tb_lineno}\n\nerror: {e}")

    return [adsk.core.Point3D.create(ans1[0], ans1[1], ans1[2]), adsk.core.Point3D.create(ans2[0], ans2[1], ans2[2])]

def create_cylinder(id: str, p1: adsk.core.Point3D, p2: adsk.core.Point3D, r: float, lenght: float) -> adsk.fusion.BRepBody:
    try:
        planes = _rootComp.constructionPlanes
        planeInput = adsk.fusion.ConstructionPlaneInput.cast(planes.createInput())
        planeInput.setByPlane(adsk.core.Plane.create(p1, p1.vectorTo(p2)))   
        plane1 = _rootComp.constructionPlanes.add(planeInput)
        sketch1 = _rootComp.sketches.add(plane1)
        
        circles = sketch1.sketchCurves.sketchCircles
        circle1 = circles.addByCenterRadius(adsk.core.Point3D.create(0, 0, 0), r)
        profile0 = sketch1.profiles.item(0)

        extrudes = adsk.fusion.ExtrudeFeatures.cast(_rootComp.features.extrudeFeatures)
        dist = adsk.core.ValueInput.createByReal(lenght)
        extInput = extrudes.createInput(profile0, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
        extInput.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(dist), adsk.fusion.ExtentDirections.PositiveExtentDirection)
        # extInput.isSolid = True
        ext = extrudes.add(extInput)

        cilinder = ext.bodies.item(0)
        cilinder.name = id

        plane1.deleteMe()
        sketch1.deleteMe()
        ext.dissolve()

        return cilinder
        
    except Exception as e:
        _ui.messageBox(f"create_cylinder: {e.__traceback__.tb_lineno}\n\nerror: {e}")
