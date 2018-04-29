#!/usr/bin/python
from functools import partial
import multiprocessing
import os
import sys
import time
if sys.version_info[0] == 3:
    import tkinter as tk
    import tkinter.filedialog as tkFileDialog
    import tkinter.messagebox as tkMessageBox
else:
    import Tkinter as tk
    import tkFileDialog
    import tkMessageBox

import chart as chart_
import config
import pubsub
import HMC5983
import sourcedlg
import utils
import serial
from datetime import datetime
import pyscreenshot as ImageGrab
#import wx
#from pywin32 import * 
#import win32ui, win32gui, win32con, win32api
#from dialogListWindows import dialogListWindows

#==== product identification ====
PRODUCT = 'magnetometer'
MAJOR = 0
MINOR = '1'
BETA = 1
VERSION = '%d.%s' % (MAJOR, MINOR)
if BETA:
    VERSION = '%sb%d' % (VERSION, BETA)
IDENTITY = '%s %s' % (PRODUCT, VERSION)


TITLE = PRODUCT + ' %s'
DATADIR = 'data'
CONFIG = 'magnetometer.cfg'
NWE = tk.N + tk.E + tk.W
PADX = 5
PADY = 5
QUEUE_SIZE = 2 # size of FIFO queue
filetypes = (('CSV files', '*.csv'), ('All files', '*.*'), )
shift = 0
left_btn = 0

BASE_MAX = 100
SPAN_MAX = 100
SMOOTHING_MIN = 1
SMOOTHING_MAX = 100
FREQSAMPLE_MIN = 1
FREQSAMPLE_MAX = 60
SAMPLESCALE_MIN = 100
SAMPLESCALE_MAX = 22000
FREQSCALE_MIN = 10
FREQSCALE_MAX = 120
MinSize=100

def unique_filename(file_name):
    """Generate a unique file name based on the one supplied."""
    counter = 1
    base, ext = os.path.splitext(file_name)
    while os.path.lexists(file_name):
        file_name = '%s_%d%s' % (base, counter, ext)
        counter += 1
    return file_name


def on_button(event):
    """Callback to record shift and button state when L.click on a widget."""
    global shift, left_btn
    shift = event.state & 1
    left_btn = not event.state & 0x100


def check_state(widget):
    """Record states when a widget is clicked."""

    widget.bind('<Button-1>', on_button)
    widget.bind('<ButtonRelease-1>', on_button)


class Slider(tk.Scale):
    """A tk Scale object that only generates events from user actions."""

    def __init__(self, parent, **options):
        self.btn_down = False
        self.cmd = options['command']
        options['command'] = self.command
        tk.Scale.__init__(self, parent, **options)
        check_state(self)

    def command(self, data):
        if left_btn:
            return self.cmd(data)


class App(tk.Frame):
    COLORS = ["black", "red", "#080", "blue", "#800", "#880", "#a35", "#5f2"]
    SETUP, HMC5983, CLOSING = list(range(3))
    states = ['setup', 'HMC5983', 'closing']
    running_text = ['Run', 'Pause']
    AUTO, NONE, MANUAL = list(range(3)) # scale modes
    plot_types = (\
        (config.SAMPLES, 'Samples', 'help'),
        (config.FREQS, 'Spectrum', 'help'))
    DEFAULT_SCALE_MODE = AUTO
    DEFAULT_MAN_BASE = 1000
    DEFAULT_MAN_RANGE = 1000
    load_dir = os.path.join(os.path.split(sys.argv[0])[0], DATADIR)

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.path = os.path.split(sys.argv[0])[0]
        self.data_dir = os.path.join(self.path, DATADIR)
        self.cfg = config.Load(os.path.join(self.data_dir, CONFIG))
        self.grid(sticky=tk.NSEW)
        self.idle_calls = 0
        self.charts = [] 
        self.focus_chart = None
        self.q = multiprocessing.Queue(maxsize=QUEUE_SIZE)
        self.status_q = multiprocessing.Queue(0)
        self.next_color = 0
        self.running = 1
        self.proc = None
        self.state = App.SETUP
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.man_span = 0
        self.scaling = config.ScaleInfo()
        self.spans = [0] * SPAN_MAX # map range slider to range value
        self.time_diff = time.time() - utils.timer() # see module docstring
        top = self.winfo_toplevel()
        top.geometry(self.cfg.geometry)
        try:
            top.wm_iconbitmap('magnetometer.ico')
        except:
            pass
        top.rowconfigure(0, weight=1)
        top.columnconfigure(0, weight=1)
        self.scale_min = (SAMPLESCALE_MIN, 0, FREQSCALE_MIN)
        self.scale_max = (SAMPLESCALE_MAX, 0, FREQSCALE_MAX)
        self.plot_sizes = [SAMPLESCALE_MAX,
                           0,
                           FREQSCALE_MAX]

        # the layout is 3 rows:
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1000)
        self.rowconfigure(2, weight=1)
        # row 1 is constructed as 2 columns, with all the expansion
        # assigned to the graphs
        self.columnconfigure(0, weight=1000)
        self.columnconfigure(1, weight=1)

        # construct the widgets - note that these member functions know where
        # they belong in the grid, so they are sensitive to grid layout changes
        self.create_menu(self)
        self.create_controls(self)
        self.create_graphs(self)
        self.create_button_row(self)

        # connect event handlers
        top.protocol("WM_DELETE_WINDOW", self.on_quit)
        pubsub.subscribe('status', self.set_status)
        pubsub.subscribe('focus2', self.on_focus)

        # start a process to receive and buffer data
        self.start_source(self.cfg.sources)

        self.on_timer()
        # start the code that processes and displays the data
        self.after_idle(self.on_plot_type)
        self.after_idle(self.read_queue)


    def add_chart(self):
        """Add a chart to the application."""
        _row = len(self.charts)
        new_chart = chart_.Chart(self.chart_frame, self.running)
        new_chart.grid(row=_row, column=0, sticky=tk.NSEW)
        self.charts.append(new_chart)
        pubsub.publish('focus', new_chart)
        self.focus_chart = new_chart
        # allow charts to expand vertically
        # (horizontal expansion has already been set)
        self.chart_frame.rowconfigure(_row, weight=3)
        return new_chart

    def create_button_row(self, master):
        # construct a frame to hold buttons at bottom
        frame = tk.Frame(master)
        frame.grid(row=2, column=0, sticky=tk.S+tk.E+tk.W, columnspan=2)
        frame.columnconfigure(0, weight=1)

        # add status fields
        self.status = []
        for n in range(3):
            ctl = tk.Label(frame, bd=1, relief=tk.SUNKEN)
            ctl.grid(row=0, column=n, sticky=tk.W, ipadx=6)
            self.status.append(ctl)

        # add exit button
        btn = tk.Button(frame, text='Exit', command=self.on_quit)
        btn.grid(row=0, column=n+1, sticky=tk.E,
                 padx=PADX, pady=PADY, ipadx=10)        


    def create_controls(self, master):
        """Make a Frame to hold the controls in a vertical column at right."""
        ctrl_col = tk.Frame(master)
        ctrl_col.grid(row=1, column=1, sticky=tk.NW)        

        row=0

        self.btn_running = tk.Button(ctrl_col)
        self.btn_running["text"] = App.running_text[self.running]
        self.btn_running["command"] = self.on_run
        self.btn_running.grid(row=row, sticky=tk.NW, padx=PADX, pady=PADY,
                              ipadx=10)
        self.btn_screenshot = tk.Button(ctrl_col)
        self.btn_screenshot["text"] = 'PrtScr'
        self.btn_screenshot["command"] = self.on_screenshot
        self.btn_screenshot.grid(row=row, sticky=tk.E, padx=PADX, pady=PADY,
                              ipadx=10)
        row += 1
 

        self.sub_frame = tk.Frame(ctrl_col, bd=1, relief=tk.SUNKEN)
        self.sub_frame.grid(row=row, sticky=tk.NW, padx=PADX, pady=PADY)
        for n in range(2):
            self.sub_frame.columnconfigure(n, minsize=MinSize)
        """Create scaling controls in the supplied frame."""
        # add labels to describe the sliders
        c = tk.Label(self.sub_frame, text="HMC5983 controls:")
        c.grid(row=row, sticky=tk.EW, columnspan=2)
        row += 1
        self.use_81Gs = self.cfg._81Gs
        self._81Gs = tk.IntVar()
        self._81Gs.set(self.use_81Gs)
        #c_81Gs = tk.Checkbutton(ctrl_col, text="8.1 Gs", variable=self._81Gs,
        c_81Gs = tk.Checkbutton(self.sub_frame, text="8.1 Gs", variable=self._81Gs,
                           command=self.on_81Gs)
        c_81Gs.grid(row=row, column=0, sticky=tk.NW, padx=PADX)
        if self.use_81Gs :
            self.parent_conn.send(['on_81Gs',self.cfg.calc_81Gs])

        row += 1
        
        self.use_088Gs = self.cfg._088Gs
        self._088Gs = tk.IntVar()
        self._088Gs.set(self.use_088Gs)
        #c_088Gs = tk.Checkbutton(ctrl_col, text="0.88 Gs", variable=self._088Gs,
        c_088Gs = tk.Checkbutton(self.sub_frame, text="0.88 Gs", variable=self._088Gs,
                           command=self.on_088Gs)
        c_088Gs.grid(row=row, column = 0, sticky=tk.NW, padx=PADX)
        if self.use_088Gs :
            self.parent_conn.send(['on_088Gs',self.cfg.calc_088Gs])


        row += 1
        
        #======================================================================
        # construct a sub-frame to hold scaling controls
        self.sub_frame = tk.Frame(ctrl_col, bd=1, relief=tk.SUNKEN)
        self.sub_frame.grid(row=row, sticky=tk.NW, padx=PADX, pady=PADY)
        for n in range(2):
            self.sub_frame.columnconfigure(n, minsize=MinSize)
        row += 1
        # add frequency controls to frame, then remove them
        self.create_freq(self.sub_frame)
        for slave in self.freq_ctls:
            slave.grid_remove()
        # add scaling controls to frame
        self.create_scaling(self.sub_frame)
        #======================================================================

        self.smoothing = Slider(ctrl_col,
                                from_=SMOOTHING_MIN,
                                to=SMOOTHING_MAX,
                                length=MinSize*2,
                                orient=tk.HORIZONTAL,
                                label='Smoothing',
                                state= 'normal',
                                activebackground="#00ff00",
                                command=self.on_smoothing)
        self.smoothing.grid(row=row, column=0)
        self.smoothing.set(self.cfg.smoothing)

        if (self.cfg.plot_type == 2) :
            self.smoothing.grid_remove()

        row += 1

        self.plot_type = tk.IntVar()
        self.plot_type.set(self.cfg.plot_type)
        self.x_scale = tk.Scale(ctrl_col,
                     length=MinSize*2,
                     orient=tk.HORIZONTAL,
                     command=self.on_plot_size)
        self.x_scale.grid(row=row, column=0)
        row += 1

        # add radio buttons to choose the x-axis meaning
        for mode, text, tip in App.plot_types:
            c = tk.Radiobutton(ctrl_col, text=text,
                               variable=self.plot_type,
                               value=mode, command=self.on_plot_type)
            check_state(c)
            c.grid(row=row, sticky=tk.NW, padx=PADX, pady=0, columnspan=2)
            row += 1

    def create_freq(self, frame):
        """Create frequency controls in the supplied frame."""
        row = 0

        # add labels to describe the sliders
        c = tk.Label(frame, text="PSD controls:")
        c.grid(row=row, sticky=tk.EW)
        row += 1

        c = Slider(frame,
                   from_=FREQSAMPLE_MIN,
                   to=FREQSAMPLE_MAX,
                   length=MinSize*2-10,
                   orient=tk.HORIZONTAL,
                   label='Sample size (secs.)',
                   command=self.on_freq_sample)
        c.grid(row=row)
        c.set(self.cfg.freq_sample)
        row += 1

        c = Slider(frame,
                   from_=0.0,
                   to=10.0,
                   resolution=0.5,
                   length=MinSize*2-10,
                   orient=tk.HORIZONTAL,
                   label='High pass (Hz)',
                   command=self.on_hi_pass)
        c.grid(row=row)
        c.set(self.cfg.hi_pass)
        row += 1
        self.nt_dB_var = tk.IntVar()
        self.dB_type = tk.IntVar()
        self.nt_type = tk.IntVar()
        self.nt_dB_type = tk.IntVar()
        self.nt_dB_type = self.cfg.nt_dB_type

        #if self.cfg.nt_dB_type :
        #    self.dB_type = 1
        #    self.nt_type = 0
        #else :
        #    self.dB_type = 0
        #    self.nt_type = 1

        #print(self.cfg.nt_dB_type)
        self.c_dB = tk.Radiobutton(frame, text='dB/Hz',
                            variable=self.nt_dB_var,
                            value=3, command=self.on_nT_dB)
        #check_state(c_dB)
        self.c_dB.grid(row=row, sticky=tk.NW, padx=PADX, pady=0, columnspan=2)

        row += 1
        self.c_nT = tk.Radiobutton(frame, text='nT/Hz',
                            variable=self.nt_dB_var,
                            value=2, command=self.on_nT_dB
                            #,indicatoron= False
                            )
        #check_state(c_nT)
        self.c_nT.grid(row=row, sticky=tk.NW, padx=PADX, pady=0, columnspan=2)

        # make a note of all the controls so we can later remove/restore them
        self.freq_ctls = frame.grid_slaves()
        if (self.cfg.nt_dB_type == 2) :  
            self.c_dB.deselect()
            self.c_nT.select()
        if (self.cfg.nt_dB_type == 3) :  
            self.c_dB.select()
            self.c_nT.deselect()

    def create_graphs(self, master):
        """Make a Frame to hold the graphs (Canvas objects, see chart.py)."""
        self.chart_frame = tk.Frame(master, padx=PADX, pady=PADY)
        self.chart_frame.grid(row=1, column=0, sticky=tk.NSEW)

        # Allow charts to expand horizontally. (Vertical expansion will be
        # applied when the individual charts are constructed.)
        self.chart_frame.columnconfigure(0, weight=1)

        self.scrollbar = tk.Scrollbar(self.chart_frame,
                                      orient=tk.HORIZONTAL,
                                      command=self.on_scroll)
        self.scrollbar.grid(row=99, column=0, sticky=tk.EW)
        self.scrollbar.set(0.0, 1.0)

    def create_menu(self, master):
        """Make a Frame to hold the menu in a horizontal row at the top."""
        self.menu_bar = tk.Frame(master, relief=tk.RAISED, bd=2)
        self.menu_bar.grid(row=0, column=0, sticky=NWE, columnspan=2)

        mbutton = tk.Menubutton(self.menu_bar, text='File', underline=0)
        mbutton.pack(side=tk.LEFT)
        menu = tk.Menu(mbutton, tearoff=0)
        menu.add_command(label='Save', command=self.on_save)
        menu.add_command(label='Save as', command=self.on_save_as)
        menu.add_command(label='Plot CSV', command=self.on_load_csv)
        menu.add_command(label='Settings', command=self.on_setting)
        menu.add_command(label='Quit', command=self.on_quit)
        mbutton['menu'] = menu
        self.fmenu = menu

        mbutton = tk.Menubutton(self.menu_bar, text='Help', underline=0)
        mbutton.pack(side=tk.LEFT)
        menu = tk.Menu(mbutton, tearoff=0)
        menu.add_command(label='About', command=self.on_about)
        mbutton['menu'] = menu

    def create_scaling(self, frame):
        """Create scaling controls in the supplied frame."""
        row = 0

        # add labels to describe the sliders
        c = tk.Label(frame, text="Scaling controls:")
        c.grid(row=row, sticky=tk.EW, columnspan=2)
        row += 1

        # add radio buttons to choose the type of scaling
        self.scale_mode = tk.IntVar()

        c = tk.Radiobutton(frame, text='Auto',
                            variable=self.scale_mode,
                            value=App.AUTO, command=self.on_scale_mode)
        check_state(c)
        c.grid(row=row, sticky=tk.NW, padx=PADX, pady=0, columnspan=2)
        row += 1

        c = tk.Radiobutton(frame, text='Manual',
                            variable=self.scale_mode,
                            value=App.MANUAL, command=self.on_scale_mode)
        check_state(c)
        c.grid(row=row, sticky=tk.NW, padx=PADX, pady=0, columnspan=2)
        row += 1
        row += 1

        # add radio buttons to choose auto/sticky manual scaling
        self.sticky = tk.IntVar()
        for mode, text in ((0, 'All'), (1, 'Smoothing')):
            c = tk.Radiobutton(frame, text=text,
                               variable=self.sticky,
                               value=mode, command=self.on_sticky)
            c.grid(row=row-3, column=1, sticky=tk.NW, padx=PADX, pady=0)
            row += 1
        self.sticky.set(self.cfg.manual_sticky)        

        # add sliders to control manual scaling
        self.man_base = Slider(frame, from_=BASE_MAX, to=1,
                               length=150,
                               command=self.on_man_base)
        self.man_base.grid(row=row, column=0, sticky=tk.NW)
        self.man_range = Slider(frame, from_=SPAN_MAX, to=1,
                                length=150,
                                command=self.on_man_range)
        self.man_range.grid(row=row, column=1, sticky=tk.NW)
        row += 1

        # add labels to describe the sliders
        c = tk.Label(frame, text="Base")
        c.grid(row=row, column=0, sticky=tk.EW)
        c = tk.Label(frame, text="Range")
        c.grid(row=row, column=1, sticky=tk.EW)
        row += 1
        self.base_label = tk.Label(frame)
        self.base_label.grid(row=row, column=0, sticky=tk.EW)
        self.range_label = tk.Label(frame)
        self.range_label.grid(row=row, column=1, sticky=tk.EW)
        row += 1
        # make a note of all the controls so we can later remove/restore them
        self.scale_ctls = frame.grid_slaves()

        # make a "clicked radiobutton" call to set state of sliders
        self.on_scale_mode()

    def base2slider(self, base):
        """Convert manual base value to slider value."""
        if self.scaling.base_min == self.scaling.base_max:
            return 1
        # force into valid range
        base = max(self.scaling.base_min, base)
        base = min(self.scaling.base_max, base)
        base -= self.scaling.base_min
        base /= float(self.scaling.base_max - self.scaling.base_min)
        base *= BASE_MAX
        return base + 1

    def find_chart(self, _id):
        """Find the chart that holds Plot with _id."""
        for chart in self.charts:
            #print(chart.plots)
            for plot in chart.plots:
                plot.label = 'nT'
                if _id == plot.id:
                    return chart

    def flush_queue(self):
        while self.parent_conn.poll():
            self.parent_conn.recv()

    def get_chart(self, _id):
        """Get or create the chart containing the plot identified as <_id>."""
        chart = self.find_chart(_id)
        #print(chart)
        if not chart:
            # determine if we need to construct a new chart
            single_chart_exists = bool(self.charts) 
            if single_chart_exists:
                chart = self.charts[0]
            else:
                chart = self.add_chart()
            # we don't have a buffer for this id, so construct one
            plot = chart.add_plot(_id, App.COLORS[self.next_color])
            #plot.label = 'nT             '
            #print('plot.label')


            self.next_color += 1
            self.next_color %= len(App.COLORS)


            if not single_chart_exists:
                self.set_scaling(chart)

                _dict = self.cfg.scale_settings
 
                mode = self.scaling.mode
                pubsub.publish('scale_mode', mode, False)
                self.scale_mode.set(mode)
                self.set_scaling(chart)

        #else:
        return chart

    def get_data_size(self):
        """Get the total size of the data in the active plot.

        Units returned will depend on the plot type.
        """
        if self.focus_chart:
            plot = self.focus_chart.plots[0]
            if self.plot_type.get() != config.SAMPLES:
                return plot.get_time_duration()
            else:
                return plot.count
        else:
            return 0

    def get_scaleinfo_or_new(self):
        """Set up the ScaleInfo object for the current chart, or a new one."""
        if self.focus_chart:
            plots = self.focus_chart.plots
            if plots:
                name = plots[0].label
                d = self.cfg.scale_settings
                if name in d:
                    self.scaling = d[name]
                return True
        self.scaling = config.ScaleInfo()
        return False

    def on_about(self):
        tkMessageBox.showinfo('About', IDENTITY)


    def on_focus(self, chart):
        """Focus has been set to a chart."""
        old_chart = self.focus_chart
        if old_chart and\
           old_chart.plots and\
           old_chart.scale_mode == App.MANUAL:
            # save old values into config dictionary
            self.scaling.mode = self.scale_mode.get()
            self.scaling.base = self.slider2base(self.man_base.get())
            # base_min/max should already be set in here
            index = self.man_range.get()
            self.scaling.range = self.spans[int(index)]
            name = old_chart.plots[0].label

        # keep track of which chart has focus
        self.focus_chart = chart
        self.get_scaleinfo_or_new()
        plot_type = chart.plot_type
        self.scale_mode.set(chart.scale_mode)
        self.plot_type.set(plot_type)
        self.on_plot_type()

    def on_freq_sample(self, data):
        """The smoothing slider has changed.

        Its meaning varies with plot type.
        """
        data = int(data)
        self.cfg.freq_sample = data
        pubsub.publish('freq_sample', data)
        if not self.running:
            self.update_charts()


    def on_hi_pass(self, data):
        """The hi-pass slider has changed."""
        self.cfg.hi_pass = float(data)



    def on_man_base(self, data):
        """The manual-scaling base slider has been changed."""

        # convert the slider value to the range we want
        base = self.slider2base(data)
        # save it in the configuration file
        self.save_scale_setting('base', base)

        if self.scale_mode.get() != App.MANUAL:
            self.scale_mode.set(App.MANUAL)
            self.on_scale_mode()
        # display the value to the user
        self.base_label['text'] = str(base)
        start = self.scrollbar.get()[0]
        pubsub.publish('man_base', base, start, shift)

    def on_man_range(self, data):
        """The manual-scaling scale slider has been changed."""

        # convert the slider value to the range we want
        if self.man_span:
            # see on_scale_mode() for an explanation
            span = self.man_span
            self.man_span = 0
        else:
            span = self.spans[int(data) - 1]
        # save it in the configuration file
        self.save_scale_setting('range', span)

        if self.scale_mode.get() != App.MANUAL:
            self.scale_mode.set(App.MANUAL)
            self.on_scale_mode()
        # display the value to the user
        self.range_label['text'] = str(span)
        # tell the charts
        start = self.scrollbar.get()[0]
        #pubsub.publish('man_range', span, start, shift, False)
        pubsub.publish('man_range', span, start, shift)

    def on_81Gs(self):

        self._81Gs.set(True)
        self.use_81Gs = self._81Gs.get()
        self.cfg._81Gs = self.use_81Gs
        self._088Gs.set(False)
        self.cfg._088Gs = self._088Gs.get()
        self.parent_conn.send(['on_81Gs',self.cfg.calc_81Gs])

    def on_088Gs(self):

        self._088Gs.set(True)
        self.use_088Gs = self._088Gs.get()
        self.cfg._088Gs = self.use_088Gs
        self._81Gs.set(False)
        self.cfg._81Gs = self._81Gs.get()
        self.parent_conn.send(['on_088Gs',self.cfg.calc_088Gs])

    def on_plot_size(self, data):
        """The slider for horizontal scaling has changed."""
        #print('on_plot1_size')
        plot_type = self.plot_type.get()
        plot_size = int(data)
        self.plot_sizes[plot_type] = plot_size
        data_size = self.get_data_size()
        if data_size:
            lo, hi = self.scrollbar.get()
            if plot_type != config.FREQS:

                # the thumb of the horizontal scrollbar must change to
                # represent the portion of data that is visible on screen
                if data_size > plot_size:
                    # we have more data than can will fit on the chart
                    old_sz = hi - lo
                    new_sz = float(plot_size) / data_size
                    delta = new_sz - old_sz
                    if hi == 1.0:
                        # old thumb was at right, so just amend its start
                        lo -= delta
                    else:
                        # amend thumb so current data wll remain centered
                        lo -= delta / 2
                        hi += delta / 2
                    # handle out-of-range conditions
                    if lo < 0.0:
                        lo = 0.0
                        hi = lo + new_sz
                    if hi > 1.0:
                        hi = 1.0
                        lo = hi - new_sz
                else:
                    # all data fits on the chart, so scrollbar is inactive
                    lo = 0.0
                    hi = 1.0
                self.scrollbar.set(lo, hi)
            pubsub.publish('plot_size', plot_size, plot_type)
            pubsub.publish('scroll', lo)

    def on_plot_type(self):
        """Meaning of x-axis has changed."""
        plot_type = self.plot_type.get()

        if (plot_type == config.FREQS) :
            self.smoothing.grid_remove()
        else :    
            self.smoothing.grid()


        # Are we changing between a frequency plot and a non-frequency plot?
        # If so, change the visible controls.
        if plot_type == config.FREQS:
            ctls = self.freq_ctls

        elif self.cfg.plot_type == config.FREQS:
            ctls = self.scale_ctls
        else:
            ctls = None
        if ctls:
            self.sub_frame.grid_propagate(False)
            # remove the existing controls
            for slave in self.sub_frame.grid_slaves():
                slave.grid_remove()
            # restore the required controls
            for ctl in ctls:
                ctl.grid()

        self.cfg.plot_type = plot_type

        # change the scale limits
        fr_ = self.scale_min[plot_type]
        to_ = self.scale_max[plot_type]

        if (plot_type == config.FREQS) :

            self.x_scale.configure(from_=fr_, to=to_,
                                   resolution=fr_,
                                   label='Hz')
        else :
            self.x_scale.configure(from_=fr_, to=to_,
                                   resolution=fr_,
                                   label='Samples')
        plot_size = self.plot_sizes[plot_type]
        self.x_scale.set(plot_size)
        pubsub.publish('plot_type', plot_type, shift)

    def on_nT_dB(self):
        """Meaning of y-axis has changed."""
        chart = self.get_chart(1)
        plot_type = self.plot_type.get()
        self.cfg.nt_dB_type =  self.nt_dB_var.get()
        chart.label_nT_dB_Hz_PSD()
        if (self.cfg.nt_dB_type == 2) :  
            self.c_dB.deselect()
            self.c_nT.select()
        if (self.cfg.nt_dB_type == 3) :  
            self.c_dB.select()
            self.c_nT.deselect()
        #Plot.set_label(self, plot_type)            
   
        #nt_dB_type = self.nt_dB_type.get()

        #self.cfg.plot_type = plot_type
        #pubsub.publish('plot_type', plot_type, shift)

    def on_quit(self):
        """Application is closing."""
        self.state = App.CLOSING
        # terminate any running process
        self.parent_conn.send('STOP')
        # update configuration values
        top = self.winfo_toplevel()
        self.cfg.geometry = top.geometry()
        config.Save(self.cfg)
        # close the app
        top.destroy()


    def on_screenshot(self):
        self.on_run()
        #self.set_run_state(0)

        datetim = str(datetime.now())
        year = datetim[0:4]
        month = datetim[5:7]
        day = datetim[8:10]
        hour = datetim[11:13]
        minute = datetim[14:16]
        secund = datetim[17:19]
        name = '%s_%s_%s_%s_%s_%s.png' % (year, month, day, hour, minute, secund)
        upath = os.path.join(self.data_dir, name)
        #print(datetim)
        #print(upath)
        
        if __name__ == "__main__":
            top = self.winfo_toplevel()
            x2 = top.winfo_width() #width in pixels
            y2 = top.winfo_height() #height in pixels
            x1 = top.winfo_x() # left corner
            y1 = top.winfo_y() # left corner
            im=ImageGrab.grab(bbox=(x1, y1, (x1 + x2 + 10), (y1 + y2 +30))) # X1,Y1,X2,Y2
            im.save(upath)
        
        #self.set_run_state(1)
            #im.show()
        #time.sleep(4) # seconds
        #self.on_run()

    def on_run(self):
        # toggle the running state
        self.set_run_state(self.running ^ 1)
        self.parent_conn.send(['RUN', self.running])
        if not self.running:
            # flush the queue - needed for FILE/FREQ to stop queued values
            while self.parent_conn.poll():
                self.parent_conn.recv()

    def on_load_csv(self):
        files = tkFileDialog.askopenfilename(parent=self,
                                            defaultextension='txt',
                                            initialdir=app.load_dir,
                                            filetypes=filetypes,
                                            multiple=True,
                                            title='Choose file scv to plot png')
        if files:
            old_state = self.running
            if old_state:
                self.set_run_state(0)
            for chart in self.charts:
                for plot in chart.plots:
                    try:
                        plot.plot_csv_to_png(files[0])
                    except:
                        msg = 'Could not save plot because:\n%s\n%s' %\
                            (str(sys.exc_info()[0]),
                             str(sys.exc_info()[1]))
                        tkMessageBox.showerror('Save Error', msg)
            if old_state:
                self.set_run_state(1)

    def on_save(self, save_as=False):
        old_state = self.running
        if old_state:
            self.set_run_state(0)
        ufiles = []
        for chart in self.charts:
            for plot in chart.plots:
                # The plot id could be an integer from HMC5983 or a path + file.
                # Create a suitable filename.
                if isinstance(plot.id, int):
                    datetim = str(datetime.now())
                    year = datetim[0:4]
                    month = datetim[5:7]
                    day = datetim[8:10]
                    hour = datetim[11:13]
                    minute = datetim[14:16]
                    name = '%s%s%s%s%s_HMC5983_MAG_1M_data.csv' % (year, month, day, hour, minute) 
                else:
                    name = os.path.split(plot.id)[1]
                    if not name.lower().endswith('.txt'):
                        name += '.txt'
                try:
                    if save_as:
                        options = {}
                        options['filetypes'] = [('all files', '.*'), ('text files', '.txt')]
                        options['initialfile'] = name
                        options['parent'] = self
                        upath = tkFileDialog.asksaveasfilename(**options)
                        if not upath:
                            return
                        ufile = os.path.split(upath)[1]
                    else:
                        #name = 'SAVED_' + name
                        ufile = unique_filename(name)
                        upath = os.path.join(self.data_dir, ufile)
                    plot.save_csv(upath)
                    ufiles.append(ufile)
                except:
                    msg = 'Could not save plot because:\n%s\n%s' %\
                        (str(sys.exc_info()[0]),
                         str(sys.exc_info()[1]))
                    tkMessageBox.showerror('Save Error', msg)
        #if ufiles:
        #    msg = 'Plots\n   %s\nsaved in "%s"' % ('\n   '.join(ufiles), self.data_dir)
        #    tkMessageBox.showinfo('Files saved', msg)
        if old_state:
            self.set_run_state(1)

    def on_save_as(self):
        self.on_save(True)

    def on_scale_mode(self):
        """Scaling mode has changed."""
        # get value from radio buttons and save it
        mode = self.scale_mode.get()
        if not self.focus_chart or not self.focus_chart.plots:
            return

        # record the new mode for this plot
        self.save_scale_setting('mode', mode)

        pubsub.publish('scale_mode', mode, shift)
        self.set_scaling(self.focus_chart)
        if not self.running:
            self.update_charts()

    def on_scroll(self, cmd, value, units=''):
        """The horizontal scrollbar has changed."""
        if cmd == 'scroll':
            lo, hi = self.scrollbar.get()
            if int(value) < 0:
                delta = -min(lo, 0.05)
            else:
                delta = min(1.0 - hi, 0.05)
            self.scrollbar.set(lo + delta, hi + delta)
        elif cmd == 'moveto':
            value = float(value)
            lo, hi = self.scrollbar.get()
            self.scrollbar.set(value, value + hi - lo)

        # if we're running, change state to paused
        if self.running:
            self.set_run_state(0)
        pubsub.publish('scroll', lo)


    def on_smoothing(self, data):
        """The smoothing slider has changed."""
        data = int(data)
        self.cfg.smoothing = data
        pubsub.publish('smoothing', data)
        if not self.running:
            self.update_charts()

    def on_setting(self):
        """Edit the list of sources and use the changed value."""
        sources = self.cfg.sources
        # the choices of source offered to the user in the dialog are blank
        # (to deselect the source) and all possible states except for SETUP
        # and CLOSING
        choices = [''] + App.states[1:-1]
        dlg = sourcedlg.SourceDlg(self, sources, choices)
        if dlg.sources:
            self.cfg.sources = dlg.sources
            self.start_source(dlg.sources)

    def on_sticky(self):
        """Manual scaling stickiness mode has changed; save state."""
        self.cfg.manual_sticky = self.sticky.get()

    def on_timer(self):
        """Event that runs approximately every 1/5 second."""
        while not self.status_q.empty():
            text = self.status_q.get()
            self.status[0].config(text=text)

        if self.focus_chart and self.focus_chart.plots:
            plot = self.focus_chart.plots[0]
            s = 'Total: %d' % plot.total
            self.status[2].config(text=s)

        # set the horizontal scrollbar to represent the amount of visible data
        if self.running and self.charts:
            plot_type = self.plot_type.get()
            plot_size = self.plot_sizes[plot_type]
            data_size = self.get_data_size()
            if data_size > plot_size:
                # we have more data than can will fit on the chart
                lo = 1.0 - float(plot_size) / data_size
            else:
                # all data fits on the chart, so scrollbar is inactive
                lo = 0.0
            self.scrollbar.set(lo, 1.0)

        self.read_queue()
        self.after(self.cfg.refresh_rate, self.on_timer)


    def read_queue(self):
        """Read and display data from process.

        Called from timer. Runs in top-level process.
        """
        try:
            # flush data in pipe, accumulating data for each channel
            channels = {}
            while self.parent_conn.poll():
                data = self.parent_conn.recv()
                # data can be either of:
                #   string:    status message OR command
                #   3-list:    id, duration, values
                if isinstance(data, str):
                    if data == 'STOP':
                        print('STOP rx by app')
                        self.stop_source()
                        self.set_state(App.SETUP)
                    else:
                        self.set_status(data)
                else:
                    id_, duration, values = data
                    if id_ not in channels:
                        channels[id_] = [duration, values]
                    else:
                        channels[id_][0] += duration
                        channels[id_][1] += values

            if not self.running :
                    return

            # display data
            if channels:
                static = not self.running and False
                for _id, (duration, values) in list(channels.items()):
                    chart = self.get_chart(_id)
                    # display data on chart
                    chart.plot(_id, duration, values, static)
                    # show data rate for active chart
                    if chart is self.focus_chart:
                        s = '%.f Hz' % (len(values) / duration)
                        self.status[1].config(text=s)
                #print('read_queue') 
                for chart in self.charts:
                    chart.update_all()
        except:
            print(sys.exc_info()[0], sys.exc_info()[1])

    def remove_charts(self):
        while self.charts:
            chart = self.charts.pop()
            self.chart_frame.rowconfigure(len(self.charts), weight=0)
            chart.unlink()
            chart.destroy()
        self.next_color = 0

    def save_scale_setting(self, attr, value):
        """Save a scale setting for the current plot."""
        setattr(self.scaling, attr, value)

    def set_run_state(self, state):
        # save the running state
        self.running = state
        # get text description of the /other/ state
        text = App.running_text[state]
        # change the button text
        self.btn_running["text"] = text
        # tell the world about the change
        pubsub.publish('running', state)

    def set_scaling(self, chart):
        """Set scaling controls for the supplied chart."""
        if self.scale_mode.get() == App.MANUAL:
            found = False

            # if settings exist for this chart, use them
            if chart.plots:
                name = chart.plots[0].label
                d = self.cfg.scale_settings
                if name in d:
                    found = True
                    self.scaling = d[name]
            if not found:
                # use values from existing chart
                # because no plot or settings not saved
                _range = chart.ymax - chart.ymin
                self.scaling = config.ScaleInfo()
                d[name] = self.scaling
                if _range:
                    self.scaling.base = chart.ymin
                    self.scaling.base_min = min(self.scaling.base, 0)
                    self.scaling.base_max = chart.ymax
                    self.scaling.range = int(_range * 1.1)

            # set any new values into controls and inform the chart
            self.set_scaling_values()

        if not self.running:
            self.update_charts()

    def set_scaling_values(self):
        """Set up scaling values for base and span."""

        # set base value into control
        base = self.scaling.base
        start = self.scrollbar.get()[0]
        self.man_base.set(self.base2slider(base))
        # display the value to the user
        self.base_label['text'] = str(base)
        pubsub.publish('man_base', base, start, shift)

        # set up range control
        _range = self.scaling.range
        # generate a log scale for the range
        span = max(_range / 100.0, 10.0)
        for n in range(SPAN_MAX - 1, -1, -1):
            self.spans[n] = int(round(span))
            span *= 1.1
        # map range to slider setting
        index = self.span2slider(_range)
        self.man_range.set(index)
        # display the value to the user
        self.range_label['text'] = str(_range)


    def set_state(self, state):
        """Set the program state."""
        self.state = state
        #self.set_run_state(int(state != App.FILE))
        self.set_run_state(1)
        self.winfo_toplevel().title(TITLE % App.states[state])

    def set_status(self, text):
        """Put status message onto a thread-safe queue.

        It is a pubsub listener. Mesages are pulled off the queue and displayed
        by the timer routine.
        """
        self.status_q.put(text)

    def show_data(self, _id, _data):
        """Display data pulled from the queue."""
        chart = self.get_chart(_id)
        # display data on chart
        chart.plot(_id, _data)

    def slider2base(self, slider):
        """Convert slider value to manual base value."""
        return int(float(int(slider) - 1) / BASE_MAX *\
                   (self.scaling.base_max - self.scaling.base_min)\
                   + self.scaling.base_min)

    def span2slider(self, span):
        """Given a span, return the closest slider index."""
        for ndx, v in enumerate(self.spans):
            if v <= span:
                break
        return ndx + 1

    def start_source(self, sources):
        """Parse the sources supplied and start input.

        Existing sources are cleaned up.
        The list of sources supplied is parsed for the first valid source.
        A process is started to receive and buffer data.
        """

        # close existing process
        self.stop_source()

        # start the process that gets data
        self.proc, state = HMC5983.start(self, DATADIR, sources)
        if not self.proc:
            self.set_status('WARNING: No valid data source found. Use File > Source')
        self.set_state(state)

        state = tk.NORMAL
        self.man_base['state'] = state

    def stop_source(self):
        """Stop any existing source."""
        self.flush_queue()
        if self.proc:
            self.parent_conn.send('STOP')
            self.proc.join()
            self.proc = None

        # remove existing plots
        # (this removes the plots but not the charts???)
        self.remove_charts()
        # flush any pending plots from the queue
        self.flush_queue()

    def update_charts(self):
        """Update all charts.

        When running, charts are updated every time data arrives, but
        when not running, it must be done manually.
        """
        start = self.scrollbar.get()[0]
        for c in self.charts:
            c.update_all(start)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
