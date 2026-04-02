from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Vector3(BaseModel):
    x: float
    y: float
    z: float

class SpaceObject(BaseModel):
    id: str
    type: str
    r: Vector3
    v: Vector3

class TelemetryRequest(BaseModel):
    timestamp: str
    objects: List[SpaceObject]

class TelemetryResponse(BaseModel):
    status: str
    processed_count: int
    active_cdm_warnings: int

class BurnCommand(BaseModel):
    burn_id: str
    burnTime: str
    deltaV_vector: Vector3

class ManeuverRequest(BaseModel):
    satelliteId: str
    maneuver_sequence: List[BurnCommand]

class ManeuverValidation(BaseModel):
    ground_station_los: bool
    sufficient_fuel: bool
    projected_mass_remaining_kg: float

class ManeuverResponse(BaseModel):
    status: str
    validation: ManeuverValidation

class SimStepRequest(BaseModel):
    step_seconds: float

class SimStepResponse(BaseModel):
    status: str
    new_timestamp: str
    collisions_detected: int
    maneuvers_executed: int

class SatSnapshot(BaseModel):
    id: str
    lat: float
    lon: float
    fuel_kg: float
    status: str

class SnapshotResponse(BaseModel):
    timestamp: str
    satellites: List[SatSnapshot]
    debris_cloud: List[List]