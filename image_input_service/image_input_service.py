import logging
import asyncio
import grpc
import face_analysis_pb2_grpc
import agender_analysis_pb2_grpc
import image_input_pb2_grpc
import common_pb2
from concurrent import futures
import uuid
import argparse
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageInputService(image_input_pb2_grpc.ImageInputServiceServicer):
    def __init__(self, face_analysis_address, agender_analysis_address):
        self.face_analysis_address = face_analysis_address
        self.agender_analysis_address = agender_analysis_address
        self.request_queue = asyncio.Queue()
        self.request_tracker = {}
        self._start_queue_processor()

    def _start_queue_processor(self):
        """Start an asyncio task to process the request queue."""
        asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """Process requests from the queue asynchronously."""
        async with grpc.aio.insecure_channel(self.face_analysis_address) as face_channel, \
                   grpc.aio.insecure_channel(self.agender_analysis_address) as agender_channel:
            face_stub = face_analysis_pb2_grpc.FaceAnalysisServiceStub(face_channel)
            agender_stub = agender_analysis_pb2_grpc.AgenderAnalysisServiceStub(agender_channel)
            while True:
                request_id, request = await self.request_queue.get()
                image_id = request.image_id

                try:
                    # Concurrently forward to both services
                    face_task = face_stub.ReceiveImage(
                        common_pb2.ImageToFaceServiceRequest(image_data=request.image_data, image_id=image_id)
                    )
                    agender_task = agender_stub.ReceiveImage(
                        common_pb2.ImageToAgenderServiceRequest(image_data=request.image_data, image_id=image_id)
                    )
                    face_response, agender_response = await asyncio.gather(face_task, agender_task)

                    # Check responses
                    if not face_response.success:
                        logger.error(f"Face analysis failed for {image_id}: {face_response.error_message}")
                    if not agender_response.success:
                        logger.error(f"Agender analysis failed for {image_id}: {agender_response.error_message}")
                    if face_response.success and agender_response.success:
                        logger.info(f"Successfully processed image ID: {image_id}")
                except grpc.aio.AioRpcError as e:
                    logger.error(f"Error forwarding image ID: {image_id}: {str(e)}")
                finally:
                    self.request_tracker.pop(request_id, None)
                    self.request_queue.task_done()

    async def SendImageToFaceService(self, request, context):
        """Handle incoming image requests for face analysis."""
        try:
            logger.info(f"Received image with ID: {request.image_id} for face analysis")
            request_id = str(uuid.uuid4())
            self.request_tracker[request_id] = request.image_id
            await self.request_queue.put((request_id, request))
            return common_pb2.DoneFlagToImageInputServiceResponse(success=True, error_message="")
        except Exception as e:
            logger.error(f"Error queuing image {request.image_id}: {str(e)}")
            return common_pb2.DoneFlagToImageInputServiceResponse(success=False, error_message=str(e))

    async def SendImageToAgenderService(self, request, context):
        """Handle incoming image requests for agender analysis (already queued via SendImageToFaceService)."""
        try:
            logger.info(f"Received image with ID: {request.image_id} for agender analysis")
            # Since the queue processes both, we can reuse the same queuing logic
            request_id = str(uuid.uuid4())
            self.request_tracker[request_id] = request.image_id
            await self.request_queue.put((request_id, request))
            return common_pb2.DoneFlagToImageInputServiceResponse(success=True, error_message="")
        except Exception as e:
            logger.error(f"Error queuing image {request.image_id}: {str(e)}")
            return common_pb2.DoneFlagToImageInputServiceResponse(success=False, error_message=str(e))

async def serve(face_analysis_address: str, agender_analysis_address: str, image_input_port: str):
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    image_input_pb2_grpc.add_ImageInputServiceServicer_to_server(
        ImageInputService(face_analysis_address, agender_analysis_address), server
    )
    bind_address = f"[::]:{image_input_port}"
    server.add_insecure_port(bind_address)
    logger.info(f"Image Input Service starting on port {image_input_port}...")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Image Input Service")
    parser.add_argument(
        "--face_analysis_address",
        type=str,
        default=os.getenv("FACE_ANALYSIS_ADDRESS", "localhost:50052"),
        help="Address of the Face Analysis Service (default: localhost:50052)",
    )
    parser.add_argument(
        "--agender_analysis_address",
        type=str,
        default=os.getenv("AGENDER_ANALYSIS_ADDRESS", "localhost:50054"),
        help="Address of the Agender Analysis Service (default: localhost:50054)",
    )
    parser.add_argument(
        "--image_input_port",
        type=str,
        default=os.getenv("GRPC_PORT", "50051"),
        help="Port to run the Image Input Service on (default: 50051)",
    )
    args = parser.parse_args()

    asyncio.run(serve(args.face_analysis_address, args.agender_analysis_address, args.image_input_port))