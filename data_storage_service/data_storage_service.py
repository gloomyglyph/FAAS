import grpc
from concurrent import futures
import logging
import socket
import pymongo
from pymongo import MongoClient
from gridfs import GridFS
import data_storage_pb2
import data_storage_pb2_grpc
import common_pb2
import json
from bson import json_util
import hashlib

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


def convert_face_results_to_json(face_results):
    """Convert FaceResult messages to JSON-serializable format."""
    json_face_results = []
    for fr in face_results:
        # Convert bbox to list of floats
        bbox = [float(x) for x in fr.bbox]

        # Convert landmark_2d_106 to list of dicts
        landmarks_2d = [
            {"x": float(lm.x), "y": float(lm.y)} for lm in fr.landmark_2d_106
        ]

        # Convert landmark_3d_68 to list of dicts
        landmarks_3d = [
            {"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)}
            for lm in fr.landmark_3d_68
        ]

        json_face_results.append(
            {
                "bbox": bbox,
                "landmark_2d_106": landmarks_2d,
                "landmark_3d_68": landmarks_3d,
                "age": int(fr.age),
                "gender": fr.gender,
            }
        )
    return json_face_results


def prepare_and_validate_document(image_id, gridfs_id, image_hash, face_results):
    """Prepare MongoDB document and validate its JSON serializability."""
    document = {
        "image_id": image_id,
        "gridfs_id": gridfs_id,
        "image_hash": image_hash,
        "face_results": face_results,
    }

    # Remove None values
    document = {k: v for k, v in document.items() if v is not None}

    # Validate JSON serializability
    try:
        json.dumps(document, default=json_util.default)
        return document, None
    except Exception as e:
        logger.error(f"Document validation failed: {str(e)}")
        return None, str(e)


class DataStorageServicer(data_storage_pb2_grpc.DataStorageServiceServicer):
    def __init__(self):
        self.client = MongoClient("mongodb://localhost:27017/")
        self.db = self.client["face_analysis_db"]
        self.fs = GridFS(self.db)
        logger.info("Connected to MongoDB")

    def StoreFaceResult(self, request, context):
        try:
            image_id = request.image_id
            image_data = request.image_data

            # Compute image hash
            image_hash = compute_image_hash(image_data)
            logger.info(f"Computed image hash: {image_hash}")

            # Store image in GridFS
            gridfs_id = store_image_in_gridfs(self.fs, image_data, image_id)

            # Convert face results to JSON-serializable format
            json_face_results = convert_face_results_to_json(request.face_results)

            # Prepare and validate document
            document, validation_error = prepare_and_validate_document(
                image_id, gridfs_id, image_hash, json_face_results
            )
            if validation_error:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Invalid document structure: {validation_error}")
                return common_pb2.DoneFlagToFaceAnalysisServiceResponse(
                    success=False, error_message=validation_error
                )

            # Insert document into MongoDB
            self.db.face_results.insert_one(document)
            logger.info(f"Stored face result for image ID: {image_id}")
            return common_pb2.DoneFlagToFaceAnalysisServiceResponse(
                success=True, error_message=""
            )

        except Exception as e:
            logger.error(
                f"Error storing face result for image ID: {image_id}: {str(e)}"
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error storing face result: {str(e)}")
            return common_pb2.DoneFlagToFaceAnalysisServiceResponse(
                success=False, error_message=str(e)
            )


def serve():
    default_port = 50053
    try:
        port = find_available_port(default_port)
        if port != default_port:
            logger.warning(f"Port {default_port} is in use, using port {port} instead.")

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        data_storage_pb2_grpc.add_DataStorageServiceServicer_to_server(
            DataStorageServicer(), server
        )
        server.add_insecure_port(f"[::]:{port}")
        logger.info(f"Data Storage Service starting on port {port}...")
        server.start()
        server.wait_for_termination()
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise


if __name__ == "__main__":
    serve()
