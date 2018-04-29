import os

header = """\
# Saved settings for the plotting program
"""
desc_scale = """\
# The scaling mode, base and range for each plot:
"""
desc_plot_size = """\
# The number of seconds or samples displayed horizontally,
"""
desc_smoothing = """\
# the number of points to  display as a smoothed curve
"""
desc_sources = """\
#    HMC5983, serial-number , channel-number [ , channel-number...]
"""
desc_multi_scale = """\
# when showing all plots on a single chart, scale each plot independently
"""
desc_plot_type = """\
# type of data plotted on x-axis: 0=samples, 1=time, 2=frequencies
"""
desc_manual_sticky = """\
# Displayed as 2 radio buttons to the right of the "manual" radio button.
"""
descriptions = {
    'geometry': '# width x height + x-origin + y-origin',
    'sources': desc_sources,
    'buffer_size': '# the maximum number of samples held',
    'refresh_rate': '# refresh rate in millseconds',
    'single': '# show all plots on a single chart',
    '_81Gs': '# 810 uT',
    '_088Gs': '# 88 uT',
    'calc_81Gs': '# for mult 810 uT',
    'calc_088Gs': '# for mult 88 uT',
    'multi_scale': desc_multi_scale,
    'plot_size': desc_plot_size,
    'smoothing': desc_smoothing,
    'freq_sample': '# number of seconds to sample for frequency analysis',
    'hi_pass': '# only show frequencies above this value',
    'scale_settings': desc_scale,
    'plot_type': desc_plot_type,
    'nt_dB_type': '# nt or dB type PSD',
    'manual_sticky': desc_manual_sticky,
    'logging': '# log print statements to file',
}
# the three types of plot:
SAMPLES, TIMES, FREQS = list(range(3))


class ScaleInfo(object):
    """An object to hold the scaling information for a plot."""

    def __init__(self):
        self.manual_set = False
        self.mode = 0

        # values for the range of the base slider and its current setting
        self.base_min = 0
        self.base_max = 30000
        self.base = 0

        # current setting for the range slider
        self.range = 1000

    def __repr__(self):
        return str(self.__dict__)


class Config(object):
    """An object to hold persistent information for the application."""

    def __init__(self):
        self.geometry = '800x720+100+100'
        d = dict(sep=os.sep)
        sources = ['HMC5983, COM3,1,2,3']
        sources = ','.join(sources)
        self.sources = sources % d
        self.buffer_size = 40000
        self.refresh_rate = 40
        self.single = 0
        self._81Gs = 0        
        self.calc_81Gs = 7.77
        self._088Gs = 1
        self.calc_088Gs = 1.3
        self.multi_scale = 0
        self.plot_size = 10
        self.smoothing = 1
        self.freq_sample = 10
        self.hi_pass = 2.0
        self.scale_settings = {}
        self.manual_sticky = 0
        self.plot_type = SAMPLES
        self.nt_dB_type = 0
        self.logging = 1


def Load(fname):
    """Parse <fname> and return its contents as a dictionary.
    Lines in the file take either of two formats:
        #comment
        key=value
    """
    obj = Config()
    # save the filename so we can save the configuration without needing
    # to supply the filename again
    obj._name = fname
    try:
        for line in open(fname):
            line = line.strip()
            if not line:
                # ignore empty lines
                continue
            if line.startswith('#'):
                # ignore comments
                continue
            bits = line.split('=', 1)
            if not len(bits) == 2:
                # ignore badly formatted lines
                continue
            key = bits[0].strip()
            value = bits[1].strip()
            if not hasattr(obj, key):
                # ignore keys that we don't recognize
                continue
            try:
                # get the type of the existing value
                oldval = getattr(obj, key)
                # dictionaries need special treatment
                if isinstance(oldval, dict):
                    newval = eval(value)
                    if not isinstance(newval, dict):
                        raise TypeError
                else:
                    valtype = type(oldval)
                    newval = valtype(value)
                setattr(obj, key, newval)
            except:
                print('could not convert "%s" to correct type' % line)
    except:
        pass

    # Scale settings are saved as a dictionary, see ScaleInfo.__repr__.
    # Convert them back to a ScaleInfo instance.
    for k, v in obj.scale_settings.items():
        assert isinstance(v, dict)
        scale_info = ScaleInfo()
        for k2, v2 in v.items():
            setattr(scale_info, k2, v2)
        obj.scale_settings[k] = scale_info
    return obj


def Save(obj):
    try:
        fp = open(obj._name, 'w')
        fp.write(header)
        kv = list(obj.__dict__.items())
        kv.sort()
        for k, v in kv:
            if k != '_name':
                if k in descriptions:
                    fp.write('\n')
                    desc = descriptions[k]
                    fp.write(desc)
                    if desc[-1] != '\n':
                        fp.write('\n')
                fp.write('%s = %s\n' % (k, str(v)))
        fp.close()
        return True
    except:
        import sys
        print(str(sys.exc_info()[1]))
        return False
