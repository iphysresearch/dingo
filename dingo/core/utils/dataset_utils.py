import ast
import numpy as np
from os.path import isfile
import h5py

from dingo.core.dataset import DingoDataset
from dingo.core.dataset import recursive_hdf5_save, recursive_hdf5_load


def recursive_check_dicts_are_equal(dict_a, dict_b):
    if dict_a.keys() != dict_b.keys():
        return False
    else:
        for k, v_a in dict_a.items():
            v_b = dict_b[k]
            if type(v_a) != type(v_b):
                return False
            if type(v_a) == dict:
                if not recursive_check_dicts_are_equal(v_a, v_b):
                    return False
            elif not np.all(v_a == v_b):
                return False
    return True


def load_data_from_file(file_name, data_key, settings=None):
    """
    Loads data from a file.

    * If isfile(file_name):
        -> load file as DingoDataset
        -> if settings is not None, checks that settings match dataset.settings
        -> return vars(dataset)[data_key] (which is None, if the key does not match)
    * else:
        -> return None

    Parameters
    ----------
    file_name: str
        name of the dataset file

    data_key:
        key for data in dataset file

    Returns
    -------

    """
    if not isfile(file_name):
        return None

    else:
        dataset = DingoDataset(file_name=file_name, data_keys=[data_key])
        if settings is not None:
            if not recursive_check_dicts_are_equal(settings, dataset.settings):
                raise ValueError(
                    f"Settings {settings} don't match saved settings {dataset.settings}"
                )
        return vars(dataset)[data_key]


# This should eventually be removed. Most usages have been taken into the DingoDataset
# class.


def save_dataset(dataset, settings, file_name):
    print("Saving dataset to " + file_name)
    f = h5py.File(file_name, "w")
    recursive_hdf5_save(f, dataset)
    f.attrs["settings"] = str(settings)
    f.close()


def load_dataset(file_name):
    f = h5py.File(file_name, "r")
    data = recursive_hdf5_load(f)
    try:
        settings = ast.literal_eval(f.attrs["settings"])
    except KeyError:
        settings = None
    f.close()
    return data, settings