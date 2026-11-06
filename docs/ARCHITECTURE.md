# Atlas — System Architecture

> Comprehensive system architecture document covering Microservices, 
> the Data Layer, Background Workers, API definitions, and Config.

---

## 1. Microservices Topology

Atlas relies on a distributed computing cluster built on top of Docker Compose. 

```text
┌──────────────────────────────────────────────────────────────┐
│                    ATLAS TERMINAL (Web UI)                   │
│                    React 19 (Port 3000)                      │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼  REST API / WebSockets
┌──────────────────────────────────────────────────────────────┐
│                  ATLAS API GATEWAY & APP                     │
│                  FastAPI (Port 8000 / 8001)                  │
│       server.py | workspace_api.py | api_learning.py         │
└──────┬──────────────────────┬───────────────────────┬────────┘
       │                      │                       │
       ▼                      ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   MongoDB    │       │    Redis     │       │    MinIO     │
│ (Port 27017) │       │ (Port 6379)  │       │ (Port 9000/1)│
│  Metadata    │       │ Message Bus  │       │  Artifacts   │
└──────▲───────┘       └──────▲───────┘       └──────▲───────┘
       │                      │                       │
       │                      ▼                       │
       │               ┌──────────────┐               │
       └───────────────┤ Celery Worker├───────────────┘
                       │ (Background) │
                       └──────────────┘
```

### Docker Compose Services

1. **`api`** (Port 8000)
   - **Build Context:** Base directory (`.`).
   - **Environment:** Connected to `mongo`, `redis`, and `minio`. `ATLAS_ENV=development`.
   - **Volumes:** Mounts `./apps/api` and `./libs/python` for live reloading.
   - **Role:** Handles synchronous requests, fetches market data, coordinates the Decision Engine, orchestrates the Feature Registry (Atlas Core).

2. **`web`** (Port 3000)
   - **Build Context:** `./apps/web`
   - **Environment:** Connects to API at `http://localhost:8000`.
   - **Role:** The frontend UI layer.

3. **`worker`**
   - **Command:** `celery -A apps.api.worker.celery_app worker --loglevel=info`
   - **Role:** Background asynchronous task processor. Performs CPU-bound ML training via XGBoost and long-running walk-forward validations.

4. **`mongo`** (Port 27017)
   - **Image:** `mongo:6.0`
   - **Volume:** `mongo_data`
   - **Role:** NoSQL document database for metadata persistence.

5. **`redis`** (Port 6379)
   - **Image:** `redis:7-alpine`
   - **Role:** Celery task broker and backend.

6. **`minio`** (Port 9000 API / 9001 Console)
   - **Image:** `minio/minio`
   - **Volume:** `minio_data`
   - **Credentials:** `minioadmin` / `minioadmin`
   - **Role:** S3-compatible blob storage for model binaries (`.pkl`) and artifacts.

---

## 2. MongoDB Data Layer

The `atlas_dev` database manages structured metadata across several collections.

### Core Collections

1. **`predictions`**
   - **Purpose:** Stores the history of machine learning predictions.
   - **Schema:** 
     - `symbol` (str), `horizon` (int), `model` (str)
     - `prediction` (dict): Direction, probability, expected_move.
     - `metrics` (dict): accuracy, precision, recall.
     - `created_at` (timestamp)

2. **`recommendations`**
   - **Purpose:** Outputs from the Layer-5 Decision Engine voter.
   - **Schema:** 
     - `symbol` (str), `provider` (str), `horizon` (int).
     - `action` (str), `confidence` (float).
     - `ml_advisor` (dict), `peer_context` (dict).
     - `created_at` (timestamp)

3. **`atlas_models`**
   - **Purpose:** Registry for trained ML models.
   - **Schema:** 
     - `model_id` (str, unique)
     - `kind` (str)
     - `metrics` (dict)
     - `experiment_id` (str), `feature_ids` (List[str]).

4. **`atlas_bots`**
   - **Purpose:** Paper trading portfolio execution daemons.
   - **Schema:** 
     - `name` (str), `market` (str), `status` (str)
     - `allocation` (float), `unrealized_pnl` (float), `trades_count` (int).

### Learning System Collections

5. **`atlas_datasets`**
   - **Purpose:** Manifests of prepared ML training datasets.
   - **Schema:** `project_id`, `description`, `features`, `targets`.
   
6. **`atlas_experiments`** / **`learning_experiments`**
   - **Purpose:** Defines ML hyperparameter sweeps and configuration.
   - **Schema:** `spec.tags`, `spec.name`, `aggregate.accuracy_mean`, `created_at`.
   
7. **`learning_models`**
   - **Purpose:** Production inference model metadata.
   - **Schema:** `model_id`, `hyperparameters`, `blob_uri`.

8. **`learning_backtests`** / **`atlas_backtests`**
   - **Purpose:** Out-of-sample portfolio simulation results.
   - **Schema:** `spec.tags`, `spec.symbol`, `metrics.sharpe_ratio`, `metrics.drawdown`.

### Workspace Collections

9. **`atlas_projects`**
   - **Purpose:** Research workspace organization.
   - **Schema:** `name`, `description`, `status`, `tags`, `scratchpad`, `open_questions`, `created_at`, `updated_at`, `experiment_count`, `note_count`.

10. **`atlas_notes`**
    - **Purpose:** Researcher notes attached to projects.
    - **Schema:** `project_id`, `type` (Hypothesis, Finding, Decision, Question), `title`, `body`, `resolution_status`, `feature_ids`.

11. **`atlas_users`**
    - **Purpose:** Role-based access control and team organization.
    - **Schema:** `email`, `role`, `status`, `last_active`.

---

## 3. MinIO Artifact Storage

MinIO replaces AWS S3 for local environments.

- **Bucket Name:** Typically `atlas-artifacts` or specific to storage module context.
- **Artifacts stored:**
  - Machine Learning Model Binaries (e.g. `models/{exp_id}.pkl`) uploaded by the Celery worker.
  - Large Dataset CSVs or Parquet files.
  - Backtest graphical tear sheets (images).

---

## 4. Celery Task Queue

Background asynchronous processing is managed by Celery (`worker.py`).

**Configuration:**
- **Broker:** Redis (`redis://redis:6379/0`)
- **Backend:** Redis

**Key Tasks:**
- `train_experiment(exp_id, project_id, dataset_id, feature_ids, target_id, validation_config)`
  - Uses `xgboost` (if available) or `LogisticRegression`.
  - Performs walk-forward cross-validation (PurgedKFold-style) simulating embargoed bars.
  - Pickles the model and uploads it to MinIO (`models/{exp_id}.pkl`).
  - Updates MongoDB with completion status.

---

## 5. API Routing and Endpoints

The API is structured in FastAPI and mounted primarily under `/api`.

**`server.py` Endpoints:**
- `GET /api/registry/stats`, `GET /api/registry/features` - Feature definitions.
- `GET /api/market/ohlcv` - Market Data ingestion.
- `GET /api/features/values`, `GET /api/features/correlation` - Core layer computations.
- `GET /api/analysis/snapshot` - Market explanation.
- `POST /api/predict/train`, `POST /api/predict/compare` - On-the-fly ML.
- `GET /api/analysis/portfolio` - Real-time bot metrics.
- `POST /api/decision/recommend` - Core Layer 5 entry point.
- `POST /api/decision/learned_weights`, `POST /api/decision/regime_conditional_weights` - Weight tuning.
- `GET /api/validation/report`, `GET /api/validation/profile/{id}` - Golden test execution and validation profiles.

**`workspace_api.py` Endpoints:**
- `GET|POST /api/projects` - Workspace lifecycle.
- `PATCH /api/projects/{id}`, `DELETE /api/projects/{id}`
- `GET|POST /api/projects/{id}/notes` - Notes lifecycle.
- `GET /api/knowledge/notes` - Global note search.
- `POST /api/ai/suggest-features`, `POST /api/ai/summarize-project` - Helper AI endpoints.
- `WS /api/workspace/notes/ws/{client_id}` - WebSocket for collaborative presence.

**Daemon Management:**
- `POST /api/daemons/{daemon_name}/toggle` - Spawns subprocesses for `stat-arb`, `whale-hunter`, `futures-paper`.

---

## 6. Frontend React Architecture

The Web UI (React 19) interacts with the API Gateway.
Key views include:
- **Decision Terminal:** Polls `decision/recommend` and displays signals, ML advisor recommendations, and live charts using Lightweight Charts.
- **Registry Viewer:** Explores the 925 Atlas Core features across L1–L4 (and 1,039 total platform features), their mathematical formulations, and validation profiles.
- **Workspace:** Project boards and Notes explorer.
- **Live Execution Dashboard:** Displays `atlas_bots` paper trading PNL and live states.
- **Model Training / Lab:** Submits requests to the Celery worker and tracks experiment convergence.

---

## 7. Environment Variables

- `ATLAS_ENV`: development | production
- `MONGO_URL`: Connection string for MongoDB (default `mongodb://mongo:27017`).
- `DB_NAME`: MongoDB database (e.g., `atlas_dev`).
- `REDIS_URL`: Connection string for Redis.
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`: Credentials for artifact storage.
- `CORS_ORIGINS`: Allowed origins for FastAPI.
- `ATLAS_ACCESS_CODES`: Admin authentication tokens.
- `ATLAS_GUEST_CODES`: Read-only authentication tokens (prevents mutating ML/trade endpoints).

---

## 8. Inter-Service Communication

1. **API -> Mongo:** Async motor client (`motor.motor_asyncio.AsyncIOMotorClient`).
2. **API -> Redis:** Async pub/sub for caching and Celery broker connection.
3. **API -> Worker:** API delegates `train_experiment.delay(...)` via Celery; Worker performs heavy processing and writes results back to Mongo and artifacts to MinIO.
4. **API -> External Data Providers:** Yahoo Finance, Binance APIs fetched synchronously or wrapped in threadpools.

