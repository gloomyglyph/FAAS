import logging
import face_analysis_pb2_grpc
import image_input_pb2_grpc
import common_pb2
import grpc
from concurrent import futures
import os
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageInputService(image_input_pb2_grpc.ImageInputServiceServicer):
    def SendImageToFaceService(self, request, context):
        logger.info(f"Received image with ID: {request.image_id}")

        try:
            # Forward image to Face Analysis Service (B)
            with grpc.insecure_channel("localhost:50052") as channel:
                stub = face_analysis_pb2_grpc.FaceAnalysisServiceStub(channel)
                response = stub.ReceiveImage(
                    common_pb2.ImageToFaceServiceRequest(
                        image_data=request.image_data, image_id=request.image_id
                    )
                )
            return common_pb2.DoneFlagToImageInputServiceResponse(
                success=response.success, error_message=response.error_message
            )
        except Exception as e:
            logger.error(f"Error forwarding image {request.image_id}: {str(e)}")
            return common_pb2.DoneFlagToImageInputServiceResponse(
                success=False, error_message=str(e)
            )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    image_input_pb2_grpc.add_ImageInputServiceServicer_to_server(
        ImageInputService(), server
    )
    server.add_insecure_port("[::]:50051")
    logger.info("Image Input Service starting on port 50051...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
