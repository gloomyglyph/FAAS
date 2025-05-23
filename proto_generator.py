import os
import shutil
import tempfile
import logging
from grpc_tools import protoc

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_protos():
    """Generate Protobuf files and copy them to microservice proto_files directories."""
    # Define paths
    base_dir = os.path.abspath(os.path.dirname(__file__))
    proto_dir = os.path.join(base_dir, "proto_files")
    temp_dir = None

    # Microservice proto_files directories
    microservices = [
        os.path.join(base_dir, "data_storage_service"),
        os.path.join(base_dir, "face_analysis_service"),
        os.path.join(base_dir, "agender_analysis_service"),
        os.path.join(base_dir, "image_input_service"),
        os.path.join(base_dir, "tests"),
    ]

    # Proto files to compile
    proto_files = [
        "common.proto",
        "data_storage.proto",
        "face_analysis.proto",
        "agender_analysis.proto",
        "image_input.proto",
    ]

    try:
        # Create temporary directory for generated files
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")

        # Compile proto files
        for proto_file in proto_files:
            proto_path = os.path.join(proto_dir, proto_file)
            if not os.path.exists(proto_path):
                raise FileNotFoundError(f"Proto file not found: {proto_path}")

            logger.info(f"Compiling {proto_file}...")
            result = protoc.main(
                [
                    "grpc_tools.protoc",
                    f"-I{proto_dir}",
                    f"--python_out={temp_dir}",
                    f"--grpc_python_out={temp_dir}",
                    proto_path,
                ]
            )
            if result != 0:
                raise RuntimeError(f"Failed to compile {proto_file}")

        # List of generated files
        generated_files = [
            f for f in os.listdir(temp_dir) if f.endswith(("_pb2.py", "_pb2_grpc.py"))
        ]
        logger.info(f"Generated files: {generated_files}")

        # Delete old _pb2.py and _pb2_grpc.py files and copy new ones
        for microservice_dir in microservices:
            if not os.path.exists(microservice_dir):
                os.makedirs(microservice_dir)
                logger.info(f"Created directory: {microservice_dir}")

            # Delete old generated proto files
            for file_name in os.listdir(microservice_dir):
                if file_name.endswith(("_pb2.py", "_pb2_grpc.py")):
                    file_path = os.path.join(microservice_dir, file_name)
                    os.remove(file_path)
                    logger.info(f"Deleted old file: {file_path}")

            # Copy new files
            for gen_file in generated_files:
                src_path = os.path.join(temp_dir, gen_file)
                dst_path = os.path.join(microservice_dir, gen_file)
                shutil.copy2(src_path, dst_path)
                logger.info(f"Copied {gen_file} to {microservice_dir}")

    except Exception as e:
        logger.error(f"Error generating or copying proto files: {str(e)}")
        raise

    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Removed temporary directory: {temp_dir}")


if __name__ == "__main__":
    generate_protos()
