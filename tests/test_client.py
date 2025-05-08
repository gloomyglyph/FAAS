import logging

import os
import sys

# Add the proto_generated folder to the Python path
sys.path.append(os.path.abspath("./proto_files"))
import image_input_pb2_grpc
import common_pb2
import grpc

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run():
    try:
        with grpc.insecure_channel("localhost:50051") as channel:
            stub = image_input_pb2_grpc.ImageInputServiceStub(channel)
            response = stub.SendImageToFaceService(
                common_pb2.ImageToFaceServiceRequest(
                    image_id="test_image_001", image_data=b"dummy_image_data"
                )
            )
            logger.info(
                f"Response: Success={response.success}, Error={response.error_message}"
            )
    except Exception as e:
        logger.error(f"Client error: {str(e)}")


if __name__ == "__main__":
    run()
