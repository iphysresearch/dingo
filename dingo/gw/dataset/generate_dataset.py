import textwrap
import yaml
import argparse
from multiprocessing import Pool
import pandas as pd
import numpy as np
from threadpoolctl import threadpool_limits

from dingo.gw.dataset.waveform_dataset import WaveformDataset
from dingo.gw.prior import build_prior_with_defaults
from dingo.gw.domains import build_domain
from dingo.gw.waveform_generator import WaveformGenerator, generate_waveforms_parallel
from torchvision.transforms import Compose
from dingo.gw.SVD import SVDBasis, ApplySVD


def generate_parameters_and_polarizations(
    waveform_generator, prior, num_samples, num_processes
):
    """
    Generate a dataset of waveforms based on parameters drawn from the prior.

    Parameters
    ----------
    waveform_generator : WaveformGenerator
    prior : Prior
    num_samples : int
    num_processes : int

    Returns
    -------
    pandas DataFrame of parameters
    dictionary of numpy arrays corresponding to waveform polarizations
    """
    print("Generating dataset of size " + str(num_samples))
    parameters = pd.DataFrame(prior.sample(num_samples))

    if num_processes > 1:
        with threadpool_limits(limits=1, user_api="blas"):
            with Pool(processes=num_processes) as pool:
                polarizations = generate_waveforms_parallel(
                    waveform_generator, parameters, pool
                )
    else:
        polarizations = generate_waveforms_parallel(waveform_generator, parameters)
    return parameters, polarizations


def train_svd_basis(parameters, polarizations, size, n_train):
    """
    Train (and optionally validate) an SVD basis.

    Parameters
    ----------
    parameters : DataFrame
    polarizations : dict
        {ifo: np.array} dictionary containing waveforms
    size : int
        Number of elements to keep for the SVD basis.
    n_train : int
        Number of training waveforms to use. Remaining are used for validation. Note
        that the actual number of training waveforms is n_train * len(polarizations),
        since there is one waveform used for each polarization.

    Returns
    -------
    SVDBasis, n_train, n_test
        Since EOB waveforms can fail to generate, provide also the number used in
        training and validation.
    """
    # Prepare data for training and validation.
    train_data = np.vstack([val[:n_train] for val in polarizations.values()])
    test_data = np.vstack([val[n_train:] for val in polarizations.values()])
    test_parameters = pd.concat(
        [
            # I would like to save the polarization, but saving the dataframe with
            # string columns causes problems. Fix this later.
            # parameters.iloc[n_train:].assign(polarization=pol)
            parameters.iloc[n_train:]
            for pol in polarizations
        ]
    )
    test_parameters.reset_index(drop=True, inplace=True)

    print("Building SVD basis.")
    basis = SVDBasis()
    basis.generate_basis(train_data, size)

    # Since there is a possibility that the size of the dataset returned by
    # generate_parameters_and_polarizations is smaller than requested, we don't assume
    # that there are n_test samples. Instead we just look at the size of the test
    # dataset.
    if test_data.size != 0:
        basis.compute_test_mismatches(
            test_data, parameters=test_parameters, verbose=True
        )

    # Return also the true number of samples. Some EOB waveforms may have failed to
    # generate, so this could be smaller than the number requested.
    n_ifos = len(polarizations)
    n_train = len(train_data) // n_ifos
    n_test = len(test_data) // n_ifos

    return basis, n_train, n_test


def generate_dataset(settings, num_processes):
    """
    Generate a waveform dataset.

    Parameters
    ----------
    settings : dict
        Dictionary of settings to configure the dataset
    num_processes : int

    Returns
    -------
    A dictionary consisting of a parameters DataFrame and a polarizations dictionary of
    numpy arrays.
    """

    prior = build_prior_with_defaults(settings["intrinsic_prior"])
    domain = build_domain(settings["domain"])
    waveform_generator = WaveformGenerator(
        settings["waveform_generator"]["approximant"],
        domain,
        settings["waveform_generator"]["f_ref"],
    )

    dataset_dict = {"settings": settings}

    if "compression" in settings:
        compression_transforms = []

        if "svd" in settings["compression"]:
            svd_settings = settings["compression"]["svd"]

            # Load an SVD basis from file, if specified.
            if "file" in svd_settings:
                basis = SVDBasis(file_name=svd_settings["file"])

            # Otherwise, generate the basis based on simulated waveforms.
            else:
                n_train = svd_settings["num_training_samples"]
                n_test = svd_settings.get("num_validation_samples", 0)
                parameters, polarizations = generate_parameters_and_polarizations(
                    waveform_generator,
                    prior,
                    n_train + n_test,
                    num_processes,
                )
                basis, n_train, n_test = train_svd_basis(
                    parameters, polarizations, svd_settings["size"], n_train
                )
                # Reset the true number of samples, in case this has changed due to
                # failure to generate some EOB waveforms.
                svd_settings["num_training_samples"] = n_train
                svd_settings["num_validation_samples"] = n_test

            compression_transforms.append(ApplySVD(basis))
            dataset_dict["svd"] = basis.to_dictionary()

        waveform_generator.transform = Compose(compression_transforms)

    # Generate main dataset
    parameters, polarizations = generate_parameters_and_polarizations(
        waveform_generator, prior, settings["num_samples"], num_processes
    )
    dataset_dict["parameters"] = parameters
    dataset_dict["polarizations"] = polarizations

    dataset = WaveformDataset(dictionary=dataset_dict)
    return dataset


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
        Generate a waveform dataset based on a settings file.
        """
        ),
    )
    parser.add_argument(
        "--settings_file",
        type=str,
        required=True,
        help="YAML file containing database settings",
    )
    parser.add_argument(
        "--num_processes",
        type=int,
        default=1,
        help="Number of processes to use in pool for parallel waveform generation",
    )
    parser.add_argument(
        "--out_file",
        type=str,
        default="waveform_dataset.hdf5",
        help="Name of file for storing dataset.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load settings
    with open(args.settings_file, "r") as f:
        settings = yaml.safe_load(f)

    dataset = generate_dataset(settings, args.num_processes)
    dataset.to_file(args.out_file)


if __name__ == "__main__":
    main()
