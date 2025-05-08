import logging
import data_storage_pb2_grpc
import common_pb2
import grpc
from concurrent import futures
import os
import sys
from pymongo import MongoClient
from gridfs import GridFS
import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataStorageService(data_storage_pb2_grpc.DataStorageServiceServicer):
    def __init__(self):
        # Initialize MongoDB client
        try:
            self.client = MongoClient("mongodb://localhost:27017")
            self.db = self.client["face_aggregation"]
            self.fs = GridFS(self.db)  # GridFS for storing images
            # Collection for metadata
            self.collection = self.db["face_results"]
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def StoreFaceResult(self, request, context):
        logger.info(f"Storing face result for image ID: {request.image_id}")

        try:
            self.store_data(request)
            logger.info(f"Stored face result for image ID: {request.image_id}")
            return common_pb2.DoneFlagToFaceAnalysisServiceResponse(
                success=True, error_message=""
            )
        except Exception as e:
            logger.error(
                f"Error storing face result for image ID: {request.image_id}: {str(e)}"
            )
            return common_pb2.DoneFlagToFaceAnalysisServiceResponse(
                success=False, error_message=str(e)
            )

    def store_data(self, request):
        """Store image in GridFS and face results in MongoDB collection."""
        # Store image in GridFS
        image_id = request.image_id
        image_data = request.image_data
        if image_data:
            gridfs_id = self.fs.put(image_data, filename=image_id)
            logger.info(f"Stored image in GridFS with ID: {gridfs_id}")
        else:
            gridfs_id = None
            logger.warning(f"No image data provided for image ID: {image_id}")

        # Serialize face results to a list of dictionaries
        face_results = []
        for result in request.face_results:
            face_result = {
                "bbox": result.bbox,
                "landmark_2d_106": [
                    {"x": p.x, "y": p.y} for p in result.landmark_2d_106
                ],
                "landmark_3d_68": [
                    {"x": p.x, "y": p.y, "z": p.z} for p in result.landmark_3d_68
                ],
                "age": result.age,
                "gender": result.gender,
            }
            face_results.append(face_result)

        # Store metadata in collection
        document = {
            "image_id": image_id,
            "gridfs_id": str(gridfs_id) if gridfs_id else None,
            "face_results": face_results,
            "timestamp": datetime.datetime.utcnow(),
        }
        self.collection.insert_one(document)
        logger.info(f"Stored metadata for image ID: {image_id} in MongoDB collection")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    data_storage_pb2_grpc.add_DataStorageServiceServicer_to_server(
        DataStorageService(), server
    )
    server.add_insecure_port("[::]:50053")
    logger.info("Data Storage Service starting on port 50053...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
