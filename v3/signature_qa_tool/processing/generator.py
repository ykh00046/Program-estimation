"""
Signature generation logic for the QA Tool.

This module encapsulates the signature synthesis and compositing workflow,
leveraging the main application's ImageProcessor.
"""
from PIL import Image
import os
from datetime import datetime


class SignatureGenerator:
    """Generates composite images with synthesized signatures."""

    def __init__(self, qa_config):
        """
        Initialize the generator with configuration.

        Args:
            qa_config: QAToolConfig instance
        """
        self.qa_config = qa_config
        self.base_document_path = qa_config.base_document_path

        # Import ImageProcessor (path already added by config.py)
        from models.image_processor import ImageProcessor
        self.ImageProcessor = ImageProcessor

    def generate_composite_image(self, worker_name, params=None):
        """
        Generate a single composite image with a synthesized signature.

        Args:
            worker_name: Name of the worker for signature generation
            params: Optional dict of ImageProcessor parameters to override

        Returns:
            PIL.Image: Composite image with signature overlay
        """
        # Get base configuration
        sig_config = self.qa_config.get_signature_config().copy()

        # Override with custom parameters if provided
        if params:
            sig_config.update(params)

        # Create ImageProcessor instance
        processor = self.ImageProcessor(
            resources_path=self.qa_config.get_resources_path(),
            config=sig_config
        )

        # Create a temporary output path
        temp_output = os.path.join(
            self.qa_config.output_directory,
            f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
        )

        # Generate signed image
        success, message = processor.create_signed_image(
            base_image_path=self.base_document_path,
            output_path=temp_output,
            selected_worker=worker_name
        )

        if success and os.path.exists(temp_output):
            # Load and return the image
            composite_image = Image.open(temp_output).convert("RGB")
            # Clean up temp file
            try:
                os.remove(temp_output)
            except (OSError, IOError):
                pass
            return composite_image
        else:
            # Return a blank image if generation failed
            return Image.new("RGB", (800, 600), color="white")

    def generate_batch(self, worker_name, num_variations, params=None):
        """
        Generate multiple variations of composite images.

        Args:
            worker_name: Name of the worker for signature generation
            num_variations: Number of variations to generate
            params: Optional dict of ImageProcessor parameters to override

        Returns:
            list[PIL.Image]: List of composite images
        """
        images = []
        for i in range(num_variations):
            composite = self.generate_composite_image(worker_name, params)
            images.append(composite)

        return images

    def save_composite(self, image, worker_name, params_summary=""):
        """
        Save a composite image to the output directory.

        Args:
            image: PIL.Image to save
            worker_name: Worker name for filename
            params_summary: Optional parameter summary for filename

        Returns:
            str: Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{worker_name}_{params_summary}_{timestamp}.png" if params_summary else f"{worker_name}_{timestamp}.png"
        output_path = os.path.join(self.qa_config.output_directory, filename)

        image.save(output_path, dpi=(300, 300))
        return output_path
