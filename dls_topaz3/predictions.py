"""Module containing useful functions for getting predictions on
images from a model and outputting the predictions in a useful format"""

import sys
import logging
import mrcfile
import numpy as np
import keras.models
from dls_topaz3.maps_to_images import slice_map

IMG_DIM = (201, 201)


def predictions_from_images(image_stack: np.ndarray, model_file: str) -> np.ndarray:
    """Get predictions from a model on the image stack provided"""
    try:
        model = keras.models.load_model(model_file)
    except OSError:
        logging.exception(f"Could not find .h5 model at {model_file}")
        raise

    predictions = model.predict(image_stack)

    return predictions


def map_to_images(map_file: str, slices_per_axis: int) -> np.ndarray:
    """Convert a map to an image stack and scale it properly"""
    logging.info(f"Extracting data from {map_file}")
    try:
        with mrcfile.open(map_file) as mrc:
            volume = mrc.data
    except ValueError:
        logging.exception(f"Expected a .map file, not {map}")
        raise
    except FileNotFoundError:
        logging.exception(f"No file found at {map_file}, please provide .map file path")
        raise
    except Exception:
        logging.exception(
            f"Could not get data from {map_file}, please provide .map file path"
        )
        raise

    # Get image slices
    logging.info(f"Slicing map into {slices_per_axis} images on each axis")
    image_stack = slice_map(volume, slices_per_axis)

    # Check dimensions are correct
    assert (
        image_stack.shape[1],
        image_stack.shape[2],
    ) == IMG_DIM, f"Expected image slices of {IMG_DIM}, not {(image_stack.shape[1], image_stack.shape[2])}"

    logging.info(f"Got {image_stack.shape[0]} slices for prediction")

    # Scale slices for input to neural network
    for slice_num in range(image_stack.shape[0]):
        # Get slice
        slice = image_stack[slice_num, :, :]
        # Scale slice
        slice = (slice - slice.min()) / (slice.max() - slice.min())

        # Return to image_stack (in place)
        image_stack[slice_num, :, :] = slice

    # Add a 4th dimension for the benefit of keras and return
    return np.expand_dims(image_stack, 3)


def predictions_from_map(
    map_file: str, slices_per_axis: int, model_file: str
) -> np.ndarray:
    """Get the image slices from a map file and get their predictions"""
    image_stack = map_to_images(map_file, slices_per_axis)

    # Get predictions
    predictions = predictions_from_images(image_stack, model_file)

    return predictions


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print(sys.argv)

    print(predictions_from_map(sys.argv[1], int(sys.argv[2]), sys.argv[3]))
