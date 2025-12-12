from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone
import pytest
from main import app, get_db, Base, MetricDB

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_create_metric():
    response = client.post(
        "/metrics",
        json={
            "sensor_id": "sensor1",
            "metric_type": "temperature",
            "value": 25.5
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sensor_id"] == "sensor1"
    assert data["value"] == 25.5
    assert "id" in data
    assert "timestamp" in data

def test_query_metrics_average():
    # Insert data
    client.post("/metrics", json={"sensor_id": "s1", "metric_type": "temp", "value": 20.0})
    client.post("/metrics", json={"sensor_id": "s1", "metric_type": "temp", "value": 30.0})
    client.post("/metrics", json={"sensor_id": "s1", "metric_type": "humidity", "value": 50.0})

    # Query average temp
    response = client.get("/metrics/query?statistic=average&metrics=temp&sensor_ids=s1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["metric_type"] == "temp"
    assert data[0]["value"] == 25.0
    assert data[0]["statistic"] == "average"

def test_query_metrics_min_max():
    client.post("/metrics", json={"sensor_id": "s2", "metric_type": "speed", "value": 10.0})
    client.post("/metrics", json={"sensor_id": "s2", "metric_type": "speed", "value": 20.0})

    # Query max
    response = client.get("/metrics/query?statistic=max&metrics=speed")
    assert response.status_code == 200
    assert response.json()[0]["value"] == 20.0

    # Query min
    response = client.get("/metrics/query?statistic=min&metrics=speed")
    assert response.status_code == 200
    assert response.json()[0]["value"] == 10.0

def test_query_date_range():
    # Insert old data
    old_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    client.post("/metrics", json={"sensor_id": "s3", "metric_type": "pressure", "value": 1000.0, "timestamp": old_date})
    
    # Insert new data
    client.post("/metrics", json={"sensor_id": "s3", "metric_type": "pressure", "value": 1010.0})

    # Query last 24 hours (default)
    response = client.get("/metrics/query?statistic=average&metrics=pressure")
    data = response.json()
    assert len(data) == 1
    assert data[0]["value"] == 1010.0  # Should only include new data

    # Query wider range
    start_date = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    response = client.get("/metrics/query", params={
        "statistic": "average",
        "metrics": "pressure",
        "start_date": start_date
    })
    data = response.json()
    # Average of 1000 and 1010 is 1005
    assert len(data) > 0
    assert data[0]["value"] == 1005.0

def test_invalid_statistic():
    response = client.get("/metrics/query?statistic=median")
    assert response.status_code == 422

def test_query_invalid_date_range():
    # Start > End
    response = client.get("/metrics/query", params={
        "statistic": "average",
        "start_date": "2023-01-02T00:00:00",
        "end_date": "2023-01-01T00:00:00"
    })
    assert response.status_code == 400
    assert "Start date cannot be after end date" in response.json()["detail"]

    # Range > 31 days
    response = client.get("/metrics/query", params={
        "statistic": "average",
        "start_date": "2023-01-01T00:00:00",
        "end_date": "2023-03-01T00:00:00"
    })
    assert response.status_code == 400
    assert "cannot exceed 1 month" in response.json()["detail"]

def test_query_implicit_defaults():
    # Insert data at T-2 days
    t_minus_2 = datetime.now(timezone.utc) - timedelta(days=2)
    client.post("/metrics", json={"sensor_id": "s_implicit", "metric_type": "val", "value": 100.0, "timestamp": t_minus_2.isoformat()})
    
    # 1. Query with only start_date = T-3 days. End date defaults to Now.
    start = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    response = client.get("/metrics/query", params={
        "statistic": "average", 
        "metrics": "val",
        "start_date": start
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["value"] == 100.0
    
    # 2. Query with only end_date = T-1 day. Start defaults to T-2 days.
    t_minus_1_5 = datetime.now(timezone.utc) - timedelta(days=1, hours=12)
    client.post("/metrics", json={"sensor_id": "s_implicit_2", "metric_type": "val2", "value": 50.0, "timestamp": t_minus_1_5.isoformat()})
    
    end = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = client.get("/metrics/query", params={
        "statistic": "average", 
        "metrics": "val2",
        "end_date": end
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["value"] == 50.0


