# Sensor Metrics Service

A minimal REST API to receive and query sensor metrics.

## Requirements

- Python 3.8+
- `pip`

## Setup

1. Create a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

Start the server using `uvicorn`:

```bash
python3 main.py
```
Or directly with uvicorn:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Documentation

Interactive API documentation (Swagger UI) is available at:
`http://localhost:8000/docs`

This interface allows you to explore the API and execute requests directly from your browser.

**Example: Insert a Metric**
1. Click on **POST /metrics** to expand it.
2. Click **Try it out**.
3. In the **Request body** field, paste the following JSON:
   ```json
   {
     "sensor_id": "sensor-1",
     "metric_type": "temperature",
     "value": 25.5
   }
   ```
4. Click **Execute**.

**Example: Query Metrics**
1. Click on **GET /metrics/query**.
2. Click **Try it out**.
3. Fill in the parameters:
   - `statistic`: `average`
   - `metrics`: `temperature`
   - `sensor_ids`: `sensor-1`
4. Click **Execute**.

### Endpoints

- **POST /metrics**: Insert a new metric reading.
- **GET /metrics/query**: Query metrics with filters and statistics.

## Usage Examples

### 1. Insert a Metric

**Request:**

```bash
curl -X POST "http://localhost:8000/metrics" \
     -H "Content-Type: application/json" \
     -d '{
           "sensor_id": "sensor-1",
           "metric_type": "temperature",
           "value": 25.5
         }'
```

**Response:**

```json
{
  "sensor_id": "sensor-1",
  "metric_type": "temperature",
  "value": 25.5,
  "timestamp": "2023-10-27T10:00:00.123456",
  "id": 1
}
```

### 2. Query Metrics

Get the **average temperature** for `sensor-1`:

**Request:**

```bash
curl "http://localhost:8000/metrics/query?statistic=average&metrics=temperature&sensor_ids=sensor-1"
```

**Response:**

```json
[
  {
    "metric_type": "temperature",
    "statistic": "average",
    "value": 25.5
  }
]
```

### 3. Query with Date Range

Get the **average temperature** between two specific dates (max 1 month range):

**Request:**

```bash
curl "http://localhost:8000/metrics/query?statistic=average&metrics=temperature&start_date=2023-10-26T00:00:00&end_date=2023-10-27T23:59:59"
```

### 4. Error Handling (Date Range Limit)

If you request a range larger than 1 month:

**Request:**

```bash
curl "http://localhost:8000/metrics/query?statistic=average&metrics=temperature&start_date=2023-01-01T00:00:00&end_date=2023-03-01T00:00:00"
```

**Response (400 Bad Request):**

```json
{
  "detail": "Query range cannot exceed 1 month (31 days)."
}
```

## Running Tests

Run the unit tests using `pytest`:

```bash
pytest test_main.py
```

## Design Notes

- **Architecture**: Single-file FastAPI application (`main.py`) for simplicity and "interview-friendly" review.
- **Database**: SQLite (file-based `metrics.db`) using SQLAlchemy ORM.
- **Validation**: 
  - Pydantic models for request/response validation.
  - Date range validation: Queries are limited to a maximum window of 1 month (31 days).
  - Defaults: If date range is not specified, it defaults to the last 24 hours.
- **Testing**: In-memory SQLite database for fast, isolated unit tests.

