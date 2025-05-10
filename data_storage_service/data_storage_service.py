import grpc
from concurrent import futures
import logging
import socket
import pymongo
from pymongo import MongoClient
from gridfs import GridFS
import redis
import data_storage_pb2
import data_storage_pb2_grpc
import common_pb2
import json
from bson import json_util
import hashlib
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return False
        except socket.error:
            return True

def find_available_port(start_port, max_attempts=100):
    """Find an available port starting from start_port."""
    port = start_port
    for _ in range(max_attempts):
        if not is_port_in_use(port):
            return port
        port += 1
    raise RuntimeError(f"No available port found starting from {start_port}")

def compute_image_hash(image_data):
    """Compute SHA-256 hash of the image data."""
    return hashlib.sha256(image_data).hexdigest()

def store_image_in_gridfs(gridfs, image_data, image_id):
    """Store image data in GridFS and return the gridfs_id."""
    gridfs_id = str(gridfs.put(image_data, filename=image_id))
    logger.info(f"Stored image in GridFS with ID: {gridfs_id}")
    return gridfs_id

def store_image_data(db, gridfs, image_data, image_id, image_hash):
    """Store image data in GridFS and image_data collection if not already present."""
    existing_image = db.image_data.find_one({"image_hash": image_hash})
    if existing_image:
        logger.info(f"Image hash {image_hash} already exists in image_data collection.")
        return existing_image["gridfs_id"]
    else:
        gridfs_id = store_image_in_gridfs(gridfs, image_data, image_id)
        db.image_data.insert_one({"image_hash": image_hash, "gridfs_id": gridfs_id})
        logger.info(f"Stored new image data for hash: {image_hash}")
        return gridfs_id

def convert_face_results_to_json(face_results):
    """Convert FaceResult messages to JSON-serializable format."""
    json_face_results = []
    for fr in face_results:
        bbox = [float(x) for x in fr.bbox]
        landmarks_2d = [{"x": float(lm.x), "y": float(lm.y)} for lm in fr.landmark_2d_106]
        landmarks_3d = [{"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)} for lm in fr.landmark_3d_68]
        json_face_results.append({
            "bbox": bbox,
            "landmark_2d_106": landmarks_2d,
            "landmark_3d_68": landmarks_3d,
        })
    return json_face_results

def convert_agender_results_to_json(agender_results):
    """Convert AgenderResult messages to JSON-serializable format."""
    json_agender_results = []
    for ar in agender_results:
        json_agender_results.append({
            "age": int(ar.age),
            "gender": ar.gender,
        })
    return json_agender_results

def prepare_and_validate_document(image_id, image_hash, results, result_type):
    """Prepare MongoDB document for analysis results and validate its JSON serializability."""
    document = {
        "image_id": image_id,
        "image_hash": image_hash,
        f"{result_type}_results": results,
    }
    document = {k: v for k, v in document.items() if v is not None}
    try:
        json.dumps(document, default=json_util.default)
        return document, None
    except Exception as e:
        logger.error(f"Document validation failed: {str(e)}")
        return None, str(e)

def store_in_redis(redis_client, image_hash, document):
    """Store document in Redis with image_hash as the key."""
    try:
        json_data = json.dumps(document, default=json_util.default)
        redis_client.set(image_hash, json_data)
        logger.info(f"Stored document in Redis with key: {image_hash}")
        return None
    except redis.RedisError as e:
        logger.error(f"Failed to store document in Redis: {str(e)}")
        return str(e)

class DataStorageServicer(data_storage_pb2_grpc.DataStorageServiceServicer):
    def __init__(self, mongo_host="localhost", mongo_port=27017, redis_host="localhost", redis_port=6379):
        self.client = MongoClient(f"mongodb://{mongo_host}:{mongo_port}/")
        self.db = self.client["face_analysis_db"]
        self.fs = GridFS(self.db)
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
        try:
            self.redis_client.ping()
            logger.info("Connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
        logger.info(f"Connected to MongoDB at {mongo_host}:{mongo_port}")

    def StoreFaceResult(self, request, context):
        try:
            image_id = request.image_id
            image_data = request.image_data
            image_hash = compute_image_hash(image_data)
            logger.info(f"Computed image hash: {image_hash}")
            # Store image data and get gridfs_id (only stores if hash doesn't exist)
            gridfs_id = store_image_data(self.db, self.fs, image_data, image_id, image_hash)
            # Store face results separately
            json_face_results = convert_face_results_to_json(request.face_results)
            document, validation_error = prepare_and_validate_document(
                image_id, image_hash, json_face_results, "face"
            )
            if validation_error:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Invalid document structure: {validation_error}")
                return common_pb2.DoneFlagToFaceAnalysisServiceResponse(
                    success=False, error_message=validation_error
                )
            self.db.face_results.insert_one(document)
            logger.info(f"Stored face result for image ID: {image_id}")
            redis_error = store_in_redis(self.redis_client, image_hash, document)
            if redis_error:
                logger.warning(f"Proceeding despite Redis error: {redis_error}")
            return common_pb2.DoneFlagToFaceAnalysisServiceResponse(success=True, error_message="")
        except Exception as e:
            logger.error(f"Error storing face result for image ID: {image_id}: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error storing face result: {str(e)}")
            return common_pb2.DoneFlagToFaceAnalysisServiceResponse(success=False, error_message=str(e))

    def StoreAgenderResult(self, request, context):
        try:
            image_id = request.image_id
            image_data = request.image_data
            image_hash = compute_image_hash(image_data)
            logger.info(f"Computed image hash: {image_hash}")
            # Store image data and get gridfs_id (only stores if hash doesn't exist)
            gridfs_id = store_image_data(self.db, self.fs, image_data, image_id, image_hash)
            # Store agender results separately
            json_agender_results = convert_agender_results_to_json(request.agender_results)
            document, validation_error = prepare_and_validate_document(
                image_id, image_hash, json_agender_results, "agender"
            )
            if validation_error:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Invalid document structure: {validation_error}")
                return common_pb2.DoneFlagToAgenderAnalysisServiceResponse(
                    success=False, error_message=validation_error
                )
            self.db.agender_results.insert_one(document)
            logger.info(f"Stored agender result for image ID: {image_id}")
            redis_error = store_in_redis(self.redis_client, image_hash, document)
            if redis_error:
                logger.warning(f"Proceeding despite Redis error: {redis_error}")
            return common_pb2.DoneFlagToAgenderAnalysisServiceResponse(success=True, error_message="")
        except Exception as e:
            logger.error(f"Error storing agender result for image ID: {image_id}: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error storing agender result: {str(e)}")
            return common_pb2.DoneFlagToAgenderAnalysisServiceResponse(success=False, error_message=str(e))

def serve(host: str, port: int, mongo_host: str, mongo_port: int, redis_host: str, redis_port: int):
    if is_port_in_use(port):
        port = find_available_port(port)
        logger.warning(f"Port is in use, using alternative available port: {port}")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    data_storage_pb2_grpc.add_DataStorageServiceServicer_to_server(
        DataStorageServicer(mongo_host=mongo_host, mongo_port=mongo_port, redis_host=redis_host, redis_port=redis_port), server
    )
    server.add_insecure_port(f"{host}:{port}")
    logger.info(f"Data Storage Service starting on {host}:{port}...")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start gRPC Data Storage Service")
    parser.add_argument("--host", type=str, default="localhost", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=50053, help="Port to run the server on")
    parser.add_argument("--mongo-host", type=str, default="localhost", help="MongoDB host")
    parser.add_argument("--mongo-port", type=int, default=27017, help="MongoDB port")
    parser.add_argument("--redis-host", type=str, default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    args = parser.parse_args()
    serve(args.host, args.port, args.mongo_host, args.mongo_port, args.redis_host, args.redis_port)