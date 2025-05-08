import grpc
from concurrent import futures
import common_pb2
import face_analysis_pb2_grpc
import data_storage_pb2_grpc
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceAnalysisService(face_analysis_pb2_grpc.FaceAnalysisServiceServicer):
    def ReceiveImage(self, request, context):
        logger.info(f"Processing image with ID: {request.image_id}")
        
        try:
            # Placeholder: Simulate face analysis
            face_result = common_pb2.FaceResult(
                bbox=[0.1, 0.1, 0.5, 0.5],
                landmark_2d_106=[common_pb2.Point2D(x=0.2, y=0.3)],
                landmark_3d_68=[common_pb2.Point3D(x=0.2, y=0.3, z=0.1)],
                age=30,
                gender="male"
            )
            
            # Send result to Data Storage Service (C)
            with grpc.insecure_channel('localhost:50053') as channel:
                stub = data_storage_pb2_grpc.DataStorageServiceStub(channel)
                response = stub.StoreFaceResult(common_pb2.FaceResultRequest(
                    image_id=request.image_id,
                    image_data=request.image_data,
                    face_results=[face_result]
                ))
            
            if response.success:
                logger.info(f"Successfully stored result for image ID: {request.image_id}")
                return common_pb2.DoneFlagToImageInputServiceResponse(
                    success=True,
                    error_message=""
                )
            else:
                logger.error(f"Failed to store result for image ID: {request.image_id}: {response.error_message}")
                return common_pb2.DoneFlagToImageInputServiceResponse(
                    success=False,
                    error_message=response.error_message
                )
        except Exception as e:
            logger.error(f"Error processing image {request.image_id}: {str(e)}")
            return common_pb2.DoneFlagToImageInputServiceResponse(
                success=False,
                error_message=str(e)
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    face_analysis_pb2_grpc.add_FaceAnalysisServiceServicer_to_server(FaceAnalysisService(), server)
    server.add_insecure_port('[::]:50052')
    logger.info("Face Analysis Service starting on port 50052...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()