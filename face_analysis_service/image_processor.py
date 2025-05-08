import insightface
import cv2
import logging
import numpy as np
import time
import grpc
import common_pb2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Performs face analysis on images using the InsightFace library.
    """

    def __init__(self):
        """
        Initializes the ImageProcessor with a pre-trained InsightFace model.
        The model is configured for buffalo_l and prepared for execution.
        """
        self.model = insightface.app.FaceAnalysis(name="buffalo_l")
        self.model.prepare(ctx_id=0, det_size=(640, 640))

    def process(self, image_data, decode_image_flag=False):
        """
        Runs face analysis on the input image data.

        Args:
            image_data (bytes or numpy.ndarray): The image data. If decode_image_flag is True,
                image_data should be bytes; otherwise, it should be a cv2-compatible image (numpy.ndarray).
            decode_image_flag (bool): A flag indicating whether the image_data needs to be decoded from bytes.

        Returns:
            list: A list of face detections, each containing bounding box and landmark information. Returns None if decoding fails
        """
        if decode_image_flag:
            # Decode byte image to cv2 format
            image = self.decode_byte_image(image_data)
            if image is None:
                return None
        else:
            image = image_data  # Assume image_data is already a decoded image
        # Process image
        faces = self.model.get(image)
        converted_results = self.convert_results(faces)
        return faces

    def decode_byte_image(self, image_data):
        """
        Decodes the byte image data into a cv2 image.

        Args:
            image_data (bytes): The image data in bytes format.

        Returns:
            numpy.ndarray: The decoded cv2 image as a numpy array, or None if decoding fails.

        Raises:
            grpc.RpcError: If the image format is invalid.
        """
        start_time = time.time()
        try:
            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.error("Invalid image format")
                return None
        except Exception as e:
            logger.error(f"An error occurred during image decoding: {e}")
            return None
        logger.info(f"Image decoding took {time.time() - start_time:.3f} seconds")
        return img

    def convert_results(self, faces):
        """
        Convert face analysis results to a list of dictionaries.

        Args:
            faces (list): A list of face detections from the InsightFace model.

        Returns:
            list: A list of dictionaries, where each dictionary represents a face and contains
                  bounding box, landmark, age, and gender information.
        """
        results = []
        for face in faces:
            results.append(
                {
                    "bbox": [float(x) for x in face.bbox],
                    "landmark_2d_106": [
                        [float(p[0]), float(p[1])] for p in face.landmark_2d_106
                    ],
                    "landmark_3d_68": [
                        [float(p[0]), float(p[1]), float(p[2])]
                        for p in face.landmark_3d_68
                    ],
                    "age": int(face.age),
                    "gender": "female" if face.gender == 0 else "male",
                }
            )
        return results


if __name__ == "__main__":
    # Initialize the ImageProcessor
    processor = ImageProcessor()

    # Load a sample image (replace with your image path)
    image_path = "./data/MultipleFaces.jpg"
    image = cv2.imread(image_path)

    if image is None:
        print(f"Error: Unable to load image at {image_path}")
    else:
        # Process and convert results
        raw_results = processor.process(image)
        results = processor.convert_results(raw_results)

        # Print the results
        print("Face Analysis Results:")
        for result in results:
            print(result)
