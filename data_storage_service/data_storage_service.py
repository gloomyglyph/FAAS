import logging
import data_storage_pb2_grpc
import common_pb2
import grpc
from concurrent import futures
import os
import sys


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataStorageService(data_storage_pb2_grpc.DataStorageServiceServicer):
    def __init__(self):
        # In-memory storage
        self.storage = {}

    def StoreFaceResult(self, request, context):
        logger.info(f"Storing face result for image ID: {request.image_id}")

        try:
            self.storage[request.image_id] = request.face_results
            self.store_data()

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

    def store_data(self):
        pass


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
