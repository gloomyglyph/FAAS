import grpc
from concurrent import futures
from image_processor import ImageProcessor
import common_pb2
import face_analysis_pb2_grpc
import data_storage_pb2_grpc
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaceAnalysisService(face_analysis_pb2_grpc.FaceAnalysisServiceServicer):
    def __init__(self):
        self.img_processor = ImageProcessor()

    def convert_to_face_results(self, face_dicts):
        """Convert a list of face detection dictionaries to common_pb2.FaceResult objects."""
        face_results = []
        for face_dict in face_dicts:
            face_result = common_pb2.FaceResult(
                bbox=face_dict["bbox"],
                landmark_2d_106=[
                    common_pb2.Point2D(x=point[0], y=point[1])
                    for point in face_dict["landmark_2d_106"]
                ],
                landmark_3d_68=[
                    common_pb2.Point3D(x=point[0], y=point[1], z=point[2])
                    for point in face_dict["landmark_3d_68"]
                ],
                age=face_dict["age"],
                gender=face_dict["gender"],
            )
            face_results.append(face_result)
        return face_results

    def ReceiveImage(self, request, context):
        logger.info(f"Processing image with ID: {request.image_id}")

        try:
            # Process image using InsightFace
            raw_faces = self.img_processor.process(
                request.image_data, decode_image_flag=True
            )
            if raw_faces is None:
                raise ValueError(
                    "Failed to process image: No faces detected or invalid image"
                )

            # Convert raw face detections to list of dictionaries
            face_dicts = self.img_processor.convert_results(raw_faces)

            # Convert dictionaries to common_pb2.FaceResult objects
            face_results = self.convert_to_face_results(face_dicts)

            # Send result to Data Storage Service (C)
            with grpc.insecure_channel("localhost:50053") as channel:
                stub = data_storage_pb2_grpc.DataStorageServiceStub(channel)
                response = stub.StoreFaceResult(
                    common_pb2.FaceResultRequest(
                        image_id=request.image_id,
                        image_data=request.image_data,
                        face_results=face_results,
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


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    face_analysis_pb2_grpc.add_FaceAnalysisServiceServicer_to_server(
        FaceAnalysisService(), server
    )
    server.add_insecure_port("[::]:50052")
    logger.info("Face Analysis Service starting on port 50052...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
