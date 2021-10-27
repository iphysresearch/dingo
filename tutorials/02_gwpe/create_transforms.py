import yaml

from bilby.gw.detector import InterferometerList

from dingo.gw.waveform_dataset import WaveformDataset
from dingo.gw.prior_split import default_extrinsic_dict
from dingo.gw.domains import build_domain
from dingo.gw.transforms.parameter_transforms import SampleExtrinsicParameters
from dingo.gw.transforms.detector_transforms import GetDetectorTimes, ProjectOntoDetectors

import numpy as np





if __name__ == '__main__':
    wfd_path = '/Users/mdax//Documents/dingo/devel/dingo-devel/tutorials/02_gwpe' \
               '/datasets/waveforms/02_IMR_test/waveform_dataset.hdf5'
    wfd = WaveformDataset(wfd_path)

    with open('./train_dir/train_settings.yaml', 'r') as fp:
        train_settings = yaml.safe_load(fp)

    extrinsic_prior_dict = default_extrinsic_dict.copy()
    for k, v in train_settings['transform_settings']['extrinsic_prior'].items():
        if v.lower() != 'default':
            extrinsic_prior_dict[k] = v
    ref_time = train_settings['transform_settings']['ref_time']
    detector_list = train_settings['transform_settings']['detectors']
    domain_dict = wfd.domain.domain_dict
    # build objects
    domain = build_domain(domain_dict)
    ifo_list = InterferometerList(detector_list)

    # build transforms
    sample_extrinsic_parameters = SampleExtrinsicParameters(extrinsic_prior_dict)
    get_detector_times = GetDetectorTimes(ifo_list, ref_time)
    project_onto_detectors = ProjectOntoDetectors(ifo_list, domain, ref_time)

    d0 = wfd[0]
    d1 = sample_extrinsic_parameters(d0)
    d2 = get_detector_times(d1)
    d3 = project_onto_detectors(d2)

    import matplotlib.pyplot as plt
    plt.plot(wfd[0]['waveform']['h_cross'].real / d3['parameters'][
        'luminosity_distance'] * 100)
    plt.plot(d3['waveform']['H1'].real)
    plt.show()

    ref_data = np.load('train_dir/waveform_data.npy', allow_pickle=True).item()
    sample_in = {'parameters': ref_data['intrinsic_parameters'],
                 'waveform': {'h_cross': ref_data['hc'],
                              'h_plus': ref_data['hp']},
                 'extrinsic_parameters': ref_data['extrinsic_parameters']}

    # check that we packaged the polarizations correctly
    assert sample_in.keys() == d1.keys()
    for k in sample_in.keys():
        assert sample_in[k].keys() == d1[k].keys()

    sample_out = get_detector_times(sample_in)
    sample_out = project_onto_detectors(sample_out)

    ifo_name = 'L1'

    new = sample_out['waveform'][ifo_name].real
    ref = ref_data['h_d_unwhitened'][ifo_name].real
    deviation = new - ref

    plt.xlim((0,250))
    plt.xlabel('f in Hz')
    plt.title(f'strain.real in {ifo_name}')
    plt.plot(domain(), ref.real, '.', label='research code')
    plt.plot(domain(), new.real, label='dingo code')
    # plt.plot(domain(), deviation, label='deviation')
    plt.legend()
    plt.show()

    plt.xlim((0,1024))
    plt.xlabel('f in Hz')
    plt.title('Deviation between research code and Dingo strain (H1)')
    plt.plot(deviation)
    plt.show()

    print('done')