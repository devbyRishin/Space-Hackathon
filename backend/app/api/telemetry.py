from fastapi import APIRouter
from ..models.schemas import TelemetryRequest, TelemetryResponse
from ..core.state import sim_state
from ..core.scheduler import run_conjunction_assessment
from loguru import logger

router = APIRouter()

@router.post("/api/telemetry", response_model=TelemetryResponse)
async def ingest_telemetry(req: TelemetryRequest):
    for obj in req.objects:
        r = [obj.r.x, obj.r.y, obj.r.z]
        v = [obj.v.x, obj.v.y, obj.v.z]
        if obj.type == 'DEBRIS':
            sim_state.add_debris(obj.id, r, v)
        else:
            sim_state.add_satellite(obj.id, r, v)

    logger.info(f"Telemetry ingested: {len(req.objects)} objects")
    warnings = run_conjunction_assessment()
    critical = sum(1 for w in warnings if w['critical'])

    return TelemetryResponse(
        status="ACK",
        processed_count=len(req.objects),
        active_cdm_warnings=critical
    )