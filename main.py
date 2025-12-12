from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, func
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import uvicorn

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./metrics.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class MetricDB(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String, index=True)
    metric_type = Column(String, index=True)
    value = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

Base.metadata.create_all(bind=engine)

# Pydantic Schemas
class MetricCreate(BaseModel):
    sensor_id: str = Field(..., description="ID of the sensor")
    metric_type: str = Field(..., description="Type of metric (e.g. temperature, humidity)")
    value: float = Field(..., description="Value of the metric")
    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        description="Timestamp of the reading"
    )

class MetricResponse(MetricCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class QueryResult(BaseModel):
    metric_type: str
    statistic: str
    value: float

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# App
app = FastAPI(title="Sensor Metrics Service")

@app.post("/metrics", response_model=MetricResponse, status_code=201)
def create_metric(metric: MetricCreate, db: Session = Depends(get_db)):
    """
    Insert a new metric reading.
    """
    # Ensure timestamp is set
    ts = metric.timestamp or datetime.now(timezone.utc)
    
    db_metric = MetricDB(
        sensor_id=metric.sensor_id,
        metric_type=metric.metric_type,
        value=metric.value,
        timestamp=ts
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

@app.get("/metrics/query")
def query_metrics(
    sensor_ids: Optional[List[str]] = Query(None, description="List of sensor IDs to include"),
    metrics: Optional[List[str]] = Query(None, description="List of metric types to include"),
    statistic: str = Query(..., pattern="^(min|max|sum|average)$", description="Statistic to calculate: min, max, sum, average"),
    start_date: Optional[datetime] = Query(None, description="Start date for range"),
    end_date: Optional[datetime] = Query(None, description="End date for range"),
    db: Session = Depends(get_db)
):
    """
    Query sensor data with filters and statistics.
    If no date range is provided, queries the last 24 hours (implied 'latest data').
    If only one date is provided, usage is ambiguous so explicit range is preferred, 
    but logic will handle open-ended ranges if needed or default to 'latest'.
    """
    
    # Default Date Range Logic
    now = datetime.now(timezone.utc)
    
    if not start_date and not end_date:
        end_date = now
        start_date = end_date - timedelta(days=1)
    elif start_date and not end_date:
        end_date = now
    elif end_date and not start_date:
        start_date = end_date - timedelta(days=1)

    # Ensure timezone awareness
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    # Validation
    if start_date > end_date:
        raise HTTPException(
            status_code=400, 
            detail="Start date cannot be after end date."
        )
    
    if (end_date - start_date) > timedelta(days=31):
         raise HTTPException(
            status_code=400, 
            detail="Query range cannot exceed 1 month (31 days)."
        )

    query = db.query(
        MetricDB.metric_type,
        func.count(MetricDB.value).label('count')
    )

    # Select statistic
    stat_func = {
        "min": func.min(MetricDB.value),
        "max": func.max(MetricDB.value),
        "sum": func.sum(MetricDB.value),
        "average": func.avg(MetricDB.value)
    }
    
    if statistic in stat_func:
        query = query.add_columns(stat_func[statistic].label('result'))
    
    # Filters
    if sensor_ids:
        query = query.filter(MetricDB.sensor_id.in_(sensor_ids))
    if metrics:
        query = query.filter(MetricDB.metric_type.in_(metrics))
    
    query = query.filter(MetricDB.timestamp >= start_date)
    query = query.filter(MetricDB.timestamp <= end_date)

    # Group by metric type
    query = query.group_by(MetricDB.metric_type)
    
    results = query.all()
    
    output = []
    for row in results:
        m_type = row[0]
        val = row[2]
        
        if val is not None:
            output.append({
                "metric_type": m_type,
                "statistic": statistic,
                "value": round(val, 2)
            })
        
    return output

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
