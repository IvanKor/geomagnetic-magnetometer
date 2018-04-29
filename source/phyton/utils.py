import os
import sys
import time

timer = time.clock if os.name == 'nt' else time.time
suffixes = ('Oldest', 'Older', 'Old', '')


def GetCyclicNames(fname):
    base, ext = os.path.splitext(fname)
    return [base + x + ext for x in suffixes]


def GetOS():
    if os.name == 'nt':
        return 'Windows %d.%d build %d platform %d, %s' %\
               tuple(sys.getwindowsversion())
    else:
        return os.name


def MakeCyclicName(fname):
    names = GetCyclicNames(fname)
    # rename files
    try:
        os.remove(names[0])
    except:
        pass
    for x in range(1, len(names)):
        try:
            os.rename(names[x], names[x-1])
        except:
            pass
    return names[-1]


def run(path):
    """Attempt to open the data file <path> in an application."""
    try:
        os.startfile(path)
        return
    except AttributeError:
        # startfile only available on Windows
        return str(os.system('open "%s"' % path))
    except WindowsError:
        return str(sys.exc_info()[0])


def time_function(func):
    """Decorator to time a function."""

    def wrapper(*args, **kwargs):
        t1 = timer()
        res = func(*args, **kwargs)
        t2 = timer()
        print('%s took %0.3f ms' % (func.__name__, (t2-t1)*1000.0))
        return res
    return wrapper
