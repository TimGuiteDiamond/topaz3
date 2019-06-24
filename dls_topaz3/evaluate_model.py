"""Load a model and evaluate its performance against an unknown test set"""
import sys
import logging
import glob
import numpy as np
import sqlite3
import pandas
import re
import os

# encode text category labels
from pathlib import Path
from keras.preprocessing.image import ImageDataGenerator
import keras.models
from sklearn.metrics import classification_report, confusion_matrix

IMG_DIM = (201, 201)


def evaluate(
    model_file: str,
    test_dir: str,
    database_file: str,
    output_dir: str,
    slices_per_structure: int = 60,
):
    # Load model
    try:
        model = keras.models.load_model(model_file)
    except Exception:
        logging.error(f"Failed to load model from {model_file}")
        raise

    logging.info(f"Model loaded from {model_file}")

    # Get test files prepared
    # Load files
    try:
        train_files = glob.glob(f"{test_dir}/*")
        logging.info(f"Found {len(train_files)} files for training")
        assert len(train_files) > 0, f"Could not find files at {test_dir}"
        assert (
            len(train_files) % slices_per_structure == 0
        ), f"Number of test files is not an exact multiple of slices per structure"
    except AssertionError as e:
        logging.error(e)
        raise
    except Exception as e:
        logging.error(e)
        raise

    try:
        conn = sqlite3.connect(database_file)
    except Exception:
        logging.error(f"Could not connect to database at {database_file}")
        raise

    # Read table into pandas dataframe
    data = pandas.read_sql(f"SELECT * FROM ai_labels", conn)
    data_indexed = data.set_index("Name")

    names = [re.findall("(.*)(?=_[0-9]+)", Path(file).stem)[0] for file in train_files]
    train_labels = [data_indexed.at[name, "Label"] for name in names]

    # Create training dataframe
    testing_dataframe = pandas.DataFrame({"Files": train_files, "Labels": train_labels})

    test_datagen = ImageDataGenerator(rescale=1.0 / 255)

    test_batch_size = slices_per_structure

    test_generator = test_datagen.flow_from_dataframe(
        testing_dataframe,
        x_col="Files",
        y_col="Labels",
        target_size=IMG_DIM,
        class_mode=None,
        color_mode="grayscale",
        batch_size=test_batch_size,
        shuffle=False,
    )

    logging.info("Getting predictions")

    predictions = model.predict_generator(
        test_generator, steps=int(len(testing_dataframe["Files"]) / test_batch_size)
    )

    # Per image analysis
    predictions_1 = [x for x in predictions if x[1] > x[0]]
    predictions_0 = [x for x in predictions if x[1] < x[0]]
    logging.info(f"Predicted good value {len(predictions_1)} times")
    logging.info(f"Predicted bad value {len(predictions_0)} times")

    predictions_decoded = [int(pred[1] > pred[0]) for pred in predictions]

    # Create an output directory if it doesn't exist
    output_dir_path = Path(output_dir)
    if not output_dir_path.exists():
        # Make one
        try:
            os.mkdir(output_dir_path)
            logging.info(f"Created new directory in {output_dir_path}")
        except Exception as e:
            logging.error(
                f"Could not create directory at {output_dir_path}.\n"
                f"Please check permissions and location."
            )
            logging.error(e)
            raise

    # Save raw predictions
    raw_dataframe = pandas.DataFrame(
        {
            "File": testing_dataframe["Files"],
            "0": predictions[:, 0],
            "1": predictions[:, 1],
            "True Score": train_labels,
        }
    )
    raw_dataframe.set_index("File", inplace=True)
    raw_dataframe.to_csv(output_dir_path / "raw_predictions.csv")

    logging.info("Per image analysis:")
    per_image_class = classification_report(
        predictions_decoded, testing_dataframe["Labels"], output_dict=True
    )
    per_image_class_frame = pandas.DataFrame(per_image_class).transpose()
    per_image_conf = confusion_matrix(predictions_decoded, testing_dataframe["Labels"])
    per_image_conff_frame = pandas.DataFrame(per_image_conf)
    logging.info(per_image_class)
    logging.info(per_image_conf)
    # Save reports to csv
    per_image_class_frame.to_csv(output_dir_path / "per_image_class.csv")
    per_image_conff_frame.to_csv(output_dir_path / "per_image_conf.csv")
    logging.info("Per image analysis complete")

    # Per structure analysis
    logging.info("Per structure analysis: ")
    # Generate a table of average 0 and 1 scores across the structure
    predictions_structure_avg = np.array(
        [
            (
                np.mean(
                    predictions[
                        slices_per_structure * i : slices_per_structure * i
                        + slices_per_structure,
                        0,
                    ]
                ),
                np.mean(
                    predictions[
                        slices_per_structure * i : slices_per_structure * i
                        + slices_per_structure,
                        1,
                    ]
                ),
            )
            for i in range(int(len(predictions) / slices_per_structure))
        ]
    )
    # Save average predictions
    average_dataframe = pandas.DataFrame(
        {
            "Structure": [
                names[slices_per_structure * i]
                for i in range(int(len(names) / slices_per_structure))
            ],
            "0": predictions_structure_avg[:, 0],
            "1": predictions_structure_avg[:, 1],
            "True Score": [
                train_labels[slices_per_structure * i]
                for i in range(int(len(names) / slices_per_structure))
            ],
        }
    )
    average_dataframe.set_index("Structure", inplace=True)
    average_dataframe.to_csv(output_dir_path / "averaged_predictions.csv")

    # Generate a table of the percentage of 0 and 1 classifications across the structure
    predictions_by_result = np.array(
        [(int(pred[0] > pred[1]), int(pred[1] > pred[0])) for pred in predictions]
    )
    predictions_structure_count = np.array(
        [
            (
                np.sum(
                    predictions_by_result[
                        slices_per_structure * i : slices_per_structure * i
                        + slices_per_structure,
                        0,
                    ]
                )
                / slices_per_structure,
                np.sum(
                    predictions_by_result[
                        slices_per_structure * i : slices_per_structure * i
                        + slices_per_structure,
                        1,
                    ]
                )
                / slices_per_structure,
            )
            for i in range(int(len(predictions) / slices_per_structure))
        ]
    )
    # Save counted predictions
    counted_dataframe = pandas.DataFrame(
        {
            "Structure": [
                names[slices_per_structure * i]
                for i in range(int(len(names) / slices_per_structure))
            ],
            "0": predictions_structure_count[:, 0],
            "1": predictions_structure_count[:, 1],
            "True Score": [
                train_labels[slices_per_structure * i]
                for i in range(int(len(names) / slices_per_structure))
            ],
        }
    )
    counted_dataframe.set_index("Structure", inplace=True)
    counted_dataframe.to_csv(output_dir_path / "counted_predictions.csv")

    predictions_struct_avg_flat = [
        int(pred > 0.5) for pred in predictions_structure_avg[:, 1]
    ]
    predictions_struct_count_flat = [
        int(pred > 0.5) for pred in predictions_structure_count[:, 1]
    ]

    labels = testing_dataframe["Labels"]
    testing_info_by_structure = [
        labels[slices_per_structure * i]
        for i in range(int(len(labels) / slices_per_structure))
    ]

    logging.info("Classification by structure using average:")
    structure_avg_class = classification_report(
        predictions_struct_avg_flat, testing_info_by_structure, output_dict=True
    )
    structure_avg_class_frame = pandas.DataFrame(structure_avg_class).transpose()
    structure_avg_conf = confusion_matrix(
        predictions_struct_avg_flat, testing_info_by_structure
    )
    structure_avg_conf_frame = pandas.DataFrame(structure_avg_conf)
    logging.info(structure_avg_class)
    logging.info(structure_avg_conf)
    # Save to file
    structure_avg_class_frame.to_csv(output_dir_path / "average_class.csv")
    structure_avg_conf_frame.to_csv(output_dir_path / "average_conf.csv")

    logging.info("Classification by structure using count:")
    structure_count_class = classification_report(
        predictions_struct_count_flat, testing_info_by_structure, output_dict=True
    )
    structure_count_class_frame = pandas.DataFrame(structure_count_class).transpose()
    structure_count_conf = confusion_matrix(
        predictions_struct_count_flat, testing_info_by_structure
    )
    structure_count_conf_frame = pandas.DataFrame(structure_count_conf)
    logging.info(structure_count_class)
    logging.info(structure_count_conf)
    # Save to file
    structure_count_class_frame.to_csv(output_dir_path / "count_class.csv")
    structure_count_conf_frame.to_csv(output_dir_path / "count_conf.csv")

    logging.info("Evaluations complete.")

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    evaluate(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])