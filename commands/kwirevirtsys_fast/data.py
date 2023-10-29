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
    time_init: float
    phase: str
    ECP_number: int
    PA_number: int
    success: bool
    PA_D: float
    PA_RPC: int;    "PA radiation picture count"
    PA_RESD: float; "PA radiation entrance surface dose"
    PA_RDAP: float; "PA radiation dose-area product"    # do we want to record that? !!!
    PA_RmAs: float; "PA radiation milliampere-seconds"  # do we want to record that? !!!
    PA_RkVp: float; "PA radiation kilovoltage peak"     # do we want to record that? !!!
    P1A: float
    P1B: float
    P1C: float
    P1D: float
    P2A: float
    P2B: float
    P2C: float
    P2D: float
    confidence_position: float
    confidence_angle: float
    estimate_hit: bool
    ktarget: str; "k-wire target component name on fusion 360"
    markers: dict[str, str]
    fusion_computed: bool; "analyzed by fusion 360"
    anatomy: dict[str, float]
    angle_kPA_ktarget: float
    distance_ep_kPA_ktarget: float; "distance skin entrance point"
    distance_ep_kPA_ktarget_X: float
    distance_ep_kPA_ktarget_Y: float
    distance_ep_kPA_ktarget_Z: float
    delta_id_kPA_ktarget: float; "delta insertion depth"