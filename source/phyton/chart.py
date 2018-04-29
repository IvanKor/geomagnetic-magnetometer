import math
import bisect
import io
from operator import itemgetter
import sys
import time
from time import localtime
import numpy as np
if sys.version_info[0] == 3:
    import tkinter as tk
else:
    import Tkinter as tk

import config
import pubsub
import utils
from datetime import datetime

import string
import re
import os
import numpy as np
from collections import namedtuple
import matplotlib.pyplot as plt
from operator import itemgetter # find sequences of consecutive values
import itertools
import csv

# -*- coding:utf-8 -*-
from calendar import monthrange
import random
import re



# The layout at the left is as follows:
#
# Left edge of window                      y-axis
# |                                        |
# |<--Chart.left_margin------------------->|
# |                       <--LEFT_MARGIN-->|
# |           y-axis-label                 |
# |                                        |
LEFT_MARGIN = 4
BOTTOM_MARGIN = 30
CHART_COLOR = '#e8e8ff'
FOCUS_COLOR = '#ffffff'
AXIS_COLOR = '#808080'
GRID_COLOR = '#cccccc'
AVG_COLOR = '#ff0000'
#AVG_COLOR = '#cccccc'
VALUE_DOT_COLOR = 'black'
VALUE_TEXT_COLOR = '#444'
HIDDEN_LINE = np.array([-1, -1, -1, -2], dtype=np.int)
MODULO_TIME = 1000
MIN_X_SPACING = 40
MIN_Y_SPACING = 20
STATIC_RATE = 0.008 # data rate for static file

# Colors that can be modified
COLORframes = "#000080"     # Color = "#rrggbb" rr=red gg=green bb=blue, Hexadecimal values 00 - ff
COLORcanvas = "#000000"
COLORgrid = "#808080"
COLORtrace1 = "#00ff00"
COLORtrace2 = "#ff8000"
COLORtext = "#ffffff"
COLORsignalband = "#ff0000"
COLORaudiobar = "#606060"
COLORaudiook = "#00ff00"
COLORaudiomax = "#ff0000"
COLORred = "#ff0000"
COLORyellow = "#ffff00"
COLORgreen = "#00ff00"
COLORmagenta = "#00ffff"
minute_step_start = 0
class Buffer(object):
    """Class to hold samples and their times and smoothed values."""

    def __init__(self, _id, length=128):
#    def __init__(self, _id, length= 65536):
        self.id = _id
        self.length = length # total size of buffer
        self.array = np.zeros(self.length, dtype=np.int)
        self.times = np.zeros(self.length, dtype=np.float)
        self.smoothed = np.zeros(self.length, dtype=np.int)
        self.array_write_mx = []
        self.array_write_mx.append('year,month,day,hour,minute,btotal,bx,by,bz\n')
        self.reset()
        #print('Buffer init')
        #self.plot_type2 = app.plot_type.get()
        #self.plot_type2 = self.cfg.plot_type

    def get_array_data(self, array, start, amount):
        """Get <amount> data from <array> in a numpy array.

        In practise, <array> is either self.array or self.smoothed.
        <start> is either an integer index into the buffers, or a float
        fraction into the data in the buffer; if 1.0, use the latest.
        The amount returned may be less than the amount requested.
        """
        if isinstance(start, float):
            # We are to start at that fraction of the existing data.
            # Convert that into a buffer offset.
            if start >= 1.0:
                # the latest data is required
                start = self.write_ptr - amount
                if self.count < self.length:
                    start = max(0, start)
                else:
                    start %= self.length
            else:
                if self.count < self.length:
                    start = int(self.count * start)
                else:
                    # data starts at the write pointer
                    start = self.write_ptr + int(self.length * start)
                    # deal with pointing past the end of the buffer
                    start %= self.length

        end = start + amount
        if self.count < self.length:
            # we haven't wrapped yet
            assert start <= self.count
            # don't supply more data than we have
            end = min(end, self.count)
            amount = end - start
        else:
            # deal with pointing past the end of the buffer
            end %= self.length
        start = end - amount
        if start >= 0:
            # there is enough data to the left of the write pointer
            # Note that a copy is necessary so that if the caller amends the
            # data, the original values in the buffer are not changed.
            result = np.copy(array[start:end])
        else:
            result = np.zeros(amount, dtype=array.dtype)
            result[:-start] = array[start:]
            result[-start:] = array[:end]
        # Sneaky way of supplying an extra result (which is only used in one
        # place) from this function without having to burden get_data(),
        # get_smoothed_data() and get_time_data() with returning it.
        self.time_span = self.times[end - 1] - self.times[start]
        return result

    def get_data(self, start, amount):
        """Get <amount> data from the buffer in a numpy array.

        See get_array_data() docstring for the interpretaion of <start>.
        """
        return self.get_array_data(self.array, start, amount)

    def get_smoothed_data(self, start, amount):
        """Get <amount> data from the smoothed buffer in a numpy array."""
        return self.get_array_data(self.smoothed, start, amount)

    def get_time_data(self, start, end):
        """Get numpy array of time data.

        <start> and <end> are floating time values."""
        ndx_start = self.get_time_index(start)
        ndx_end = self.get_time_index(end)
        amount = ndx_end - ndx_start
        if amount < 0:
            amount += self.length
        return self.get_array_data(self.array, ndx_start, amount)

    def get_time_duration(self):
        """Get timespan of all the entries."""
        if self.count:
            end = self.times[self.write_ptr - 1]
            ndx = 0 if self.write_ptr == self.count else self.write_ptr
            beg = self.times[ndx]
            return end - beg
        else:
            return 0.0

    def get_time_end(self):
        """Get time of the latest entry."""
        return self.last_time

    def get_time_index(self, tm):
        """Get insertion point for time <tm>."""
        if self.write_ptr == self.count:
            # we haven't wrapped yet
            start = 0
            stop = self.write_ptr
        else:
            # we have wrapped
            if self.write_ptr:
                if tm < self.times[0]:
                    # if we started at write_ptr and the
                    start = self.write_ptr + 1
                    stop = self.length
                else:
                    start = 0
                    stop = self.write_ptr
            else:
                start = 0
                stop = self.length
        return bisect.bisect_right(self.times, tm, start, stop)

    def get_time_range(self, start, end):
        """Get start index and amount corresponding to supplied time data.

        <start> and <end> are floating time values.
        Return: start index, amount.
        """
        ndx_start = self.get_time_index(start)
        ndx_end = self.get_time_index(end)
        amount = ndx_end - ndx_start
        if amount < 0:
            amount += self.length
        return ndx_start, amount

    def get_time_restart(self):
        """Get time of the last restart."""
        return self.restart_time

    def get_time_start(self):
        """Get time of the earliest entry."""
        ndx = 0 if self.write_ptr == self.count else self.write_ptr
        return self.times[ndx]

    def reset(self):
        """Start afresh."""
        self.count = 0       # number of data values in buffer
        self.write_ptr = 0   # next free location to store data
        self.smooth_ct = 1   # how many samples  for the smoothing
        self.total = 0       # total number of values read
        self.last_time = utils.timer() # time that last value was added
        self.restart_time = self.last_time

    def restart(self):
        """Restart after a pause.

        Incoming data uses its duration and the end time of the previous data
        to determine the times of the individual samples, see .plot().
        After a pause, we update the last time so that new data is given
        appropraite time stamps.
        We also discard any samples being held for averaging, and make a note
        # of the restart time. This is used for frequency analysis.
        """
        self.last_time = utils.timer()
        self.restart_time = self.last_time
        self.avg_no = 0
        self.avg_value = 0


    def retrieveFromExistingCSV(existing_csv):
        csv_data = [] # store each row as a list of list
        # match format: ['2006', '04', '14', '17', '09', '10.2030', '1.90300', '-9.81400', '-2.04100']
        # ([year, month, day, hour, minute, btotal, bx, by, bz])
        with open(existing_csv, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=',')
            next(reader, None) # skip headers
            csv_data = [row for row in reader]
        return csv_data

    ########### Convert string to datetime
    def datetime_convert(csv_data):
        # covert to datetime format
        datetime_year = [int(col[0]) for col in csv_data]
        datetime_month = [int(col[1]) for col in csv_data]
        datetime_day = [int(col[2]) for col in csv_data]
        datetime_hour = [int(col[3]) for col in csv_data]
        datetime_minute = [int(col[4]) for col in csv_data]
        dt = [] # datetime: '2009-6-8 23:59'
        for i in range(len(csv_data)):
            dt.append("{0}-{1}-{2} {3}:{4}".format(datetime_year[i],
                                                            datetime_month[i],
                                                            datetime_day[i],
                                                            datetime_hour[i],
                                                            datetime_minute[i],
                                                            ))

        print("Date range of data: '{0}' to '{1}'".format(dt[0], dt[len(dt)-1]))
        return dt#[datetime.strptime(t, '%Y-%m-%d %H:%M') for t in dt] # convert to datetime

    ########### IFE IDENTIFICATION CRITERIA
    def multiplePlot(buffer_size, datetime_list, bx, by, bz, btotal, sub_title,filename):
        # plot all four values if they create an event
        # share the x axis among all four graphs
        # four subplots sharing both x/y axes
        print("Graph {0}_event{1}.png saved to output_img".format(os.path.basename(os.path.splitext(filename)[0]), sub_title))
        fig = plt.figure()
        fig.set_figheight(9)
        fig.set_figwidth(16)
        datetime_convert = [datetime.strptime(dt, '%Y-%m-%d %H:%M') for dt in datetime_list] # convert datetime to format to use on x-axis
        #print(datetime_convert)
        pre_buffer_datetime = datetime_convert # save a local copy, to use a the title (even after updated with the buffer)
        
        import matplotlib.dates as mdates
        xfmt = mdates.DateFormatter('%Y-%m-%d %H:%M')
        # b_total does not share the same y axis as the others
        ax4 = plt.subplot(1,1,1)
        ax4.xaxis.set_major_formatter(xfmt)
        plt.setp(ax4.get_xticklabels(), fontsize=6)
        ax4.set_title('Bh')
        #ax4.plot(datetime_convert, btotal, color='black')
        ax4.plot(datetime_convert, btotal, color='blue')
        y_max = np.nanmax(np.asarray(btotal)[np.asarray(btotal) != -np.nan]) + 1 # ignore nan when finding min/max
        y_min = np.nanmin(np.asarray(btotal)[np.asarray(btotal) != -np.nan]) - 1 # ignore nan when finding min/max
        ax4.set_ylim([y_min, y_max])
        plt.ylabel("[nT]")
        
        #f.subplots_adjust(hspace=0)
        plt.setp([a.get_xticklabels() for a in fig.axes[:-1]], visible=False)
        plt.xticks(rotation=90)
        #plt.gcf().autofmt_xdate() # turn x-axis on side for easy of reading
        time_interval = len(datetime_convert) / 3600 # hour
        time_interval2 = len(datetime_convert) // 60 # hour
        #print(len(datetime_convert))

        #ax1.xaxis.set_major_locator(mdates.MinuteLocator(interval=(time_interval2)))
        time_interval = len(datetime_convert) / 60
        #ax4.xaxis.set_major_locator(mdates.MinuteLocator(interval=time_interval2))
        #74 y_tic
        #2265 
        div_tic, mod = divmod(len(datetime_convert), 60)
        #print(div_tic)
        div_tic2, mod = divmod(div_tic, 10)
        div_tic2 = div_tic2 * 10
        #print(div_tic2)
        if (div_tic2 == 0) :
            if (div_tic == 0) :
                ax4.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            else :
                ax4.xaxis.set_major_locator(mdates.MinuteLocator(interval=div_tic))
        else :
            ax4.xaxis.set_major_locator(mdates.MinuteLocator(interval=div_tic2))

        plt.xlabel('Local Time')
        plt.grid(b=True,which='major',color='k',alpha=0.2,linestyle='dotted')

        ax4.tick_params(axis='x', which='major', labelsize=10) # change size of font for x-axis

        plt.tight_layout(rect=[0, 0, 1, 0.97]) # fit x-axis/y-axi/title around the graph (left, bottom, right, top)
        plt.suptitle('Event {0}: {1} to {2}'.format(sub_title, pre_buffer_datetime[0], pre_buffer_datetime[len(pre_buffer_datetime)-1]))
        plt.savefig('output_img/{0}/{1}_event{2}.png'.format(os.path.basename(os.path.splitext(filename)[0]), os.path.basename(os.path.splitext(filename)[0]), sub_title))
        #plt.show()

    def plot_csv_to_png(self, filename):
        #print(filename)
        if not os.path.exists('output_img/{0}'.format(os.path.basename(os.path.basename(os.path.splitext(filename)[0])))):
            os.makedirs('output_img/{0}'.format(os.path.basename(os.path.basename(os.path.splitext(filename)[0]))))
        output_filename = filename


        if not os.path.isfile(output_filename): # if csv doesn't already exist, generate it
            print("\n\tWARNING: No such file or directory, exiting...\n")
            exit()
            
        else: # use exising csv to generate graph
            csv_data = Buffer.retrieveFromExistingCSV(output_filename)

        datetime_lst = []
        datetime_lst = Buffer.datetime_convert(csv_data)   #2018-4-5 10:56

        b_x = [float(col[6]) for col in csv_data]
        b_y = [float(col[7]) for col in csv_data]
        b_z = [float(col[8]) for col in csv_data]
        b_total = [float(col[5]) for col in csv_data]

        # values subject to change
        percent_cutoff_value = .25 #%
        percent_trimmed_from_mean = 0.45 #%
        time_cutoff_in_minutes = 15 # minutes
        update_mean_every_x_hours = 2 # hours
        buffer_size = .30 #% add x seconds around any event found as a buffer


        # plot total event split into parts
        Buffer.multiplePlot(buffer_size, datetime_lst, b_x, b_y, b_z, b_total, "overall",filename)




    def save_csv(self, path):

        f = open(path, 'w')
        i = 0
        ii = len(self.array_write_mx)
        while i < ii:
            f.write(self.array_write_mx[i])
            i = i + 1
        #f.write('\n')
        f.close()
        if ii < 3 :
            return
        #--------------------------------------
        self.plot_csv_to_png(path)

    def save(self, path):
        f = open(path, 'w')
        if self.count == self.length:
            self.array[self.write_ptr:].tofile(f, sep='\n')
            f.write('\n')
        self.array[:self.write_ptr].tofile(f, sep='\n')
        f.write('\n')
        f.close()

    def set_smoothing(self, smooth_ct):
        self.smooth_ct = smooth_ct = max(smooth_ct, 1)
        if smooth_ct > 1:
            total = 0
            for n in range(self.length - smooth_ct, self.length):
                total += self.array[n]
            for n in range(self.length):
                total -= self.array[n - smooth_ct]
                total += self.array[n]
                self.smoothed[n] = total / smooth_ct

    def update(self, tm, value, plot_type):
        """Add integer <value> with timestamp <tm> to the buffer."""
        self.last_time = tm
        #value_s = value
        self.array[self.write_ptr] = value
        self.times[self.write_ptr] = tm
        self.smoothed[self.write_ptr] = value
        self.write_ptr += 1

        # add 1 to the data count if the buffer is not full
        self.count = min(self.count+1, self.length)

        # if smoothing is required, calculate smoothed value  of
        # the last .smooth_ct values
        if self.smooth_ct > 1:
            # find the index of the oldest of the values to be smoothed
            start = self.write_ptr - min(self.smooth_ct, self.count)
            if start >= 0:
                total = sum(self.array[start:self.write_ptr])
                count = self.write_ptr - start
            else:
                # when the range of smoothed values wraps,
                # we must sum two ranges
                total = sum(self.array[:self.write_ptr])
                total += sum(self.array[start:])
                count = self.write_ptr - start
            self.smoothed[self.write_ptr - 1] = total / count

        # wrap the write pointer if necessary
        if self.write_ptr >= self.length:
            self.write_ptr = 0


class Plot(Buffer):
    """Class to represent a single plot on a Chart."""
    #plot = Plot(self, color, plot_id, self.cfg.buffer_size)
    def __init__(self, chart, color, _id, length=128):
        Buffer.__init__(self, _id, length)
        self.color = color
        self.value = 0
        self.mark = 0
        self.use_chart(chart, 0)
 
    def __str__(self):
        s = io.StringIO()
        s.write('PLOT       %s\n' % self.label)
        s.write('length     %d\n' % self.length)
        s.write('count      %d\n' % self.count)
        s.write('write_ptr  %d\n' % self.write_ptr)
        if len(self.array) > 8:
            for n in range(4):
                s.write('%d,' % self.array[n])
            s.write('...')
            for n in range(self.write_ptr - 4, self.write_ptr):
                s.write('%d,' % self.array[n])
            s.write('\n')
        return s.getvalue()


    def set_label(self, plot_type):

        if plot_type == 2 :
            #self.find_above(item5)
            self.delete(self.item_sampl)
            self.delete(self.item_fft)
            if (self.cfg.nt_dB_type == 3) :
                self.item_fft = self.create_text(0, 0, text='dB/Hz PSD ',font=("Courier", 12, "bold"))
                self.coords(self.item_fft, (90,13))
            if (self.cfg.nt_dB_type == 2) :
                self.item_fft = self.create_text(0, 0, text='nT/Hz PSD ',font=("Courier", 12, "bold"))
                self.coords(self.item_fft, (90,13))
        else :
            self.delete(self.item_fft)
            self.delete(self.item_sampl)
            self.item_sampl = self.create_text(0, 0, text='nT',font=("Courier", 12, "bold"))
            self.coords(self.item_sampl, (50,13))
        #self.coords(item_text, (38+40,20))

    def show_value(self, data_values, mouse_x):
        """Show data value on the plot."""
        # remove any existing value
        self.unshow_value()
        # get the x,y coordinates of the line
        xy = self.chart.coords(self.plot)
        # find the value closest to mouse_x
        x = xy[0]
        for n in range(0, len(xy) - 2, 2):
            next_x = xy[n + 2]
            if mouse_x < next_x:
                y = xy[n + 1]
                next_y = xy[n + 3]
                # calculate slope values for later adjustment of location
                dx = next_x - x
                dy = next_y - y
                if mouse_x > x + (next_x - x) / 2:
                    # the mouse is nearer the next location than this one,
                    # so use its values
                    n += 2
                    x = next_x
                    y = next_y

                # draw a dot on the line
                r = 2 # radius of oval
                self.mark = self.chart.create_oval(x-r, y-r, x+r, y+r,
                                                   fill=VALUE_DOT_COLOR)

                # adjust the location of the value to the right, up or down,
                # depending on the slope of the line
                # (note that y INCREASES for a negative slope)
                if abs(dy) > dx:
                    # slope of line is > 45 degrees, so move value right
                    x += 4
                elif dy < 0:
                    # slope is increasing, so move value down
                    y += 8
                else:
                    # slope is decreasing, so move value up
                    y -= 8

                # show the data value
                yval = data_values[n // 2]
                self.value = self.chart.create_text((x, y),
                                                    text='%d'%int(yval),
                                                    anchor=tk.W,
                                                    fill=VALUE_TEXT_COLOR)
                return
            x = next_x

    def unshow_value(self):
        """Remove any data value displayed on the plot."""
        self.chart.delete(self.mark)
        self.chart.delete(self.value)
        self.value = 0
        self.mark = 0

    def unuse_chart(self):
        """Disassociate this instance with its chart."""
        assert self.chart
        self.unshow_value()
        self.chart.delete(self.plot)
        self.chart.delete(self.plot_avg)
        self.chart.delete(self.item_text)
        self.chart = None

    def use_chart(self, chart, ndx):
        """Associate a chart with this instance."""
        self.chart = chart
        self.plot_avg = chart.create_line(0, 0, 0, 1, fill=AVG_COLOR)
        self.plot = chart.create_line(0, 0, 0, 1, fill=self.color, width=1)
        self.item_text = chart.create_text((0, 0), fill=self.color,
                                           anchor=tk.NW)


class Chart(tk.Canvas):
    """Class to represent a single graphic representation of data.

    It can show one or more data plots.
    """
    left_margin = 0

    def __init__(self, master, running, *args, **kwargs):
        tk.Canvas.__init__(self, master,
                           background=CHART_COLOR,
                           bd=2,
                           relief=tk.GROOVE,
                           cursor="crosshair",
                           *args, **kwargs)
        # sleazy way of obtaining access to the configuration object
        #print('init class Chart')

        self.item_fft = self.create_text(0, 0, text='')
        self.item_sampl = self.create_text(0, 0, text='')

        app = master.master
        self.app = app
        self.cfg = app.cfg

        self.ymin_data = 0
        self.ymax_data = 0
        self.ymin = 0
        self.ymax = 0
        self.scale_mode = app.scale_mode.get()
        self.plot_type = app.plot_type.get()
        #self.nt_dB_type = app.nt_dB_type.get()
        self.nt_dB_type = self.cfg.nt_dB_type
        #print(self.plot_type)

        self.plot_size = app.plot_sizes[self.plot_type]
        self.multi = self.cfg.multi_scale
        self.time_diff = app.time_diff
        self.freq_sample = self.cfg.freq_sample
        self.max_freq = 0

        self.plots = []
        self.running = running
        self.W = 0
        self.H = 0
        self.tm_start = 0.0         # time at left-hand edge of chart
        self.tm_end = 0.0           # time at right-hand edge of chart
        self.has_focus = False

        # prepare items for canvas
        self.item_y_axis = self.create_line(0, 0, 0, 1, fill=AXIS_COLOR)
        self.y_lines = []           # list of horizontal lines on y-axis
        self.y_labels = []          # list of labels for lines on y-axis
        self.x_lines = []           # list of vertical lines on x-axis
        self.x_labels = []          # list of labels for lines on x-axis
        self.pts = np.zeros(2)      # list of x,y points for plot
        self.freqs = []
        self.zero_freqs = []
        self.zero_freqs.append(self.create_text((950, 30 ),
                                               fill='#00C000',
                                               font=("Courier",
                                                     32,
                                                     "bold")))
        for n in range(3):
            self.freqs.append(self.create_text((300, 30 + n * 30),
                                               fill='#00C000',
                                               font=("Courier",
                                                     32 - 8 * n,
                                                     "bold")))

        # measure and save the size needed for y-axis labels
        item = self.create_text(0, 0, text='999M')
        bounds = self.bbox(item)
        self.delete(item)
        Chart.left_margin = bounds[2] - bounds[0] + LEFT_MARGIN + 2
        # create various bindings
        self.tk_bound = []
        for type_, cb in Chart.bindings:
            func_id = self.bind(type_, cb.__get__(self, Chart))
            self.tk_bound.append((type_, func_id))
        for type_, cb in Chart.subscriptions:
            pubsub.subscribe(type_, cb.__get__(self, Chart))

    def __str__(self):
        s = io.StringIO()
        s.write('ymin     %d\n' % self.ymin)
        s.write('ymax      %d\n' % self.ymax)
        s.write('scale_mode  %d\n' % self.scale_mode)
        for plot in self.plots:
            s.write(str(plot))
        return s.getvalue()

    def label_nT_dB_Hz_PSD (self):
        self.delete(self.item_fft)
        self.delete(self.item_sampl)
        self.delete(self.item_fft)
        if (self.cfg.nt_dB_type == 3) :
            self.item_fft = self.create_text(0, 0, text='dB/Hz PSD ',font=("Courier", 12, "bold"))
            self.coords(self.item_fft, (90,13))
        if (self.cfg.nt_dB_type == 2) :
            self.item_fft = self.create_text(0, 0, text='nT/Hz PSD ',font=("Courier", 12, "bold"))
            self.coords(self.item_fft, (90,13))


    def add_plot(self, plot_id, color):
        """Add a new Plot to this chart."""

        #print('add_plot')
        plot = Plot(self, color, plot_id, self.cfg.buffer_size)
        plot.set_smoothing(self.cfg.smoothing)

        self.plots.append(plot)
        Plot.set_label(self, self.plot_type)
        return plot

    def draw_background(self):
        """Draw items that only change when the Y-range or canvas size change.
        """
        # draw horizontal lines and their labels
        self.draw_lines()
        # draw the Y-axis
        self.coords(self.item_y_axis, Chart.left_margin, 0, Chart.left_margin, self.H)

    def draw_lines(self):
        """Construct canvas items for the horizontal lines and labels."""
        W, H = self.W, self.H - BOTTOM_MARGIN
        x = Chart.left_margin

        # remove existing lines and labels
        #print(Plot.label)
        while self.y_lines:
            self.delete(self.y_lines.pop())
        while self.y_labels:
            self.delete(self.y_labels.pop())

        if self.scale_mode != 2 and len(self.plots) > 1 and self.multi:
            # when more than one plot on a chart, don't draw lines or labels
            return

        span = self.ymax - self.ymin or 1 # avoid divide-by-zero
        # using a minimum value for line spacing, find approx how many lines
        count = H // MIN_Y_SPACING
        if count <= 0:
            # too small, probably still in setup
            return
        # find the range between each line
        step = float(span) / count
        # round that up to a reasonable whole value...
        # ...first, scale down to 10 or less
        factor = 1
        while step > 10.0:
            factor *= 10
            step /= 10
        # ...then choose whether to draw lines every 1, 2, 5, or 10 units
        if step < 1.4:   # sqrt(1*2)
            step = 1
        elif step < 3.2: # sqrt(2*5)
            step = 2
        elif step < 7.1: # sqrt(5*10)
            step = 5
        else:
            step = 10
        # restore the scaling factor
        step *= factor
        # calculate the value of the first line
        val = (self.ymin + step) // step * step
        # generate lines and labels
        ratio = float(H) / span
        w = x - LEFT_MARGIN
        while val < self.ymax:
            y = (self.ymax - val) * ratio
            item = self.create_line(x, y, W, y, fill=GRID_COLOR)
            self.y_lines.append(item)
            # make sure the line will appear behind the plot(s)
            self.lower(item)
            # show the value for this line, abbreviating if appropriate
            if factor < 1000:
                label = '%4d' % val
            elif factor < 1000000:
                label = '%3dK' % (val / 1000)
            else:
                label = '%3dM' % (val / 1000000)
            item = self.create_text(w, y, text=label, anchor=tk.E,
                                    width=w, justify=tk.RIGHT)
            self.y_labels.append(item)
            val += step

    def draw_plot_samples(self, plot, ycoords, start, mode_smooth):
        """Update a specific plot with its current data.

        If <start> is not 1.0, start plotting data from that fraction of the
        total data available.
        """
        H = self.H - BOTTOM_MARGIN
        if H <= 0:
            return # makes debugging easier

        ymin = self.ymin
        ymax = self.ymax
        if self.scale_mode != 2 and len(self.plots) > 1 and self.multi:
            # not manual scaling
            # and showing more than one plot on this chart
            # and plots do not share the same scale
            ymin = plot.ymin
            ymax = plot.ymax
        count = len(ycoords)
        ycoords -= int(ymin)                      # make lowest displayed value 0
        ycoords = ycoords.astype(np.float)   # work with floating point
        span = ymax - ymin
        if span:
            ycoords /= span                  # normalize to range 0.0-1.0
        ycoords = 1.0 - ycoords              # invert because y=0 is at top
        ycoords *= H                         # scale to fit

        # if the array of canvas coordinates does not match
        # the number of points to be plotted, rebuild it
        if len(self.pts) != count * 2:
            self.make_x_points(count)

        # fill in the y-coordinates of all the points to be plotted
        pts = self.pts
        odd_indices = list(range(1, count * 2 + 1, 2))
        pts.put(odd_indices, ycoords)
        if count < 2:
            pts = HIDDEN_LINE
        if mode_smooth :
            if self.cfg.manual_sticky :   
                self.coords(plot.plot, *HIDDEN_LINE)
            else:
                self.coords(plot.plot, *pts)
        else:
            self.coords(plot.plot, *pts)

        #self.coords(plot.plot, *pts)
        #self.coords(plot.plot, *HIDDEN_LINE)

        # do the same thing for the moving smooth_ct
        #print(plot.smooth_ct)
        if mode_smooth :
            if plot.smooth_ct > 1:
                ycoords = plot.get_smoothed_data(start, self.plot_size)
                ycoords -= int(ymin)
                ycoords = ycoords.astype(np.float)
                if span:
                    ycoords /= span # normalize to range 0.0-1.0
                ycoords = 1.0 - ycoords # flip
                ycoords *= H
                pts.put(odd_indices, ycoords)
                if count < 2:
                    pts = np.arange(4.0)
            else:
                pts = HIDDEN_LINE
        else:
            pts = HIDDEN_LINE
        self.coords(plot.plot_avg, *pts)

    def draw_x_lines(self):
        """Construct canvas items for the x-lines and labels."""
        W = self.W - 4 # allow for borders

        if W > 0 and self.plots:
            Chart.func_draw_x[self.plot_type](self, W, self.H - 4)

    def draw_x_lines_freqs(self, W, H):
        """Construct canvas items for the x-lines and labels."""

        # remove existing tick marks and labels
        while self.x_lines:
            self.delete(self.x_lines.pop())
        while self.x_labels:
            self.delete(self.x_labels.pop())

        # find how many values are being displayed,
        # and how many pixels each value takes up
        x_count = self.max_freq
        if x_count <= 0:
            return
        f_span = float(W - Chart.left_margin)

        # place x_lines at least 30 pixels apart and at sensible values
        multiplier = 0.001
        dp = 3
        sub_mul = (1.0, 2.0, 5.0)
        sub_index = 0
        while 1:
            step = multiplier * sub_mul[sub_index]
            x_step = f_span * step / x_count
            if x_step >= 30.0:
                break
            sub_index += 1
            if sub_index == 3: # aka len(sub_mul)
                sub_index = 0
                multiplier *= 10.0
                dp -= 1

        # generate lines
        value = 0
        x = 0.0
        fmt = '%%.%df' % dp if dp > 0 else '%.f'
        while x < f_span:
            x_pixel = Chart.left_margin + int(x)
            item = self.create_line(x_pixel, H, x_pixel, 0,
                                    fill=GRID_COLOR)
            self.x_lines.append(item)
            self.lower(item)
            self.x_labels.append(self.create_text(x_pixel, H-16,
                                                  text=fmt % value))
            value += step
            x += x_step

    def draw_x_lines_samples(self, W, H):
        """Construct canvas items for the x-lines and labels."""

        # remove existing tick marks and labels
        while self.x_lines:
            self.delete(self.x_lines.pop())
        while self.x_labels:
            self.delete(self.x_labels.pop())

        # find how many values are being displayed,
        # and how many pixels each value takes up
        x_count = self.plot_size
        x_delta = float(W - Chart.left_margin) / x_count

        # place x_lines a reasonable space apart
        # by only marking every Nth value
        x_step = x_delta
        for step in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
            if x_step >= 20.0:
                # steps will be at least 20 pixels apart
                break
            x_step = x_delta * step

        # generate lines
        value = 0
        for x in range(0, x_count, step):
            x_pixel = Chart.left_margin + int(x * x_delta)
            item = self.create_line(x_pixel, H, x_pixel, 0,
                                    fill=GRID_COLOR)
            self.x_lines.append(item)
            self.lower(item)
            self.x_labels.append(self.create_text(x_pixel, H-16,
                                                  text=str(value)))
            value += step

    @staticmethod
    def get_maxima(ycoords, duration, cfg):
        """Get frequency maxima from the supplied list."""
        # minimum sample width between successive maxima
        width = (len(ycoords) + 50) / 100
        hi_pass = cfg.hi_pass # minimum frequency to report
        back_2 = 0.0
        back_1 = 0.0
        last = [0, 0.0]
        maxima = [last] # a list of [index, maximum] items
        for x, y in enumerate(ycoords):
            if x < last[0] + width:
                if y > last[1]:
                    last[0] = x
                    last[1] = y
            elif y < back_1 and back_2 < back_1:
                # we've just passed a maximum; record it
                last = [x - 1, back_1]
                maxima.append(last)
            back_2 = back_1
            back_1 = y

        # perform a reverse sort on the maxima
        maxima.sort(key=itemgetter(1), reverse=True)

        # use up to 3 frequencies above the hi_pass value
        indices = []
        for x, y in maxima:
            x /= duration
            if x > hi_pass:
                indices.append(x)
                if len(indices) >= 3:
                    break
        return indices

    def make_x_points(self, count):
        """Construct an array of points to plot on the canvas.

        The canvas line function takes two values, x and y, for each point.
        Here we fill in the x-points only. draw_plot() will fill in the
        y-points and pass the array to the line.
        """
        self.pts = np.arange(float(count * 2)) # of visible points
        self.pts /= float(count * 2)           # scale to 0.0 ... 1.0
        x_pixels = self.W - Chart.left_margin
        if self.plot_type != config.FREQS and count < self.plot_size:
            # when the number of points is less than the number of points
            # represented on the x-axis, scale the available pixels accordingly
            x_pixels = x_pixels * count / self.plot_size
        self.pts *= x_pixels                   # convert to pixels
        self.pts += Chart.left_margin          # adjust for left margin

    def on_button_down(self, event):
        """Set focus to this chart and notify the world."""
        pubsub.publish('focus', self)
        # We must establish the new focus state for charts before the main app
        # adjusts controls, because the charts' responses depend on whether
        # they have focus or not.
        # Because pubsub uses dictionaries, the order in which registered
        # callbacks occur is indeterminate, so to ensure that the main app is
        # notified last, we use a different topic.
        pubsub.publish('focus2', self)

    def on_button_up(self, event):
        """Remove any data values from plots on all charts."""
        pubsub.publish('unshow_points')

    def on_focus(self, data):
        """Chart with focus has been changed."""
        self.has_focus = data is self
        self['background'] = FOCUS_COLOR if self.has_focus else CHART_COLOR

    def on_freq_sample(self, data):
        self.freq_sample = data

    def on_man_base(self, base, start, all):
        """The manual-scaling base slider has been changed."""
        if not all and not self.has_focus:
            return
        self.ymax += (base - self.ymin)
        self.ymin = base
        # we need to call draw_background() here to update the y-axis values
        # because draw_plot() will not detect that the range has changed
        self.draw_background()
        # redraw the plots
        self.update_all(start)

    #def on_man_range(self, span, start, all, zero_center):
    def on_man_range(self, span, start, all):
        if not all and not self.has_focus:
            return
        #if zero_center:
        #    self.ymin = -(span / 2)
        self.ymax = self.ymin + span
        # we need to call draw_background() here to update the y-axis values
        # because draw_plot() will not detect that the range has changed
        self.draw_background()
        # redraw the plots
        self.update_all(start)

    def on_motion(self, event):
        """Show data values on the plots on all charts."""
        if not self.running:
            pubsub.publish('show_points', event.x)

    def on_multi(self, data):
        """When single chart, scale each plot independently."""
        self.multi = data
        self.draw_background()

    def on_plot_size(self, plot_size, plot_type):

        Plot.set_label(self, plot_type) 
        """pubsub: plot size (ie amount to show on x-axis) has changed."""
        if plot_type == self.plot_type:
            self.plot_size = plot_size
            # for the case that the number of points is less than plot size,
            # ie the number of points to show on the x-axis, we must force the
            # x-values of the points to be recalculated
            self.pts = np.arange(0.0)
            self.draw_x_lines()

    def on_plot_type(self, data, all):
        """Meaning of x-axis has changed."""
        #print('on_plot_type ',data)
        if all or self.has_focus:
            if config.FREQS in (self.plot_type, data):
                #print('on_plot_type ')
                # changing to or from frequency plot, so turn smoothing on/off
                # depending on plot type
                smooth = 1 if data == config.FREQS else self.cfg.smoothing
                for plot in self.plots:
                    plot.set_smoothing(smooth)
                # hide frequency values when not needed
                if data != config.FREQS:
                    for item in self.freqs:
                        self.itemconfig(item, text='')
                    for item in self.zero_freqs:
                        self.itemconfig(item, text='')
                    # redraw the y-axis
                    _dict = self.cfg.scale_settings
                    if plot.label in _dict:
                        sc = _dict[plot.label]
                        #print(sc.base, sc.base + sc.range)
                        self.set_y_scale(sc.base, sc.base + sc.range)
            self.plot_type = data
            self.update_all()

    def on_resize(self, event):
        self.W, self.H = event.width, event.height
        self.draw_background()
        self.pts = np.arange(0)
        self.draw_x_lines()
        self.update_all()

    def on_running(self, data):
        """pubsub handler."""
        self.running = data
        if data:
            for plot in self.plots:
                plot.restart()

    def on_scale_mode(self, data, all):
        """pubsub handler."""
        if all or self.has_focus:
            self.scale_mode = data
            if self.has_focus and self.plots:
                if data == 2: # manual
                    info = self.app.scaling
                    if not info.manual_set :
                        ycoords = self.plots[0].get_data(self.start,
                                                         self.plot_size)
                        if len(ycoords) > 0:
                            ymin = min(ycoords)
                            ymax = max(ycoords)
                            span = ymax - ymin
                            edge = max(span // 20, 30)
                            info.base_min = ymin - edge
                            info.base_max = ymax + edge
                            info.range = info.base_max - info.base_min
                            info.base = info.base_min
                            info.manual_set = True

    def on_scroll(self, data):
        """pubsub handler. <data> = low position of thumb, range 0-1."""
        self.update_all(data)

    def on_show_points(self, data):
        """Show data values on the plots."""
        for plot in self.plots:
            if self.plot_type == config.TIMES:
                start, amount = plot.get_time_range(self.tm_start, self.tm_end)
            else:
                start = self.start
                amount = self.plot_size
            ycoords = plot.get_data(start, amount)
            plot.show_value(ycoords, data)

    def on_smoothing(self, data):
        for plot in self.plots:
            plot.set_smoothing(data)

    def on_unshow_points(self):
        """Remove any data values from the plots."""
        for plot in self.plots:
            plot.unshow_value()

##    @utils.time_function
    def plot(self, plot_id, duration, data, static):
        """Plot the value(s) <data> on the plot with id <plot_id>.

        If <static>, the data is a static sample, and we plot the data across
        the current plot size.
        """
        for plot in self.plots:
            if plot_id == plot.id:
                if static:
                    duration = STATIC_RATE
                    start = utils.timer() - duration * len(data)
                    plot.restart_time = start
                else:
                    duration /= len(data)
                    start = plot.get_time_end()
                # TODO could optimise this with numpy?
                for value in data:
                    start += duration
                    #print(self.plot_type)
                    plot.update(start, value, self.plot_type)
                plot.total += len(data)
                return
        else:
            print('**** plot not found ****')

    def reset(self):
        """Start afresh for FILE."""
        for plot in self.plots:
            self.coords(plot.plot, *HIDDEN_LINE)
            plot.reset()

    def set_y_scale(self, new_min, new_max):
        """Set the y-scale to the supplied values, adding 5% to the top and
        bottom to leave a margin between the plot and the edges of the canvas.
        """
        self.ymin_data = new_min
        self.ymax_data = new_max
        span = new_max - new_min
        edge = span // 20
        self.ymin = new_min - edge
        self.ymax = new_max + edge
        self.draw_background()

    def unlink(self):
        while self.tk_bound:
            self.unbind(*self.tk_bound.pop())
        for type_, cb in Chart.subscriptions:
            pubsub.unsubscribe(type_, cb.__get__(self, Chart))
        while self.plots:
            plot = self.plots.pop()
            plot.unuse_chart()
        self.grid_forget()

##    @utils.time_function
    def update_all(self, start=1.0):
        """Update all plots on the chart.

        If <start> is not 1.0, start plotting data from that fraction of the
        total data available.
        """
        Chart.func_update[self.plot_type](self, start)

    def update_all_freqs(self, start=1.0):
        """Calculate the frequency distribution for the 1st plot on the chart.

        If <start> is not 1.0, start plotting data from that fraction of the
        total data available.
        Note the meaning of the Horiz. Scale slider:
        * For samples and time, it's the number of samples/time to display.
        * For frequency, it's the maximum frequency we want to see.
        """

        global minute_step_start
        plot = self.plots[0]

        #plot.label ='priba'
        # Get the data range that we wish to analyse.
        # freq_sample *is* the timespan for this data.
        oldest = max(plot.get_time_restart(), plot.get_time_start())
        newest = plot.get_time_end()
        if start >= 1.0:
            tm_start = newest - self.freq_sample
            tm_end = newest
        else:
            # the scrollbar is not at maximum; calculate the start represented
            # by the scrollbar thumb, and add the data range to get the end
            tm_start = oldest + (newest - oldest) * start
            tm_end = tm_start + self.freq_sample

        # adjust start and end to fall within the available limits
        over = tm_end - newest
        if over > 0.0:
            tm_end -= over
            tm_start -= over
        tm_start = max(tm_start, oldest)

        self.tm_start = tm_start
        self.tm_end = tm_end
        duration = tm_end - tm_start

        # get the samples for that time period
        start, amount = plot.get_time_range(tm_start, tm_end)
        ycoords = plot.get_data(start, amount)
        amount = len(ycoords)

        if amount < 2:
            return # avoid numpy exception
        #print('amount= ',amount)
        # We perform a Fast Fourier Transform on the entire set of samples.
        # This gives us a similarly-sized array of frequency coefficients; see
        # http://stackoverflow.com/questions/604453/analyze-audio-using-fast-fourier-transform
        fft = np.fft.fft(ycoords)

        #fft[0] = 0.0

        # The sampling frequency SF = amount / duration.
        # The frequency spacing  FS = SF / amount
        #                           = 1 / duration.
        # The plot_size slider gives the maximum frequency we want to display.
        # The number of coefficients to give this frequency is N where
        #   N * FS = plot_size
        # Solve for N:
        #   N = plot_size / FS
        #   N = plot_size * duration
        # Use the lesser of this or the useful coefficients (only half of the
        # coefficients are useful because of the Nyquist limit):
        coeffs = min(self.plot_size * duration, amount / 2)
        coeffs_psd = coeffs * 2
        if not coeffs:
            return
        # throw away the unwanted higher-frequency samples
        fft = fft[0:int(coeffs)]
        # calculate the power at each frequency

        ycoords = (((np.sqrt(fft.real * fft.real + fft.imag * fft.imag))/(coeffs_psd)).astype(float))
        datetim = str(datetime.now())
        minut = int(datetime.now().minute)
        if not (minute_step_start == minut) :
            year = datetim[0:4]
            month = datetim[5:7]
            day = datetim[8:10]
            hour = datetim[11:13]
            minute = datetim[14:16]
            btotal = ycoords[0]
            bx = ycoords[0] 
            by = ycoords[0]
            bz = ycoords[0]
            s = '%s,%s,%s,%s,%s,%4.1f,%4.1f,%4.1f,%4.1f\n' % (year, 
                month, 
                day, 
                hour, 
                minute,  
                ycoords[0], 
                ycoords[0], 
                ycoords[0], 
                ycoords[0])
            plot.array_write_mx.append(s)
            #print(s)
            minute_step_start = minut
            

        for n, item in enumerate(self.zero_freqs):
            s = '%4.1f nT/Hz' % ycoords[0]
            s = s.rjust(10)
            self.itemconfig(item, text=s)


        
        if (self.cfg.nt_dB_type == 3) :
            ycoords = 10 * np.log10(ycoords)
           #print("--> ",self.cfg.nt_dB_type)    
        

        #ycoords = 10 * np.log10(ycoords)
        ycoords[0] = 0
        # calculate and display the maxima
        maxima = Chart.get_maxima(ycoords, duration, self.cfg)
        for n, item in enumerate(self.freqs):
            if n < len(maxima):
                s = '%3.2f Hz' % maxima[n]
                s = s.rjust(10)
            else:
                s = ''
            #print(n, item,s,self.freqs)    
            self.itemconfig(item, text=s)
        #self.itemconfig(item_text, text='self.label')
        #self.coords(item_text, (Chart.left_margin + 4, 0 * 16 + 4))
        # always auto-scale
        self.set_y_scale(ycoords.min(), ycoords.max())

        # The maximum frequency = # coefficients * FS = N / duration.
        # This is saved for display_x_lines.
        self.max_freq = coeffs / duration
        self.draw_x_lines()

        self.draw_plot_samples(plot, ycoords, start,0)


    def update_all_freqs_sampl(self, start=1.0):
        """Calculate the frequency distribution for the 1st plot on the chart.

        If <start> is not 1.0, start plotting data from that fraction of the
        total data available.
        Note the meaning of the Horiz. Scale slider:
        * For samples and time, it's the number of samples/time to display.
        * For frequency, it's the maximum frequency we want to see.
        """

        global minute_step_start
        plot = self.plots[0]

        #plot.label ='priba'
        # Get the data range that we wish to analyse.
        # freq_sample *is* the timespan for this data.
        oldest = max(plot.get_time_restart(), plot.get_time_start())
        newest = plot.get_time_end()
        if start >= 1.0:
            tm_start = newest - self.freq_sample
            tm_end = newest
        else:
            # the scrollbar is not at maximum; calculate the start represented
            # by the scrollbar thumb, and add the data range to get the end
            tm_start = oldest + (newest - oldest) * start
            tm_end = tm_start + self.freq_sample

        # adjust start and end to fall within the available limits
        over = tm_end - newest
        if over > 0.0:
            tm_end -= over
            tm_start -= over
        tm_start = max(tm_start, oldest)

        self.tm_start = tm_start
        self.tm_end = tm_end
        duration = tm_end - tm_start

        # get the samples for that time period
        start, amount = plot.get_time_range(tm_start, tm_end)
        ycoords = plot.get_data(start, amount)
        amount = len(ycoords)

        if amount < 2:
            return # avoid numpy exception

        fft = np.fft.fft(ycoords)

        coeffs = min(self.plot_size * duration, amount / 2)
        coeffs_psd = coeffs * 2
        if not coeffs:
            return
        # throw away the unwanted higher-frequency samples
        fft = fft[0:int(coeffs)]
        # calculate the power at each frequency

        ycoords = (((np.sqrt(fft.real * fft.real + fft.imag * fft.imag))/(coeffs_psd)).astype(float))
        datetim = str(datetime.now())
        minut = int(datetime.now().minute)
        if not (minute_step_start == minut) :
            year = datetim[0:4]
            month = datetim[5:7]
            day = datetim[8:10]
            hour = datetim[11:13]
            minute = datetim[14:16]
            btotal = ycoords[0]
            bx = ycoords[0] 
            by = ycoords[0]
            bz = ycoords[0]
            s = '%s,%s,%s,%s,%s,%4.1f,%4.1f,%4.1f,%4.1f\n' % (year, 
                month, 
                day, 
                hour, 
                minute,  
                ycoords[0], 
                ycoords[0], 
                ycoords[0], 
                ycoords[0])
            plot.array_write_mx.append(s)
            #print(s)
            minute_step_start = minut

    def update_all_samples(self, start=1.0):
        """Update all plots on the chart.

        If <start> is not 1.0, start plotting data from that fraction of the
        total data available.
        """
        #print('update_all_samples')

        #self.draw_background()
        self.start = start
        #print('update_all_samples')
        # when multiple plots are drawn on a single chart, we need to determine
        # ymin/ymax for all plots; this may require the currently-visible data,
        # which is also required by draw_plot(). To avoid constructing this
        # data twice, we save it here and pass it into draw_plot().
        all_data = []

        # determine if the y-axis needs to be rescaled
        new_min = sys.maxsize
        new_max = -sys.maxsize
        for plot in self.plots:
            ycoords = plot.get_data(start, self.plot_size)
            all_data.append(ycoords) # save for later (see above comment)
            if len(ycoords) == 0:
                continue # else min-max will fail
            if self.scale_mode == 0: # auto-scale visible
                ymin = ycoords.min()
                ymax = ycoords.max()
            elif self.scale_mode == 1: # auto-scale all
                if plot.count == plot.length:
                    buf = plot.array
                else:
                    buf = plot.array[:plot.count]
                ymin = buf.min()
                ymax = buf.max()
            else:
                continue
            new_min = min(new_min, ymin)
            new_max = max(new_max, ymax)
            # add 5% (see below) to the range and save it for each plot
            # in case independent scaling is in force
            edge = (ymax - ymin) // 20
            plot.ymin = ymin - edge
            plot.ymax = ymax + edge

        if self.scale_mode != 2: # auto-scaling (visible or all) is selected
            self.set_y_scale(new_min, new_max)

        for plot, ycoords in zip(self.plots, all_data):
            self.draw_plot_samples(plot, ycoords, start,1)
        #------------------------------------------------------------------- 
        Chart.update_all_freqs_sampl(self)
        #-------------------------------------------------------------------    


    def use_plot(self, plot):
        """Associate an existing Plot with this chart."""
        print('use_plot')
        plot.use_chart(self, len(self.plots))
        assert plot not in self.plots
        self.plots.append(plot)

    # asociations for creating bindings
    bindings = (('<Configure>', on_resize),
                ('<Button-1>', on_motion),
                ('<B1-Motion>', on_motion),
                ('<Button-1>', on_button_down),
                ('<ButtonRelease-1>', on_button_up),
               )
    subscriptions = (('scale_mode', on_scale_mode),
                     ('running', on_running),
                     ('smoothing', on_smoothing),
                     ('freq_sample', on_freq_sample),
                     ('plot_size', on_plot_size),
                     ('plot_type', on_plot_type),
                     ('scroll', on_scroll),
                     ('man_base', on_man_base),
                     ('man_range', on_man_range),
                     ('multi_scale', on_multi),
                     ('show_points', on_show_points),
                     ('unshow_points', on_unshow_points),
                     ('focus', on_focus),
                    )

    # member function tables indexed by plot type
    func_draw_x = (\
        draw_x_lines_samples,
        0,
        draw_x_lines_freqs,
    )
    func_update = (\
        update_all_samples,
        0,
        update_all_freqs,
    )
