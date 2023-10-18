import adsk.core, adsk.fusion
import os, string
import traceback
from ...lib import fusion360utils as futil
from ... import config
import json

import numpy as np

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

    _ = inputs.addStringValueInput('fusion360_PAimport_datastr', 'PA import json')

    _ = inputs.addValueInput('kwirer', 'kwire radius', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(kwirer))
    _ = inputs.addValueInput('kwirel', 'kwire lenght', _design.unitsManager.defaultLengthUnits, adsk.core.ValueInput.createByReal(11.0))

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.executePreview, command_preview, local_handlers=local_handlers)
    futil.add_handler(args.command.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.activate, command_activate, local_handlers=local_handlers)

def command_activate(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME}: Command Activate Event')
        

# This event handler is called when the user clicks the OK button in the command dialog or 
# is immediately called after the created event not command inputs were created for the dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    # General logging for debug.
    futil.log(f'{CMD_NAME}: Command Execute Event')

    def get_markers(fusion360_PAimport_data) -> dict[str, adsk.core.Point3D] | None:
        found = {}

        for marker_letter, marker_name in fusion360_PAimport_data["markers"].items():
            # marker_letter = "A"
            # name          = "M:3"
            occ = _rootComp.allOccurrences.itemByName(marker_name)
            if occ == None:
                futil.log(f"getMarkers: {marker_name} not found")
                return None

            cp = occ.component.constructionPoints.itemByName("centerpoint").geometry            
            cp.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis
            found[marker_letter] = cp
        
        return found

    def get_anatomy_structs(fusion360_PAimport_data) -> dict[str, adsk.fusion.BRepBody] | None:
        found = {}
        found_count = 0
        found_expected_count = len(fusion360_PAimport_data["anatomy_structs"])

        for anatomy_struct in fusion360_PAimport_data["anatomy_structs"]:
            for occ in _rootComp.allOccurrences:
                for brb in occ.bRepBodies:
                    if brb.name == anatomy_struct:
                        futil.log(f"\tfound!: {anatomy_struct}")
                        found[anatomy_struct] = brb
                        found_count += 1
        
        return found
        # if found_count == found_expected_count: # !!! add again
        #     return found
        # else:
        #     return None
    
    def get_skin() -> adsk.fusion.BRepBody | None:
        for occ in _rootComp.allOccurrences:
            for brb in occ.bRepBodies:
                if brb.name == "skin":
                    return brb
        
        
    def get_kwire_target(fusion360_PAimport_data) -> tuple[adsk.fusion.BRepBody, adsk.core.Point3D, adsk.core.Point3D] | None:
        for occ in _rootComp.allOccurrences:
            if occ.name == fusion360_PAimport_data["kwire_target"]:
                kwire = occ.component
                for ca in kwire.constructionAxes:
                    if ca.name == "k-wire axis":
                        cpo = kwire.constructionPoints.itemByName("outer end point").geometry
                        cpe = kwire.constructionPoints.itemByName("skin entrance point").geometry
                        cpo.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis
                        cpe.transformBy(occ.transform2) # must be transformed from the occurrence coordinate axis
                        return kwire.bRepBodies.itemByName("filo"), cpo, cpe
        return None
    
    def createAxis_by_Line3D(l: adsk.core.Line3D) -> bool:
        "create visible construction axis from a line 3D"
        if _design.designType == adsk.fusion.DesignTypes.DirectDesignType:
            axes = _rootComp.constructionAxes
            axisInput = axes.createInput()
            axisInput.setByLine(l.asInfiniteLine())
            return axes.add(axisInput)
    
    def delta_angle(a: adsk.core.Line3D, b: adsk.core.Line3D, axis: adsk.core.Line3D) -> float:
        "calculates delta angle of a from b on the specified axis"
        aax = _app.measureManager.measureAngle(a, axis).value * K_radang
        if aax > 90:
            aax = 180-aax
        bax = _app.measureManager.measureAngle(b, axis).value * K_radang
        if bax > 90:
            bax = 180-bax
        return aax - bax
            
    try:
        inputs = args.command.commandInputs
        fusion360_PAimport_data = json.loads(adsk.core.StringValueCommandInput.cast(inputs.itemById('fusion360_PAimport_datastr')).value)
        PA                = fusion360_PAimport_data["PA"]
        markers           = get_markers(fusion360_PAimport_data)
        bodies            = get_anatomy_structs(fusion360_PAimport_data)
        skin_brb          = get_skin()
        kwire_target_brb, kwire_target_cpo, kwire_target_cpe = get_kwire_target(fusion360_PAimport_data)
        kwire_target_line3D = adsk.core.Line3D.create(kwire_target_cpo, kwire_target_cpe)
        kwire_target_vector3D = adsk.core.Vector3D.create(kwire_target_cpe.x-kwire_target_cpo.x, kwire_target_cpe.y-kwire_target_cpo.y, kwire_target_cpe.z-kwire_target_cpo.z)

        # kwire_PA_cpo (construction point outer (end))
        P1 = trilaterate3D([list(markers["A"].asArray()) + [PA["P1A"]/10],
                            list(markers["B"].asArray()) + [PA["P1B"]/10],
                            list(markers["C"].asArray()) + [PA["P1C"]/10],
                            list(markers["D"].asArray()) + [PA["P1D"]/10]])
        # kwire_PA_cpe (construction point (skin) entrance)
        P2 = trilaterate3D([list(markers["A"].asArray()) + [PA["P2A"]/10], # add to all 4 `+(kwirer/2)` to compensate for not measuring from kwire center axis (or -(kwirer/2) depending on measuring method)
                            list(markers["B"].asArray()) + [PA["P2B"]/10],
                            list(markers["C"].asArray()) + [PA["P2C"]/10],
                            list(markers["D"].asArray()) + [PA["P2D"]/10]])

        kwire_PA_line3D = adsk.core.Line3D.create(P1, P2)
        kwire_PA_vector3D = adsk.core.Vector3D.create(P2.x-P1.x, P2.y-P1.y, P2.z-P1.z)

        kwire_PA_brb = create_cylinder(
                        fusion360_PAimport_data["PA"]["id"],
                        P1,
                        P2,
                        adsk.core.ValueCommandInput.cast(inputs.itemById('kwirer')).value,
                        adsk.core.ValueCommandInput.cast(inputs.itemById('kwirel')).value)
        
        # TODO
        # record somewhere all the stats (following lines) of target kwires

        # ++++ measure distance from anatomical structures
        tmpMgr: adsk.fusion.TemporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        for name, anatomy_brb in bodies.items():
            futil.log(f'{kwire_target_brb.getPhysicalProperties().centerOfMass.asArray()}')
            a = _app.measureManager.measureMinimumDistance(tmpMgr.copy(kwire_PA_brb), tmpMgr.copy(anatomy_brb)).value*10
            b = _app.measureManager.measureMinimumDistance(tmpMgr.copy(kwire_target_brb), tmpMgr.copy(anatomy_brb)).value*10 # NOTWORKING
            futil.log(f'dist value {anatomy_brb.name}: {a:.3f} mm -> target is: {b:.3f} mm')

        # ++++ measure delta angle between kwire and target axis
        K_radang = 57.296 # to convert from radians to degrees
        futil.log(f'angle value is {_app.measureManager.measureAngle(kwire_PA_line3D, kwire_target_line3D).value * K_radang}') 

        # measure delta angle between kwire and target on x/y/z axis
        X_axis = adsk.core.Line3D.create(adsk.core.Point3D.create(0,0,0), adsk.core.Point3D.create(1,0,0))
        Y_axis = adsk.core.Line3D.create(adsk.core.Point3D.create(0,0,0), adsk.core.Point3D.create(0,1,0))
        Z_axis = adsk.core.Line3D.create(adsk.core.Point3D.create(0,0,0), adsk.core.Point3D.create(0,0,1))
        # futil.log(f'delta angle X: {delta_angle(kwire_PA_line3D, kwire_target_line3D, X_axis)}') # ??? non so se lo si puo accettare (non sono euler angles)
        # futil.log(f'delta angle Y: {delta_angle(kwire_PA_line3D, kwire_target_line3D, Y_axis)}')
        # futil.log(f'delta angle Z: {delta_angle(kwire_PA_line3D, kwire_target_line3D, Z_axis)}')


        def normalizza(vettore):
            # Normalizza il vettore per avere lunghezza 1
            return vettore / np.linalg.norm(vettore)

        def calcola_asse_e_angolo(vettore1, vettore2):
            # Calcola l'asse e l'angolo tra due vettori
            vettore1 = normalizza(vettore1)
            vettore2 = normalizza(vettore2)
            prodotto_croce = np.cross(vettore1, vettore2)
            angolo = np.arccos(np.dot(vettore1, vettore2))
            return prodotto_croce, angolo

        def calcola_matrice_rotazione(asse, angolo):
            # Calcola la matrice di rotazione data un asse e un angolo
            c = np.cos(angolo)
            s = np.sin(angolo)
            t = 1 - c

            x, y, z = asse
            matrice = np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                                [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                                [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])
            return matrice

        def ruota_vettore(vettore, matrice_rotazione):
            # Ruota un vettore usando una matrice di rotazione
            return np.dot(matrice_rotazione, vettore)

        def allinea_vettori(vettore1, vettore2):
            # Calcola tre rotazioni successive per allineare due vettori
            asse1, angolo1 = calcola_asse_e_angolo(vettore1, vettore2)
            matrice_rotazione1 = calcola_matrice_rotazione(asse1, angolo1)
            vettore2_rot1 = ruota_vettore(vettore2, matrice_rotazione1)

            asse2, angolo2 = calcola_asse_e_angolo(vettore1, vettore2_rot1)
            matrice_rotazione2 = calcola_matrice_rotazione(asse2, angolo2)
            vettore2_rot2 = ruota_vettore(vettore2_rot1, matrice_rotazione2)

            asse3, angolo3 = calcola_asse_e_angolo(vettore1, vettore2_rot2)
            matrice_rotazione3 = calcola_matrice_rotazione(asse3, angolo3)
            vettore2_allineato = ruota_vettore(vettore2_rot2, matrice_rotazione3)

            rotazioni = [angolo1, angolo2, angolo3]

            return vettore2_allineato, rotazioni

        # Esempio d'uso
        futil.log(f"Vettore 1 xyz: {kwire_PA_vector3D.asArray()}")
        futil.log(f"Vettore 2 xyz: {kwire_target_vector3D.asArray()}")
        vettore1 = np.array(kwire_PA_vector3D.asArray())
        vettore2 = np.array(kwire_target_vector3D.asArray())

        vettore2_allineato, rotazioni = allinea_vettori(vettore1, vettore2)
        futil.log(f"Vettore 1: {vettore1}")
        futil.log(f"Vettore 2 allineato: {vettore2_allineato}")
        futil.log(f"Rotazioni sui tre assi: {[x*K_radang for x in rotazioni]}")

        # measure delta distance between kwire and target insertion point
        # measure delta distance between kwire and target insertion point on x/y/z axis ???
        # measure delta depth of insertion (depth difference between PA and target)
         
        # https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-393a1edc-08ec-466c-9813-6e3838e020f4
        # consider using the distance to P2 instead of entrance point
        # _ui.messageBox(f"containment: {kwire.pointContainment(adsk.core.Point3D.create(21.648, 109.671, -7.7738))}")
        # _ui.messageBox(f"containment: {kwire.pointContainment(adsk.core.Point3D.create(21.7569, 109.3081, -12.2972))}")
        

        
    except:
        _ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))


# funziona al 99%
def trilaterate3D(distances) -> adsk.core.Point3D:
    try:
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
    except Exception as e:
        _ui.messageBox(f"trilaterate3D: {e.__traceback__.tb_lineno}\n\nerror: {e}")

    if np.abs(r4-dist1) < np.abs(r4-dist2):
        return adsk.core.Point3D.create(ans1[0], ans1[1], ans1[2])
    else:
        return adsk.core.Point3D.create(ans2[0], ans2[1], ans2[2])


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
