from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

from backend.delivery_queue import DeliveryQueue

app = FastAPI()

dq = DeliveryQueue()

# CORS middleware (fixed and closed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # or ["http://localhost:5500"] etc. if you want to restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequestModel(BaseModel):
    id: str
    supply_type: str
    quantity: int
    timestamp: str
    expiry_date: str | None = None
    distance_km: float | None = None
    destination: str | None = None

@app.post("/api/requests")
def enqueue_request(req: RequestModel):
    r = req.model_dump()

    # basic datetime validation
    try:
        datetime.fromisoformat(r["timestamp"])
        if r.get("expiry_date"):
            datetime.fromisoformat(r["expiry_date"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad datetime format: {e}")

    priority = dq.add_request(r)
    return {"status": "enqueued", "computed_priority": priority}

@app.get("/api/queue")
def get_queue():
    return {"size": len(dq), "items": dq.list_all()}

@app.post("/api/dispatch")
def dispatch_next():
    item = dq.pop()
    if item is None:
        raise HTTPException(status_code=404, detail="Queue empty")
    return {"dispatched": item}
