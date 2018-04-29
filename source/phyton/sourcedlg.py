import csv
import sys
if sys.version_info[0] == 3:
    import tkinter as tk
else:
    import Tkinter as tk

PADX = 5
PADY = 5
PARAM_SIZE = 14
PARAM_MAX = 2
hint = """\
Choose the COM port & speed
"""


class Row(object):
    """Hold the widgets that describe a single source."""

    def __init__(self, frame, row, choices, top_cb):
        #print("row= ",row)

        self.row = row
        self.choices = choices
        self.top_cb = top_cb
        self.variable = tk.StringVar(frame)
        col = 0
        ctl = tk.OptionMenu(frame, self.variable, *choices)
        ctl.config(width=10)
        ctl.config(indicatoron=0)
        ctl.grid(row=row, column=col)
        col += 1
        self.ctls = []
        for n in range(PARAM_MAX):
            ctl = tk.Entry(frame, width=PARAM_SIZE)
            ctl.grid(row=row, column=col, sticky=tk.W, padx=PADX)
            col += 1
            self.ctls.append(ctl)
    def get_data(self):
        """Get data values from this row."""

        source = self.variable.get()
        if not source:
            return ''
        bits = [source]
        for ctl in self.ctls:
            s = ctl.get()
            if s:
                bits.append(s)
        return bits

    def set_data(self, source):
        """Set data values into this row."""
        # remove existing settings
        self.variable.set(self.choices[0])
        for ctl in self.ctls:
            ctl.delete(0, tk.END)

        for ndx, data in enumerate(source):
            if ndx == 0:
                # first data value is the type of the source
                if data in self.choices:
                    self.variable.set(data)
            else:
                # following data values are paraameters for this type
                if ndx <= PARAM_MAX:
                    ctl = self.ctls[ndx - 1]
                    ctl.insert(0, data)


class SourceDlg(tk.Toplevel):
    """Edit the data sources."""

    def __init__(self, parent, sources, choices):
        tk.Toplevel.__init__(self, parent)
        self.parent = parent
        self.sources = ''
        self.title('Set setting')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        row=0

        lbl = tk.Label(self, text=hint, justify=tk.LEFT)
        lbl.grid(row=row, sticky=tk.W, padx=PADX, pady=PADY, ipadx=10)
        row += 1

        ctrl_frame = tk.Frame(self)
        ctrl_frame.grid(row=row, padx=PADX, pady=PADY)
        row += 1
        # add captions to the data columns
        for col, caption in enumerate(('Source', 'COM port', 'speed')):
            lbl = tk.Label(ctrl_frame, text=caption, justify=tk.LEFT)
            lbl.grid(row=0, column=col)

        # construct data rows
        self.rows = [None]
        parts = next(csv.reader([sources]))
        parts = [x.strip('" ') for x in parts]
        subrow = 1
        while parts:
            name = parts.pop(0)
            if name in choices:
                params = [name]
                while parts and parts[0] not in choices:
                    params.append(parts.pop(0))
                r = Row(ctrl_frame, subrow, choices, self.on_top)
                r.set_data(params)
                self.rows.append(r)
                subrow += 1
        self.create_button_row(self, row)
        row += 1

        # Make it act like a reasonable dialog box. For why all this is needed,
        # see http://effbot.org/tkinterbook/tkinter-dialog-windows.htm
        self.grab_set()
        self.bind("<Return>", self.on_OK)
        self.bind("<Escape>", self.on_cancel)
        self.focus_set()
        self.wait_window(self)

    def create_button_row(self, parent, row):
        """Construct a frame to hold buttons at bottom."""
        frame = tk.Frame(parent)
        frame.grid(row=row, column=0, sticky=tk.S+tk.E+tk.W, columnspan=2)
        frame.columnconfigure(0, weight=1)

        self.status = tk.StringVar()
        ctl = tk.Label(frame, textvariable=self.status)
        ctl.grid(row=0, column=0, sticky=tk.W, padx=PADX)
        btn = tk.Button(frame, text='OK', command=self.on_OK)
        btn.grid(row=0, column=1, sticky=tk.E, padx=PADX, pady=PADY, ipadx=10)
        btn = tk.Button(frame, text='Cancel', command=self.on_cancel)
        btn.grid(row=0, column=2, sticky=tk.E, padx=PADX, pady=PADY, ipadx=10)

    def on_cancel(self, event=None):
        """Application is closing."""
        # put focus back to the parent window
        if self.parent:
            self.parent.focus_set()
        self.destroy()

    def on_OK(self, event=None):
        """Application is closing."""
        bits = []
        for row in self.rows:
            if row:
                s = row.get_data()
                if s:
                    bits.append(s.pop(0))
                while s:
                    bits.append('"%s"' % s.pop(0))
        self.sources = ', '.join(bits)
        self.on_cancel()

    def on_top(self, row):
        """Exchange the data values for row and row-1."""
        row1 = self.rows[1]
        row2 = self.rows[row]
        data1 = row1.get_data()
        data2 = row2.get_data()
        row1.set_data(data2)
        row2.set_data(data1)


if __name__ == '__main__':
    src_data = 'HMC5983, COM3,38400'
    choices = ['HMC5983']
    app = SourceDlg(None, src_data, choices)
    app.mainloop()
