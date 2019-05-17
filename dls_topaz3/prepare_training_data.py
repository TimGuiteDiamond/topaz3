import logging

from pathlib import Path
from mtz_info import mtz_get_cell
from space_group import textfile_find_space_group, mtz_find_space_group
from conversions import phase_to_map
from delete_temp_files import delete_temp_files

def prepare_training_data(phase_directory,
                          output_directory,
                          cell_info_directory,
                          cell_info_path,
                          space_group_directory,
                          space_group_path,
                          xyz_limits,
                          delete_temp=True):
    """Convert both the original and inverse hands of a structure into a regular map file based on information
    about the cell info and space group and the xyz dimensions. Return True if no exceptions"""

    logging.info("Preparing training data")

    # Check all directories exist
    try:
        phase_dir = Path(phase_directory)
        assert phase_dir.exists()
    except:
        logging.error(f"Could not find phase directory at {phase_directory}")
        raise

    try:
        cell_info_dir = Path(cell_info_directory)
        assert cell_info_dir.exists()
    except:
        logging.error(f"Could not find cell info directory at {cell_info_directory}")
        raise

    try:
        space_group_dir = Path(space_group_directory)
        assert space_group_dir.exists()
    except:
        logging.error(f"Could not find space group directory at {space_group_directory}")
        raise

    try:
        output_dir = Path(output_directory)
        assert output_dir.exists()
    except:
        logging.error(f"Could not find output directory at {output_directory}")
        raise

    # Get lists of child directories
    phase_structs = [struct.stem for struct in phase_dir.iterdir()]
    cell_info_structs = [struct.stem for struct in cell_info_dir.iterdir()]
    space_group_structs = [struct.stem for struct in space_group_dir.iterdir()]

    assert phase_structs == cell_info_structs == space_group_structs, "Same structures not found in all given directories"
    phase_structs = sorted(phase_structs)
    logging.debug(f"Following structures found to transform: {phase_structs}")

    # Get cell info and space group
    cell_info_dict = {}
    space_group_dict = {}

    #Set up function to get space group depending on suffix
    if Path(space_group_path).suffix == ".mtz":
        find_space_group = mtz_find_space_group
    else:
        find_space_group = textfile_find_space_group

    for struct in phase_structs:
        logging.info(f"Collecting info from {struct}, {phase_structs.index(struct)+1}/{len(phase_structs)}")
        try:
            cell_info_file = cell_info_dir / Path(struct) / Path(cell_info_path)
            assert cell_info_file.exists()
        except:
            logging.error(f"Could not find cell info file at {cell_info_file}")
            raise

        try:
            cell_info_dict[struct] = mtz_get_cell(cell_info_file)
        except:
            logging.error(f"Could not get cell info from {cell_info_file}")
            raise

        try:
            space_group_file = space_group_dir / Path(struct) / Path(space_group_path)
            assert space_group_file.exists()
        except:
            logging.error(f"Could not find space group file at {space_group_file}")
            raise

        try:
            space_group_dict[struct] = find_space_group(space_group_file)
        except:
            logging.error(f"Could not get space group from {space_group_file}")
            raise

    logging.info("Collected cell info and space group")

    # Begin transformation
    for struct in phase_structs:
        logging.info(f"Converting {struct}, {phase_structs.index(struct)+1}/{len(phase_structs)}")
        # Create original and inverse hands
        try:
            original_hand = Path(phase_dir / struct / space_group_dict[struct] / (struct + ".phs"))
            inverse_hand = Path(phase_dir / struct / space_group_dict[struct] / (struct + "_i.phs"))

            #Catch a weird situation where some space groups RXX can also be called RXX:H
            if (space_group_dict[struct][0] == "R") and (original_hand.exists() == False):
                original_hand = Path(phase_dir / struct / (space_group_dict[struct] + ":H") / (struct + ".phs"))
                inverse_hand = Path(phase_dir / struct / (space_group_dict[struct] + ":H") / (struct + "_i.phs"))

            assert original_hand.exists(), f"Could not find original hand for {struct}"
            assert inverse_hand.exists(), f"Could not find inverse hand for {struct}"
        except:
            logging.error(f"Could not find phase files of {struct} in space group {space_group_dict[struct]}")
            raise

        # Convert original
        try:
            phase_to_map(original_hand,
                         output_dir / (struct + ".map"),
                         cell_info_dict[struct],
                         space_group_dict[struct],
                         xyz_limits)
        except:
            logging.error(f"Could not convert original hand for {struct}")
            raise

        # Convert inverse
        try:
            phase_to_map(inverse_hand,
                         output_dir / (struct + "_i.map"),
                         cell_info_dict[struct],
                         space_group_dict[struct],
                         xyz_limits)
        except:
            logging.error(f"Could not convert original hand for {struct}")
            raise

        logging.info(f"Successfully converted {struct}")

    logging.info("Finished conversions")

    # Delete temporary files if requested
    if delete_temp == True:
        delete_temp_files(output_directory)
        logging.info("Deleted temporary files in output directory")

    return True


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(name="debug_log")
    userlog = logging.getLogger(name="usermessages")

    prepare_training_data("/dls/mx-scratch/melanie/for_METRIX/results_20190326/AI_training/EP_phasing/traced",
                          "/dls/science/users/riw56156/topaz_test_data/training_test",
                          "/dls/mx-scratch/melanie/for_METRIX/results_20190326/AI_training/xia2_stresstest",
                          "DataFiles/AUTOMATIC_DEFAULT_free.mtz",
                          "/dls/mx-scratch/melanie/for_METRIX/results_20190326/AI_training/EP_phasing/traced",
                          "simple_xia2_to_shelxcde.log",
                          [200, 200, 200],
                          True)