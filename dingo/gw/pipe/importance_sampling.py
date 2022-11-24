#!/usr/bin/env python
""" Script to importance sample based on Dingo samples. Based on bilby_pipe data
analysis script. """
import os
import sys

from bilby_pipe.input import Input
from bilby_pipe.utils import parse_args, logger, convert_string_to_dict

from dingo.gw.inference.inference_pipeline import prepare_log_prob
from dingo.gw.pipe.default_settings import IMPORTANCE_SAMPLING_SETTINGS
from dingo.gw.pipe.parser import create_parser
from dingo.gw.result import Result


class ImportanceSamplingInput(Input):
    def __init__(self, args, unknown_args):
        super().__init__(args, unknown_args)

        # Generic initialisation
        self.meta_data = dict()
        self.result = None

        # Admin arguments
        self.ini = args.ini
        self.scheduler = args.scheduler
        # self.periodic_restart_time = args.periodic_restart_time
        self.request_cpus = args.request_cpus_importance_sampling

        # Naming arguments
        self.outdir = args.outdir
        self.label = args.label
        self.result_format = args.result_format

        # Samples to run on
        self.proposal_samples_file = args.proposal_samples_file

        # Choices for running
        # self.detectors = args.detectors

        # self.sampler = args.sampler
        # self.sampler_kwargs = args.sampler_kwargs
        # self.sampling_seed = args.sampling_seed

        # Frequencies
        # self.sampling_frequency = args.sampling_frequency
        # self.minimum_frequency = args.minimum_frequency
        # self.maximum_frequency = args.maximum_frequency
        # self.reference_frequency = args.reference_frequency

        # # Waveform, source model and likelihood
        # self.waveform_generator_class = args.waveform_generator
        # self.waveform_approximant = args.waveform_approximant
        # self.catch_waveform_errors = args.catch_waveform_errors
        # self.pn_spin_order = args.pn_spin_order
        # self.pn_tidal_order = args.pn_tidal_order
        # self.pn_phase_order = args.pn_phase_order
        # self.pn_amplitude_order = args.pn_amplitude_order
        # self.mode_array = args.mode_array
        # self.waveform_arguments_dict = args.waveform_arguments_dict
        # self.numerical_relativity_file = args.numerical_relativity_file
        # self.frequency_domain_source_model = args.frequency_domain_source_model
        # self.conversion_function = args.conversion_function
        # self.generation_function = args.generation_function
        # self.likelihood_type = args.likelihood_type
        # self.reference_frame = args.reference_frame
        # self.time_reference = args.time_reference
        # self.extra_likelihood_kwargs = args.extra_likelihood_kwargs
        # self.enforce_signal_duration = args.enforce_signal_duration
        #
        # # ROQ
        # self.roq_folder = args.roq_folder
        # self.roq_scale_factor = args.roq_scale_factor
        #
        # # Calibration
        # self.calibration_model = args.calibration_model
        # self.spline_calibration_nodes = args.spline_calibration_nodes
        # self.spline_calibration_envelope_dict = args.spline_calibration_envelope_dict

        # # Marginalization
        # self.distance_marginalization = args.distance_marginalization
        # self.distance_marginalization_lookup_table = None
        # self.phase_marginalization = args.phase_marginalization
        # self.time_marginalization = args.time_marginalization
        # self.jitter_time = args.jitter_time

        self._load_proposal()
        self.importance_sampling_settings = args.importance_sampling_settings

    def _load_proposal(self):
        self.result = Result(file_name=self.proposal_samples_file)
        if "log_prob" not in self.result.samples.columns:
            raise KeyError(
                "log_prob is not present in proposal samples. This is "
                "required for importance sampling."
            )

    @property
    def importance_sampling_settings(self):
        return self._importance_sampling_settings

    @importance_sampling_settings.setter
    def importance_sampling_settings(self, settings):

        # Set up defaults.
        if "phase" not in self.result.samples.columns:
            self._importance_sampling_settings = IMPORTANCE_SAMPLING_SETTINGS[
                "PhaseRecoveryDefault"
            ]
        else:
            self._importance_sampling_settings = dict()

        if settings is not None:
            if settings.lower() == ["default"]:
                pass
            elif settings.lower() in ["phaserecoverydefault"]:
                self._importance_sampling_settings.update(
                    IMPORTANCE_SAMPLING_SETTINGS["PhaseRecoveryDefault"]
                )
            else:
                self._importance_sampling_settings.update(
                    convert_string_to_dict(settings)
                )
        else:
            self._importance_sampling_settings = dict()

    def run_sampler(self):

        if "synthetic_phase" in self.importance_sampling_settings:
            logger.info("Sampling synthetic phase.")
            synthetic_phase_kwargs = {
                **self.importance_sampling_settings["synthetic_phase"],
                "num_processes": self.request_cpus,
            }
            self.result.sample_synthetic_phase(synthetic_phase_kwargs)

        self.result.importance_sample(
            num_processes=self.request_cpus,
            time_marginalization_kwargs=self.importance_sampling_settings.get(
                "time_marginalization"
            ),
            phase_marginalization_kwargs=self.importance_sampling_settings.get(
                "phase_marginalization"
            ),
        )

        self.result.print_summary()
        self.result.to_file(
            os.path.join(self.result_directory, "_".join([self.label, "result.hdf5"]))
        )


def create_sampling_parser():
    """Data analysis parser creation"""
    return create_parser(top_level=False)


def main():
    """Data analysis main logic"""
    args, unknown_args = parse_args(sys.argv[1:], create_sampling_parser())
    # log_version_information()
    analysis = ImportanceSamplingInput(args, unknown_args)
    analysis.run_sampler()
    sys.exit(0)
