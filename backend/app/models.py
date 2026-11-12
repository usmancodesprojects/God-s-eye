from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(allow_inf_nan=False)]
NonNegative = Annotated[Finite, Field(ge=0)]
Coordinate = tuple[Finite, Finite]
BBox = tuple[Finite, Finite, Finite, Finite]
Instance = Literal['sector_8', 'sector_12', 'sector_16']


def check_bbox(bbox):
    w, s, e, n = bbox
    if not (-180 <= w < e <= 180 and -85 <= s < n <= 85):
        raise ValueError('bbox must be [west, south, east, north] with increasing bounds (latitude ±85°)')
    return bbox


class Extensible(BaseModel):
    # Preserve Huzaifa's additional metrics, MILP, lens details and future fields.
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)


class Sector(Extensible):
    name: str
    center: Coordinate
    bbox: BBox

    @model_validator(mode='after')
    def geography(self):
        check_bbox(self.bbox)
        lon, lat = self.center
        if not (-180 <= lon <= 180 and -85 <= lat <= 85):
            raise ValueError('invalid sector center')
        return self


class Zone(Extensible):
    id: int
    lon: Annotated[Finite, Field(ge=-180, le=180)]
    lat: Annotated[Finite, Field(ge=-85, le=85)]
    weight: NonNegative = 1
    priority: bool = False
    covered_by: list[int]


class Candidate(Extensible):
    id: int
    mount_id: int
    lon: Annotated[Finite, Field(ge=-180, le=180)]
    lat: Annotated[Finite, Field(ge=-85, le=85)]
    height_m: NonNegative
    azimuth_deg: Annotated[Finite, Field(ge=0, lt=360)]
    tilt_deg: Annotated[Finite, Field(ge=-90, le=90)]
    fov_deg: Annotated[Finite, Field(gt=0, le=360)]
    range_m: Annotated[Finite, Field(gt=0)]
    cost: NonNegative
    power_w: NonNegative
    fov_polygon: Annotated[list[Coordinate], Field(min_length=3)]

    @model_validator(mode='after')
    def polygon_coordinates(self):
        if any(not (-180 <= lon <= 180 and -85 <= lat <= 85) for lon, lat in self.fov_polygon):
            raise ValueError('invalid FOV coordinates')
        return self


class Solution(Extensible):
    selected: list[int]
    num_cameras: Annotated[int, Field(ge=0)]
    coverage_pct: Annotated[Finite, Field(ge=0, le=100)]
    cost: NonNegative
    power_w: NonNegative
    runtime_s: NonNegative
    approx_ratio: NonNegative | None = None


class Bitstring(Extensible):
    bits: Annotated[str, Field(pattern=r'^[01]+$')]
    prob: Annotated[Finite, Field(ge=0, le=1)]
    energy: Finite
    feasible: bool


class Quantum(Extensible):
    num_qubits: Annotated[int, Field(gt=0)]
    p: Annotated[int, Field(gt=0)]
    depth: Annotated[int, Field(ge=0)]
    two_qubit_gates: Annotated[int, Field(ge=0)]
    top_bitstrings: list[Bitstring]
    convergence: list[Finite]
    p_optimal: Annotated[Finite, Field(ge=0, le=1)]
    p_optimal_random: Annotated[Finite, Field(ge=0, le=1)]


class OptimizationResult(Extensible):
    sector: Sector
    zones: list[Zone]
    candidates: list[Candidate]
    solutions: dict[str, Solution]
    quantum: Quantum

    @model_validator(mode='after')
    def references(self):
        candidate_ids = {c.id for c in self.candidates}
        if len(candidate_ids) != len(self.candidates) or len({z.id for z in self.zones}) != len(self.zones):
            raise ValueError('candidate and zone IDs must be unique')
        for zone in self.zones:
            if not set(zone.covered_by) <= candidate_ids:
                raise ValueError(f'zone {zone.id} references unknown cameras')
        for method in ('qaoa', 'exact', 'greedy'):
            if method not in self.solutions:
                raise ValueError(f'missing {method} solution')
        for method, solution in self.solutions.items():
            selected = set(solution.selected)
            if not selected <= candidate_ids or len(selected) != len(solution.selected):
                raise ValueError(f'{method}: unknown or duplicate selected camera IDs')
            if len(selected) != solution.num_cameras:
                raise ValueError(f'{method}: num_cameras does not match selected')
        return self


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True, allow_inf_nan=False)
    instance: Instance = 'sector_12'
    p: Annotated[int, Field(ge=1, le=20)] = 2
    lambda_: Annotated[Finite, Field(gt=0, le=1000000)] = Field(default=2.0, alias='lambda')
    bbox: BBox | None = None

    @model_validator(mode='after')
    def geography(self):
        if self.bbox is not None:
            check_bbox(self.bbox)
        return self
