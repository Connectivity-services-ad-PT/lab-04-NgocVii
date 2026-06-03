# RUN_LOCAL.md - IoT Ingestion Service

## Prerequisites

- Docker Desktop (or Docker Engine)
- Node.js 20.x LTS + npm
- Git
- curl (for testing)

## Quick Start (3 steps)

### Step 1: Clone and build

```bash
git clone <your-repo-url>
cd FIT4110_lab04_docker_packaging
npm install
```

### Step 2: Start the service locally

Option 1: Start with Python directly

```bash
python -m uvicorn iot_app.main:app --app-dir src --host 0.0.0.0 --port 8000
```

Option 2: Build and run with Docker

```bash
docker build -t fit4110/iot-ingestion:lab04 .

docker run --rm \
  --name fit4110-iot-lab04 \
  -p 8000:8000 \
  --env-file .env.example \
  fit4110/iot-ingestion:lab04
```

### Step 3: Run Newman tests

```bash
npm run test:local
```

### Health check

```bash
curl http://localhost:8000/health
```

### Example requests

```bash
# Create a reading
curl -X POST http://localhost:8000/readings \
  -H "Authorization: Bearer local-dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-LAB-A01",
    "metric": "temperature",
    "value": 31.5,
    "unit": "celsius",
    "timestamp": "2026-06-03T08:30:00+07:00"
  }'

# Get latest readings
curl "http://localhost:8000/readings/latest?limit=5" \
  -H "Authorization: Bearer local-dev-token"
```