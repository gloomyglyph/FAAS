import grpc
import argparse
from concurrent import futures
from image_processor import ImageProcessor
import common_pb2
import agender_analysis_pb2_grpc
import data_storage_pb2_grpc
import logging
import redis
import hashlib
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def compute_image_hash(image_data):
    """Compute SHA-256 hash of the image data."""
    return hashlib.sha256(image_data).hexdigest()


class AgenderAnalysisService(agender_analysis_pb2_grpc.AgenderAnalysisServiceServicer):
    def __init__(self, storage_address, redis_host, redis_port):
        self.img_processor = ImageProcessor()
        self.storage_address = storage_address
        # Initialize Redis client
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, db=0, decode_responses=True
        )
        try:
            self.redis_client.ping()
            logger.info("Connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def check_redis_for_hash(self, image_hash):
        """Check if the 'agender_results' field exists in the Redis hash for the image."""
        try:
            return self.redis_client.hexists(image_hash, "agender_results")
        except redis.RedisError as e:
            logger.error(
                f"Error checking Redis for 'agender_results' in hash {image_hash}: {str(e)}"
            )
            return False

    def convert_to_agender_results(self, agender_dicts):
        """Convert a list of agender detection dictionaries to common_pb2.AgenderResult objects."""
        agender_results = []
        for agender_dict in agender_dicts:
            agender_result = common_pb2.AgenderResult(
                age=agender_dict["age"],
                gender=agender_dict["gender"],
            )
            agender_results.append(agender_result)
        return agender_results

    def ReceiveImage(self, request, context):
        logger.info(f"Processing image with ID: {request.image_id}")

        try:
            # Compute image hash
            image_hash = compute_image_hash(request.image_data)
            logger.info(f"Computed image hash: {image_hash}")

            # Check Redis for existing agender results
            if self.check_redis_for_hash(image_hash):
                logger.info(
                    f"Image ID: {request.image_id} already processed (agender_results found in Redis for hash {image_hash})"
                )
                return common_pb2.DoneFlagToImageInputServiceResponse(
                    success=True, error_message=""
                )

            # Process image using InsightAgender
            raw_agenders = self.img_processor.process(
                request.image_data, decode_image_flag=True
            )
            if raw_agenders is None:
                raise ValueError(
                    "Failed to process image: No agenders detected or invalid image"
                )

            # Convert raw agender detections to list of dictionaries
            agender_dicts = self.img_processor.convert_results(raw_agenders)

            # Convert dictionaries to common_pb2.AgenderResult objects
            agender_results = self.convert_to_agender_results(agender_dicts)

            # Send result to Data Storage Service
            with grpc.insecure_channel(self.storage_address) as channel:
                stub = data_storage_pb2_grpc.DataStorageServiceStub(channel)
                response = stub.StoreAgenderResult(
                    common_pb2.AgenderResultRequest(
                        image_id=request.image_id,
                        image_data=request.image_data,
                        agender_results=agender_results,
                    )
                )

            if response.success:
                logger.info(
                    f"Successfully stored result for image ID: {request.image_id}"
                )
                return common_pb2.DoneFlagToImageInputServiceResponse(
                    success=True, error_message=""
                )
            else:
                logger.error(
                    f"Failed to store result for image ID: {request.image_id}: {response.error_message}"
                )
                return common_pb2.DoneFlagToImageInputServiceResponse(
                    success=False, error_message=response.error_message
                )
        except Exception as e:
            logger.error(f"Error processing image {request.image_id}: {str(e)}")
            return common_pb2.DoneFlagToImageInputServiceResponse(
                success=False, error_message=str(e)
            )


def serve(bind_address, storage_address, redis_host, redis_port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agender_analysis_pb2_grpc.add_AgenderAnalysisServiceServicer_to_server(
        AgenderAnalysisService(storage_address, redis_host, redis_port), server
    )
    server.add_insecure_port(bind_address)
    logger.info(f"Agender Analysis Service starting on {bind_address}...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Agender Analysis Service")
    parser.add_argument(
        "--address",
        type=str,
        default=os.getenv("AGENDER_ANALYSIS_ADDRESS", "localhost:50054"),
        help="IP address and port to bind the server to (default: [::]:50054)",
    )
    parser.add_argument(
        "--storage_address",
        type=str,
        default=os.getenv("GRPC_PORT_DATA_STORAGE", "localhost:50053"),
        help="Address of the Data Storage Service (default: localhost:50053)",
    )
    parser.add_argument(
        "--redis_host",
        type=str,
        default="localhost",
        help="Redis server host (default: localhost)",
    )
    parser.add_argument(
        "--redis_port",
        type=int,
        default=os.getenv("REDIS_PORT", "6379"),
        help="Redis server port (default: 6379)",
    )
    args = parser.parse_args()
    serve(args.address, args.storage_address, args.redis_host, args.redis_port)
