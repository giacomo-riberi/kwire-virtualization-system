from dataclasses import dataclass
import json

@dataclass
class data_elaboration:
    def dumps(self) -> str:
            "dump data into json string"
            return json.dumps(self, default=lambda o: o.__dict__, sort_keys=False)

@dataclass
class PAdata(data_elaboration):
    "positioning attempt data"

    datatype: str
    PHASE_id: str
    ECP_id: str
    id: str
    comment: str; "used to mark data on database for later technical analysis"
    time_init: float
    phase: int
    ECP_number: int
    PA_number: int
    success: bool

    entered_articulation: int; "kwire entered articulation cavity (-1: not analyzed; 0: not entered; 1: entered)"

    PA_D: float
    PA_RPC: int;    "PA radiation picture count"

    values_from_unity: str
    P1A: float;     "P1 - marker: measured with caliper"
    P1B: float
    P1C: float
    P1D: float
    P2A: float
    P2B: float
    P2C: float
    P2D: float
    P1A_F: float;   "P1 - marker: measured in fusion"
    P1B_F: float
    P1C_F: float
    P1D_F: float
    P2A_F: float
    P2B_F: float
    P2C_F: float
    P2D_F: float

    P2eA: float;   "P2e - marker: measured in fusion"
    P2eB: float
    P2eC: float
    P2eD: float
    
    P1A_U: float;   "P1A - marker: measured in unity"
    P1B_U: float
    P1C_U: float
    P1D_U: float
    P2eA_U: float
    P2eB_U: float
    P2eC_U: float
    P2eD_U: float

    P1_mean_max: float
    P1_mean:  float
    P2_mean_max: float
    P2_mean:  float
    
    confidence_position: float
    confidence_angle: float
    estimate_hit: bool
    target: str; "k-wire target component name on fusion 360"
    markers: dict[str, str]
    fusion_computed: bool; "analyzed by fusion 360"
    anatomy: dict[str, float]
    angle_PA_target: float

    distance_P1_PA_target: float; "distance P1"
    distance_P1_PA_target_X: float
    distance_P1_PA_target_Y: float
    distance_P1_PA_target_Z: float

    distance_P2_PA_target: float; "distance P2"
    distance_P2_PA_target_X: float
    distance_P2_PA_target_Y: float
    distance_P2_PA_target_Z: float

    distance_P2e_PA_target: float; "distance P2 estimated"
    distance_P2e_PA_target_X: float
    distance_P2e_PA_target_Y: float
    distance_P2e_PA_target_Z: float
    
    delta_id_PA_target: float; "delta insertion depth"