import logging
import asyncio
import grpc
import face_analysis_pb2_grpc
import image_input_pb2_grpc
import common_pb2
from concurrent import futures
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageInputService(image_input_pb2_grpc.ImageInputServiceServicer):
    def __init__(self):
        # Initialize asyncio queue for requests
        self.request_queue = asyncio.Queue()
        # Dictionary to track request_id to image_id
        self.request_tracker = {}
        # Start the queue processing task
        self._start_queue_processor()

    def _start_queue_processor(self):
        """Start an asyncio task to process the request queue."""
        asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """Process requests from the queue asynchronously."""
        async with grpc.aio.insecure_channel("localhost:50052") as channel:
            stub = face_analysis_pb2_grpc.FaceAnalysisServiceStub(channel)
            while True:
                # Get request from queue
                request_id, request = await self.request_queue.get()
                image_id = request.image_id

                try:
                    # Forward request to FaceAnalysisService
                    response = await stub.ReceiveImage(
                        common_pb2.ImageToFaceServiceRequest(
                            image_data=request.image_data, image_id=image_id
                        )
                    )
                    if response.success:
                        logger.info(f"Successfully processed image ID: {image_id}")
                    else:
                        logger.error(
                            f"Failed to process image ID: {image_id}: {response.error_message}"
                        )
                except grpc.aio.AioRpcError as e:
                    logger.error(f"Error forwarding image ID: {image_id}: {str(e)}")
                finally:
                    # Remove from tracker and mark task as done
                    self.request_tracker.pop(request_id, None)
                    self.request_queue.task_done()

    async def SendImageToFaceService(self, request, context):
        """Handle incoming image requests and add them to the queue."""
        try:
            logger.info(f"Received image with ID: {request.image_id}")
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            # Track request
            self.request_tracker[request_id] = request.image_id
            # Add request to queue
            await self.request_queue.put((request_id, request))
            return common_pb2.DoneFlagToImageInputServiceResponse(
                success=True, error_message=""
            )
        except Exception as e:
            logger.error(f"Error queuing image {request.image_id}: {str(e)}")
            return common_pb2.DoneFlagToImageInputServiceResponse(
                success=False, error_message=str(e)
            )


async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    image_input_pb2_grpc.add_ImageInputServiceServicer_to_server(
        ImageInputService(), server
    )
    server.add_insecure_port("[::]:50051")
    logger.info("Image Input Service starting on port 50051...")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
