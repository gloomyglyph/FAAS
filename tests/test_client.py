import logging
import os
import sys
# Add the proto_generated folder to the Python path
sys.path.append(os.path.abspath("./proto_files"))
import grpc
import image_input_pb2_grpc
import common_pb2



# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This function sends dummy data to the image_input_service
def run_dummy():
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

# This function sends real image data to the image_input_service
def run():
    image_path = "./data/SingleFace.jpg"  # Adjust path if needed
    try:
        # Read image file
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # Send image to Image Input Service
        with grpc.insecure_channel("localhost:50051") as channel:
            stub = image_input_pb2_grpc.ImageInputServiceStub(channel)
            response = stub.SendImageToFaceService(
                common_pb2.ImageToFaceServiceRequest(
                    image_id=os.path.basename(image_path),
                    image_data=image_data
                )
            )
            logger.info(
                f"Response: Success={response.success}, Error={response.error_message}"
            )
    except Exception as e:
        logger.error(f"Client error: {str(e)}")

if __name__ == "__main__":
    #run_dummy()
    run()