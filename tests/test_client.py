import logging
import os
import sys
import asyncio
import grpc

# Add the proto_generated folder to the Python path
sys.path.append(os.path.abspath("./proto_files"))
import image_input_pb2_grpc
import common_pb2
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_image(stub, image_path):
    """Send a single image to the ImageInputService."""
    try:
        # Read image file
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # Send image to Image Input Service
        image_id = os.path.basename(image_path)
        response = await stub.SendImageToFaceService(
            common_pb2.ImageToFaceServiceRequest(
                image_id=image_id,
                image_data=image_data
            )
        )
        logger.info(
            f"Response for {image_id}: Success={response.success}, Error={response.error_message}"
        )
    except Exception as e:
        logger.error(f"Error sending {image_path}: {str(e)}")

async def run():
    """Read all images from a directory and send them simultaneously."""
    image_dir = "./data/"  # Directory containing images
    try:
        # Ensure directory exists
        if not os.path.isdir(image_dir):
            raise FileNotFoundError(f"Image directory not found: {image_dir}")
        
        # Get list of image files (supporting common extensions)
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        image_paths = [
            p for p in Path(image_dir).iterdir()
            if p.is_file() and p.suffix.lower() in image_extensions
        ]
        
        if not image_paths:
            logger.warning(f"No images found in {image_dir}")
            return
        
        logger.info(f"Found {len(image_paths)} images in {image_dir}")
        
        # Create async gRPC channel and stub
        async with grpc.aio.insecure_channel("localhost:50051") as channel:
            stub = image_input_pb2_grpc.ImageInputServiceStub(channel)
            # Send all images concurrently
            tasks = [send_image(stub, str(image_path)) for image_path in image_paths]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    except Exception as e:
        logger.error(f"Client error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run())