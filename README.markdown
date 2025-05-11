# Face Analysis and Storage System (FAAS)

## Project Concepts

The Face Analysis and Storage System (FAAS) is a distributed microservices application designed to process images, analyze facial features, estimate age and gender, and store results with high efficiency and scalability. Leveraging gRPC, Docker, Redis, and MongoDB, FAAS provides a robust pipeline for applications like security surveillance, identity verification, or social media analytics.

### Purpose 
FAAS enables real-time image processing and analysis with:
- **Facial Analysis**: Detect and extract facial features such as bounding boxes and landmarks.
- **Age and Gender Estimation**: Analyze images to estimate age and gender.
- **Scalability**: Microservices allow independent scaling for high-throughput workloads.
- **Performance**: Redis caching minimizes latency and database load.
- **Reliability**: MongoDB ensures durable, queryable storage.

### Schematic
![Alt text](./schematic.PNG)

### Technical Concepts
FAAS is built on advanced principles:
- **Microservices**: Four services (`image-input-service`, `face-analysis-service`, `agender-analysis-service`, `data-storage-service`) handle distinct tasks, enhancing modularity.
- **gRPC**: High-performance RPC with Protocol Buffers for type-safe, asynchronous communication using `grpc.aio` for non-blocking operations.
- **Concurrency and Asynchronous Processing**: Utilizes Python's `asyncio` for asynchronous I/O, enabling concurrent request handling. Services like `image-input-service` and `data-storage-service` use `asyncio.Queue` for non-blocking request queuing, while `grpc.aio` supports async gRPC servers. Thread pools (`concurrent.futures.ThreadPoolExecutor`) are used in synchronous services like `face-analysis-service` for parallel task execution.
- **Queue-Based Processing**: Non-blocking request handling with `asyncio.Queue` ensures efficient load management and continuous service availability.
- **Caching**: Redis stores temporary results in hashes to optimize performance and prevent overwrites.
- **Persistence**: MongoDB supports structured storage with separate collections for face and agender results.
- **Containerization**: Docker ensures consistency, with `my-python-base` optimizing dependencies.
- **Orchestration**: Docker Compose manages networking and dependencies.

### Microservices Technical Details
Each microservice incorporates sophisticated features:
- **image-input-service**:
  - **Concurrent Async Processing**: Employs an async gRPC server (`grpc.aio`) with `asyncio.Queue` to handle concurrent image requests. Uses `asyncio.gather` to forward images to `face-analysis-service` and `agender-analysis-service` concurrently, ensuring low-latency routing.
  - **Image Validation**: Checks image formats (JPG, PNG) before forwarding, minimizing errors.
  - **Minimal Footprint**: Optimized for efficient request queuing and forwarding.
- **face-analysis-service**:
  - **InsightFace with ONNX**: Uses `insightface` with pre-trained ONNX models for accurate facial detection and feature extraction (bounding boxes, 2D/3D landmarks).
  - **Concurrent Processing**: Utilizes a synchronous gRPC server with a thread pool (`concurrent.futures.ThreadPoolExecutor`) to process multiple image requests in parallel, enhancing throughput.
  - **Redis Hash Caching**: Stores face results in a Redis hash under the `face_results` field, using `hexists` to check for existing results.
  - **Robust Error Handling**: Returns detailed gRPC error messages for invalid inputs.
- **agender-analysis-service**:
  - **InsightFace for Age/Gender**: Employs `insightface` to estimate age and gender, integrated via `image_processor.py`.
  - **Concurrent Processing**: Similar to `face-analysis-service`, uses a thread pool for parallel processing of image requests, ensuring scalability.
  - **Redis Hash Caching**: Stores agender results in a Redis hash under the `agender_results` field, ensuring independent caching.
  - **gRPC Integration**: Processes images via gRPC, forwarding results to `data-storage-service`.
- **data-storage-service**:
  - **MongoDB Storage**: Persists results in three collections: `image_data` (image hashes and GridFS IDs), `face_results`, and `agender_results` for efficient querying.
  - **Async Queue Processing**: Uses an async gRPC server (`grpc.aio`) with `asyncio.Queue` for non-blocking request handling. Offloads synchronous MongoDB/Redis operations to threads via `asyncio.to_thread`, ensuring continuous availability.
  - **Redis Hash Caching**: Caches face and agender results as separate fields in a Redis hash, preventing overwrites.
  - **Atomic Writes**: Ensures data consistency with transactional updates.
  - **Deduplication**: Stores image data only once in GridFS, using `image_data` collection to track unique hashes.

### Workflow
1. A client (`test_client.py`) sends images to `image-input-service` via gRPC.
2. `image-input-service` queues and concurrently forwards images to `face-analysis-service` and `agender-analysis-service`.
3. `face-analysis-service` extracts facial features, caches results in Redis under `face_results`, and sends data to `data-storage-service`.
4. `agender-analysis-service` estimates age and gender, caches results in Redis under `agender_results`, and sends data to `data-storage-service`.
5. `data-storage-service` stores image data in GridFS (if new), persists results in MongoDB (`face_results` or `agender_results`), and caches metadata in Redis.
6. The client receives a success/failure response.

## Architecture

FAAS includes four gRPC-based microservices, a containerized Redis, and a local MongoDB, connected via a Docker bridge network (`faas-network`):
- **image-input-service**: Port `50051`, receives and forwards images.
- **face-analysis-service**: Port `50052`, analyzes facial features, caches in Redis.
- **agender-analysis-service**: Port `50054`, estimates age and gender, caches in Redis.
- **data-storage-service**: Port `50053`, stores results in MongoDB.
- **Redis**: Port `6379`, caching.
- **MongoDB**: Local at `host.docker.internal:27017`, persistence.

Services are containerized and orchestrated with Docker Compose, using `my-python-base`.

## Directory Structure

```
FAAS/
├── Makefile                        # Automates dependency installation, Protobuf generation, and more
├── Dockerfile.Base                 # Defines my-python-base image
├── Dockerfile.data_storage_service # Dockerfile for data-storage-service
├── Dockerfile.face_analysis_service# Dockerfile for face-analysis-service
├── Dockerfile.agender_analysis_service # Dockerfile for agender-analysis-service
├── Dockerfile.image_input_service  # Dockerfile for image-input-service
├── docker-compose.yml              # Orchestrates services and Redis
├── .env                            # Optional port/host settings
├── data/                           # User-created folder for images
│   ├── SingleFace.jpg             # Sample images (user-provided)
│   ├── MultipleFaces.jpg
├── data_storage_service/
│   ├── data_storage_service.py     # Service code
│   ├── requirements.txt            # Dependencies
├── face_analysis_service/
│   ├── face_analysis_service.py    # Service code
│   ├── image_processor.py          # Face analysis logic
│   ├── requirements.txt            # Dependencies
├── agender_analysis_service/
│   ├── agender_analysis_service.py # Service code
│   ├── image_processor.py          # Age/gender analysis logic
│   ├── requirements.txt            # Dependencies
├── image_input_service/
│   ├── image_input_service.py      # Service code
│   ├── requirements.txt            # Dependencies
├── proto_files/
│   ├── common_pb2.py               # Shared Protobuf definitions
│   ├── data_storage_pb2.py         # Data storage Protobuf
│   ├── data_storage_pb2_grpc.py    # Data storage gRPC stubs
│   ├── face_analysis_pb2.py        # Face analysis Protobuf
│   ├── face_analysis_pb2_grpc.py   # Face analysis gRPC stubs
│   ├── agender_analysis_pb2.py     # Agender analysis Protobuf
│   ├── agender_analysis_pb2_grpc.py# Agender analysis gRPC stubs
│   ├── image_input_pb2.py          # Image input Protobuf
│   ├── image_input_pb2_grpc.py     # Image input gRPC stubs
├── tests/
│   ├── test_client.py              # Client for testing
```

## Prerequisites

- **Operating System**: Windows (tested), Linux, macOS.
- **Docker**: Docker Desktop (Windows/macOS) or Docker Engine (Linux) with Docker Compose.
- **MongoDB**: Local instance on `localhost:27017`.
- **Python**: Python 3.9+ (for `Makefile` and `test_client.py`).
- **Make**: GNU Make for automation.
- **Git**: Optional for cloning.

## Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd FAAS
   ```
   Or place files in `E:\S\Mine\work\Tasks\Task_88_DidehNegarHooshNow\Sajad\sajad\FAAS`.

2. **Install Docker**
   - Windows/macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop/).
   - Linux: [Docker Engine](https://docs.docker.com/engine/install/), [Docker Compose](https://docs.docker.com/compose/install/).
   Verify:
   ```bash
   docker --version
   docker-compose --version
   ```

3. **Set Up MongoDB**
   Ensure `localhost:27017`:
   ```bash
   mongosh --eval "db.runCommand({ ping: 1 })"
   ```
   Install [MongoDB Community Server](https://www.mongodb.com/try/download/community) if needed:
   ```bash
   mongod --dbpath <your-data-directory>
   ```

4. **Install Dependencies**
   Run `make install` to install Python dependencies:
   ```bash
   make install
   ```
   Installs `grpcio`, `redis`, `pymongo`, `insightface`, `opencv-python`, etc., from `requirements.txt` files.

5. **Generate Protobuf Files**
   Run `make proto` to generate Protobuf files:
   ```bash
   make proto
   ```
   Executes `proto_generator.py` to create `*_pb2.py` and `*_pb2_grpc.py` in `proto_files/`, clearing old files to prevent conflicts.

6. **Create Data Folder**
   Create `data/` and add images (JPG, PNG) for processing:
   ```bash
   mkdir data
   copy <your-images> data/
   ```

## Environment Configuration

Use a `.env` file to customize ports/hosts:
```env
MONGO_HOST=host.docker.internal
MONGO_PORT=27017
REDIS_HOST=redis
REDIS_PORT=6379
GRPC_PORT_IMAGE_INPUT=50051
GRPC_PORT_FACE_ANALYSIS=50052
GRPC_PORT_DATA_STORAGE=50053
GRPC_PORT_AGENDER_ANALYSIS=50054
STORAGE_ADDRESS=data-storage-service:50053
FACE_ANALYSIS_ADDRESS=face-analysis-service:50052
AGENDER_ANALYSIS_ADDRESS=agender-analysis-service:50054
```
- If ports change (e.g., `GRPC_PORT_IMAGE_INPUT=50551`), update `test_client.py`:
  ```bash
  python tests/test_client.py --image_input_address localhost:50551
  ```
- For Linux, set `MONGO_HOST` to host IP (e.g., `192.168.1.x`).

## Makefile Usage

The `Makefile` automates tasks for development and production, requiring manual `OS_TYPE` setting (`Windows` or `Unix`) for cross-platform compatibility:

### Development Phase
- **format**: Formats code using `black` across all directories (`.`, `image_input_service`, `face_analysis_service`, `agender_analysis_service`, `data_storage_service`, `proto_files`).
  ```bash
  make format
  ```
- **clean**: Applies `autopep8` with aggressive options to ensure PEP 8 compliance.
  ```bash
  make clean
  ```
- **venv**: Creates a virtual environment (`.venv`) for isolated development.
  ```bash
  make venv
  ```
- **test**: Runs services on test ports (`60050`, `60052`, `60054`, `60053`), executes `test_client.py`, and cleans up processes.
  ```bash
  make test
  ```
- **help**: Displays available targets and descriptions.
  ```bash
  make help
  ```

### Production Phase
- **install**: Installs Python dependencies from `requirements.txt` files for local development or testing, but does not build or run Docker containers. For production, follow the steps in **Running the System** to build and deploy services using Docker Compose.
  ```bash
  make install
  ```
- **proto**: Generates Protobuf files using `proto_generator.py`. Existing Protobuf files are automatically cleared before generating new ones.
  ```bash
  make proto
  ```
- **cleanall**: Removes generated files (`.pyc`, `__pycache__`, `.log`, `.pytest_cache`, `.mypy_cache`) to ensure a clean environment.
  ```bash
  make cleanall
  ```

## Docker Setup

### Base Image (my-python-base)
`Dockerfile.Base` defines `my-python-base`:
- Starts from `python:3.9-slim`.
- Installs system dependencies (`gcc`, `libgomp1`, `libgl1`) for `insightface`.
- Installs Python packages (`grpcio`, `redis`, `pymongo`, `insightface`, `onnxruntime`, `numpy`).
- Configures unbuffered output for logs.

### Service Dockerfiles
Each `Dockerfile` extends `my-python-base`:
- Copies service code, `image_processor.py` (for analysis services), and Protobuf files.
- Sets environment variables and commands (e.g., `python agender_analysis_service.py`).

### Docker Compose
`docker-compose.yml` orchestrates:
- Builds `my-python-base`.
- Runs services on ports `50051`, `50052`, `50054`, `50053`.
- Configures Redis on `6379` with a persistent volume.
- Uses `faas-network` for communication.

## Running the System

1. **Verify MongoDB**
   ```bash
   mongosh --eval "db.runCommand({ ping: 1 })"
   ```

2. **Check Ports**
   Ensure `50051`, `50052`, `50054`, `50053`, `6379` are free:
   ```bash
   netstat -a -n -o | findstr "50051 50052 50054 50053 6379"
   ```
   Free ports:
   ```bash
   taskkill /PID <pid> /F
   ```

3. **Build and Run**
   ```bash
   cd E:\S\Mine\work\Tasks\Task_88_DidehNegarHooshNow\Sajad\sajad\FAAS
   docker-compose up -d --build
   ```

4. **Verify Containers**
   ```bash
   docker ps
   ```
   Expected:
   ```
   CONTAINER ID   IMAGE                     COMMAND                  CREATED        STATUS        PORTS                    NAMES
   <id>           image-input-service       "sh -c 'python image…"   <time>         Up <time>     0.0.0.0:50051->50051/tcp faas_image-input-service_1
   <id>           face-analysis-service-2   "sh -c 'python face_…"   <time>         Up <time>     0.0.0.0:50052->50052/tcp faas_face-analysis-service_1
   <id>           agender-analysis-service  "sh -c 'python agend…"   <time>         Up <time>     0.0.0.0:50054->50054/tcp faas_agender-analysis-service_1
   <id>           data-storage-service      "sh -c 'python data_…"   <time>         Up <time>     0.0.0.0:50053->50053/tcp faas_data-storage-service_1
   <id>           redis                     "docker-entrypoint.s…"   <time>         Up <time>     0.0.0.0:6379->6379/tcp   faas_redis_1
   ```

5. **Check Logs**
   ```bash
   docker-compose logs data-storage-service
   docker-compose logs face-analysis-service
   docker-compose logs agender-analysis-service
   docker-compose logs image-input-service
   docker-compose logs redis
   ```
   Expected:
   - `data-storage-service`: Connected to MongoDB/Redis, listening on `0.0.0.0:50053`.
   - `face-analysis-service`: Connected to Redis, listening on `0.0.0.0:50052`.
   - `agender-analysis-service`: Connected to Redis, listening on `0.0.0.0:50054`.
   - `image-input-service`: Listening on `50051`.
   - `redis`: Ready to accept connections.

6. **Test**
   ```bash
   python tests/test_client.py
   ```
   Expected:
   ```
   INFO:__main__:Found <n> images in ./data/
   INFO:__main__:Response for <image>.jpg: Success=True, Error=
   ...
   ```
   If ports changed in `.env`:
   ```bash
   python tests/test_client.py --image_input_address localhost:<new-port>
   ```

7. **Stop**
   ```bash
   docker-compose down
   ```
   Clean up:
   ```bash
   docker-compose down -v --rmi all
   ```

## Troubleshooting

- **Connection Refused (localhost:50051)**:
  - Verify `image-input-service` (`docker ps`).
  - Check port mapping.
  - Allow firewall:
    ```bash
    netsh advfirewall firewall add rule name="FAAS Ports" dir=in action=allow protocol=TCP localport=50051,50052,50054,50053
    ```
- **MongoDB Issues**:
  - Ensure `localhost:27017`.
  - Update `.env` for Linux.
- **Redis Errors**:
  - Check `redis` logs.
  - Verify `REDIS_HOST=redis`.
- **Protobuf Errors**:
  - Rerun `make proto`.

## Maintenance

- **Update Dependencies**:
  Edit `Dockerfile.Base`, rebuild:
  ```bash
  docker-compose build --no-cache
  ```
- **Clean Protobuf Files**:
  ```bash
  cd data_storage_service
  del face_analysis_pb2.py face_analysis_pb2_grpc.py image_input_pb2.py image_input_pb2_grpc.py agender_analysis_pb2.py agender_analysis_pb2_grpc.py
  cd ../face_analysis_service
  del common_pb2.py data_storage_pb2.py data_storage_pb2_grpc.py image_input_pb2.py image_input_pb2_grpc.py agender_analysis_pb2.py agender_analysis_pb2_grpc.py
  cd ../agender_analysis_service
  del common_pb2.py data_storage_pb2.py data_storage_pb2_grpc.py face_analysis_pb2.py face_analysis_pb2_grpc.py image_input_pb2.py image_input_pb2_grpc.py
  cd ../image_input_service
  del common_pb2.py data_storage_pb2.py data_storage_pb2_grpc.py face_analysis_pb2.py face_analysis_pb2_grpc.py agender_analysis_pb2.py agender_analysis_pb2_grpc.py
  ```
- **Dockerize test_client.py**:
  Contact maintainer for `Dockerfile.test_client`.

## Contributing

- Fork, branch (`git checkout -b feature-name`), commit (`git commit -m "Add feature"`), push (`git push origin feature-name`), pull request.

## License

MIT License. See [LICENSE](LICENSE).