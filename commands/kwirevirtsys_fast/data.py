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
    TEST_id: int
    ECP_id: int
    id: int
    comment: str; "used to mark data on database for later technical analysis"
    time_init: float
    phase: int
    ECP_number: int
    PA_number: int
    success: bool
    PA_D: float
    PA_RPC: int;    "PA radiation picture count"
    P1A: float
    P1B: float
    P1C: float
    P1D: float
    P2A: float
    P2B: float
    P2C: float
    P2D: float
    P1A_V: float
    P1B_V: float
    P1C_V: float
    P1D_V: float
    P2A_V: float
    P2B_V: float
    P2C_V: float
    P2D_V: float
    max_mean: float
    max_SD:   float
    max_SE:   float
    P1_mean:  float
    P1_SD:    float
    P1_SE:    float
    P2_mean:  float
    P2_SD:    float
    P2_SE:    float
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