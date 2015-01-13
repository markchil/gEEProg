#!/usr/bin/env python

# Copyright 2014 Mark Chilenski
# This program is distributed under the terms of the GNU General Purpose License (GPL).
# Refer to http://www.gnu.org/licenses/gpl.txt

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
# 
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
# 
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division

import Tkinter as tk
import tkFont
import tkFileDialog
import string
import serial
import serial.tools.list_ports
import time
import gEEProg
import os.path
import sys
import warnings
import webbrowser

__version__ = '1.0'

NULL_PORT_NAME = "disconnected"
SERIAL_TIMEOUT = 2

TIME_FMT = '%H:%M:%S: '

# Maximum/starting geometry to use:
MAX_ROWS = 16
MAX_COLS = 8
DIMENSIONS = {
    '2801Prog': (16, 4),
    '2006Prog': (16, 8)
}

# Help text to display:
HELP_TEXT = {
    "2801Prog": "The Motorola MCM2801 EEPROM is organized as 16 16-bit words. "
                "This programmer uses big-endian format so when data is read "
                "from or written to the device, the most significant byte in "
                "each word comes first in the buffer.",
    "2006Prog": "The Siemens SDA-2006 EEPROM is organized as 32 16-bit words. "
                "This programmer uses big-endian format so when data is read "
                "from or written to the device, the most significant byte in "
                "each word comes first in the buffer."
}

# Factor to spread characters out a bit:
CHAR_EXPANSION = 1.1

# Width of the window, in characters:
BASE_WIDTH = 40

# What key to use for keyboard shortcuts: command on Mac, control otherwise:
COMMAND_KEY = 'Command' if sys.platform == 'darwin' else 'Control'

FILL_CHAR = 'F'

class HexCanvas(tk.Canvas):
    """Canvas to act as a simple hex editor.
    
    All arguments and keyword arguments are passed to tk.Canvas.
    """
    def __init__(self, *args, **kwargs):
        if 'background' not in kwargs and 'bg' not in kwargs:
            kwargs['background'] = 'white'
        tk.Canvas.__init__(self, *args, **kwargs)
        
        self.ncol = MAX_COLS
        self.nrow = MAX_ROWS
        
        self.cursor_idx = 0
        cursor_coord = self.idx_to_coord(self.cursor_idx)
        self.cursor = self.create_rectangle(
            cursor_coord[0],
            cursor_coord[1],
            cursor_coord[0] + self.master.CHAR_WIDTH,
            cursor_coord[1] + self.master.CHAR_HEIGHT,
            fill='black'
        )
        
        self.data_text = []
        
        self.update_dimensions(MAX_ROWS, MAX_COLS)
        
        self.render_data()
        
        self.bind("<Button-1>", self.on_click)
    
    def render_data(self):
        """Draw the data on the screen.
        
        Only draws the characters that fit within nrow*ncol.
        """
        for d in self.data_text:
            self.delete(d)
        self.data_text = []
        for i in xrange(0, self.nrow * self.ncol):
            self.data_text.append(
                self.create_text(
                    *self.idx_to_coord(i),
                    anchor='nw',
                    text=self.master.data[i],
                    font=self.master.TkFixedFont
                )
            )
        self.move_cursor(min(self.cursor_idx, self.nrow * self.ncol - 1), update_old=False)
    
    def update_dimensions(self, nrow, ncol):
        """Update the dimensions of the canvas.
        
        Re-renders the data when done.
        """
        self.ncol = ncol
        self.nrow = nrow
        self.config(
            width=(ncol + 1) * self.master.CHAR_WIDTH,
            height=(nrow + 1) * self.master.CHAR_HEIGHT
        )
        if len(self.master.data) < ncol * nrow:
            self.master.data.extend([FILL_CHAR] * (ncol * nrow - len(self.master.data)))
        self.render_data()
    
    def idx_to_coord(self, i):
        """Convert index in data to coordinates on screen.
        """
        return ((1 + i % self.ncol) * self.master.CHAR_WIDTH,
                (0.75 + i // self.ncol) * self.master.CHAR_HEIGHT)
    
    def on_click(self, event):
        col_idx = max(min(event.x // self.master.CHAR_WIDTH, self.ncol), 1)
        row_idx = max(min((event.y + 0.25) // self.master.CHAR_HEIGHT, self.nrow), 1)
        
        new_idx = (row_idx - 1) * self.ncol + col_idx - 1
        self.move_cursor(int(new_idx))
    
    def cursor_left(self, event):
        """Move the cursor to the left.
        """
        if self.cursor_idx > 0:
            self.move_cursor(self.cursor_idx - 1)
        else:
            self.master.bell()
    
    def cursor_right(self, event):
        """Move the cursor to the right.
        """
        if self.cursor_idx < self.nrow * self.ncol - 1:
            self.move_cursor(self.cursor_idx + 1)
        else:
            self.master.bell()
    
    def cursor_up(self, event):
        """Move the cursor up.
        """
        if self.cursor_idx >= self.ncol:
            self.move_cursor(self.cursor_idx - self.ncol)
        else:
            self.master.bell()
    
    def cursor_down(self, event):
        """Move the cursor down.
        """
        if self.cursor_idx < self.ncol * self.nrow - self.ncol:
            self.move_cursor(self.cursor_idx + self.ncol)
        else:
            self.master.bell()
    
    def move_cursor(self, new_idx, update_old=True):
        """Move the cursor to a new index.
        """
        old_idx = self.cursor_idx
        self.cursor_idx = new_idx
        cursor_coord = self.idx_to_coord(self.cursor_idx)
        self.coords(
            self.cursor,
            cursor_coord[0],
            cursor_coord[1],
            cursor_coord[0] + self.master.CHAR_WIDTH,
            cursor_coord[1] + self.master.CHAR_HEIGHT
        )
        # Only update the old character if we need to:
        if update_old:
            self.itemconfig(self.data_text[old_idx], fill='black')
        self.itemconfig(self.data_text[new_idx], fill='white')
    
    def insert(self, event):
        """Overwrite the character under the cursor.
        """
        # TODO: Clean this up
        # 0x0004 is control
        # 0x0008 is left-hand alt (aka, command key on Mac)
        # BUT, state 0x0008 is num lock on Windows...
        # 0x0080 is right-hand alt
        
        # Fix for Linux: For whatever reason, the numpad arrow keys are not captured properly, so we have to bind them here:
        if event.char == '':
            if event.keysym == 'KP_Up':
                return self.cursor_up(event)
            elif event.keysym == 'KP_Down':
                return self.cursor_down(event)
            elif event.keysym == 'KP_Left':
                return self.cursor_left(event)
            elif event.keysym == 'KP_Right':
                return self.cursor_right(event)
        elif (not (event.state & 0x0004) and
                (sys.platform != 'darwin' or not (event.state & 0x0008)) and
                not (event.state & 0x0080)):
            if event.char != '' and event.char in string.hexdigits:
                self.itemconfig(self.data_text[self.cursor_idx], text=event.char.upper())
                self.master.data[self.cursor_idx] = event.char.upper()
                if self.cursor_idx < self.nrow * self.ncol - 1:
                    self.move_cursor(self.cursor_idx + 1)
            else:
                self.master.bell()
    
    def paste(self, event=None):
        text = scrub_hex(self.master.clipboard_get())
        self.master.data[self.cursor_idx:self.cursor_idx + len(text)] = text
        self.render_data()
        self.move_cursor(min(self.cursor_idx + len(text), self.ncol * self.nrow - 1))
    
    def swap_bytes(self):
        if len(self.master.data) % 4 != 0:
            bad = False
            warnings.warn(
                "There is not an even number of bytes present, data will be "
                "truncated!",
                RuntimeWarning
            )
            # self.master.status_box.update_status(
            #     "Odd number of bytes!",
            #     "red"
            # )
            # self.master.bell()
        else:
            bad = False
        data = pairwise(self.master.data)
        d_msb = data[::2]
        d_lsb = data[1::2]
        self.master.data = []
        for m, l in zip(d_msb, d_lsb):
            self.master.data.extend(l)
            self.master.data.extend(m)
        self.render_data()
        if not bad:
            self.master.status_box.update_status(
                "Swapped byte order.",
                "white"
            )
    
    def clear_buffer(self):
        self.master.data = [FILL_CHAR] * (MAX_ROWS * MAX_COLS)
        self.render_data()

def pairwise(iterable):
    "s -> (s0,s1), (s2,s3), (s4, s5), ..."
    a = iter(iterable)
    return zip(a, a)

def scrub_hex(text):
    out = ''
    for c in text:
        if c in string.hexdigits:
            out += c.upper()
    return out

class PortSelector(tk.Frame):
    """Class to select the port to use and to keep track of what kind of programmer is connected.
    """
    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)
        
        self.current_port = tk.StringVar(
            self,
            value=NULL_PORT_NAME,
        )
        self.current_port.trace('w', self.update_port)
        self.port_menu = tk.OptionMenu(
            self,
            self.current_port,
            NULL_PORT_NAME,
        )
        self.port_menu.grid(row=0, column=0, sticky='EW')
        
        self.find_button = tk.Button(
            self,
            text="find ports",
            command=self.update_available_ports
        )
        self.find_button.grid(row=1, column=0, sticky='W')
        
        self.grid_columnconfigure(0, weight=1)
        
        self.update_available_ports()
        
        self.port = None
        self.type = None
        
        if sys.platform == 'darwin':
            self.old_ports = []
    
    def update_port(self, *args):
        """Handles updates to which port is in use.
        """
        new_port = self.current_port.get()
        # Close out the old port:
        try:
            gEEProg.exit_automation_mode(self.port)
            if sys.platform == 'darwin':
                # Incredibly hackish way of getting around crash on close on Mac:
                if self.port is not None:
                    self.old_ports.append(self.port)
            else:
                self.port.close()
            
        except:
            pass
        if new_port == NULL_PORT_NAME:
            self.port = None
            self.master.status_box.update_status(
                'No serial port selected.',
                'yellow'
            )
            self.master.set_info("")
        else:
            try:
                self.port = serial.Serial(new_port, timeout=SERIAL_TIMEOUT)
                self.type = gEEProg.enter_automation_mode(self.port)
                self.master.hex_canvas.update_dimensions(*DIMENSIONS[self.type])
                self.master.status_box.update_status(
                    "Successfully connected to %s." % (self.type,),
                    "green"
                )
                self.master.set_info(HELP_TEXT[self.type])
            except:
                self.current_port.set(NULL_PORT_NAME)
                self.port = None
                self.master.status_box.update_status(
                    "Could not connect to selected port!",
                    "red"
                )
                self.master.bell()
                self.master.set_info("")
    
    def update_available_ports(self):
        """Looks to see what ports are available.
        """
        ports = [NULL_PORT_NAME]
        for port in serial.tools.list_ports.comports():
            ports.append(port[0])
        current_port = self.current_port.get()
        
        self.port_menu['menu'].delete(0, tk.END)
        for port in ports:
            self.port_menu['menu'].add_command(
                label=port,
                command=tk._setit(self.current_port, port)
            )
        
        if current_port not in ports:
            self.current_port.set(NULL_PORT_NAME)
            self.master.status_box.update_status(
                "Current port unexpectedly disappeared!",
                "red"
            )
            self.port = None
        else:
            self.master.status_box.update_status(
                "Available ports list refreshed.",
                "white"
            )

class StatusBox(tk.Label):
    """Class to display status messages.
    """
    def update_status(self, message, color):
        """Update the status message, prepending the time.
        """
        self.config(text=time.strftime(TIME_FMT) + message, background=color)

class ControlBox(tk.Frame):
    """Class to hold the buttons.
    """
    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)
        
        self.clear_button = tk.Button(
            self,
            text="clear buffer",
            command=self.master.hex_canvas.clear_buffer
        )
        self.clear_button.grid(row=0, column=0, sticky='W')
        self.swap_button = tk.Button(
            self,
            text="swap bytes",
            command=self.master.hex_canvas.swap_bytes
        )
        self.swap_button.grid(row=1, column=0, sticky='W')
        self.read_button = tk.Button(
            self,
            text="read",
            command=self.master.read
        )
        self.read_button.grid(row=2, column=0, sticky='W')
        self.program_button = tk.Button(
            self,
            text="program",
            command=self.master.program
        )
        self.program_button.grid(row=3, column=0, sticky='W')
        self.verify_button = tk.Button(
            self,
            text="verify",
            command=self.master.verify
        )
        self.verify_button.grid(row=4, column=0, sticky='W')
        self.erase_button = tk.Button(
            self,
            text="erase",
            command=self.master.erase
        )
        self.erase_button.grid(row=5, column=0, sticky='W')

class GEEProgMainWindow(tk.Tk):
    """Main window of the program.
    """
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        
        self.wm_title("gEEProg %s" % (__version__,))
        
        if getattr(sys, 'frozen', None) == 'macosx_app':
            img_path = 'Icon.gif'
        elif getattr(sys, 'frozen', None):
            print(sys.frozen)
            img_path = os.path.join(sys._MEIPASS, 'graphics/Icon.gif')
        else:
            img_path = '../graphics/Icon.gif'
        # If Icon.gif isn't in the usual spots for git/frozen app, it must be
        # where pip puts it:
        try:
            self.img = tk.PhotoImage(file=img_path)
        except tk.TclError:
            self.img = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), '..', 'data', 'gEEProg', 'Icon.gif'))
        self.tk.call('wm', 'iconphoto', self._w, self.img)
        
        self.data = [FILL_CHAR] * (MAX_ROWS * MAX_COLS)
        
        self.TkFixedFont = tkFont.nametofont("TkFixedFont")
        self.CHAR_WIDTH = CHAR_EXPANSION * self.TkFixedFont.measure("D")
        self.CHAR_HEIGHT = self.TkFixedFont.metrics('linespace')
        
        self.hex_canvas = HexCanvas(
            self,
            width=MAX_COLS * self.CHAR_WIDTH,
            height=MAX_ROWS * self.CHAR_HEIGHT,
            borderwidth=2,
            relief=tk.GROOVE
        )
        self.hex_canvas.grid(row=0, column=0, rowspan=2, sticky='NW')
                
        self.status_box = StatusBox(self, width=BASE_WIDTH)
        self.status_box.grid(row=5, column=0, columnspan=3, sticky='EW')
        
        self.port_selector = PortSelector(self)
        self.port_selector.grid(row=0, column=1, columnspan=2, sticky='NSEW')
        
        self.status_box.update_status(
            "Select the appropriate serial port to begin.",
            'white'
        )
        
        # Create control buttons:
        self.control_box = ControlBox(self, pady=5)
        self.control_box.grid(row=1, column=1, sticky='SW')
        
        # Create textbox:
        self.info_box = tk.Text(
            self,
            width=1,
            height=1,
            wrap=tk.WORD,
            font=tkFont.nametofont("TkDefaultFont"),
            background=self.cget("bg"),
            borderwidth=0,
            relief=tk.FLAT,
            padx=5
        )
        self.set_info("")
        self.info_box.grid(row=1, column=2, sticky='NSEW')
        
        # Set up key bindings:
        self.bind("<Left>", self.hex_canvas.cursor_left)
        self.bind("<Right>", self.hex_canvas.cursor_right)
        self.bind("<Up>", self.hex_canvas.cursor_up)
        self.bind("<Down>", self.hex_canvas.cursor_down)
        
        #for c in string.hexdigits:
        #    self.bind(c, self.hex_canvas.insert)
        # Bind all keys to insert to work around bug with numpad in Linux:
        self.bind("<Key>", self.hex_canvas.insert)
        
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Create menubars:
        self.menubar = tk.Menu(self)
        self['menu'] = self.menubar
        
        self.menu_file = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_file, label='File')
        self.menu_file.add_command(
            label="Open...",
            command=self.open,
            accelerator='%s-O' % (COMMAND_KEY,)
        )
        self.bind_all("<%s-o>" % (COMMAND_KEY,), self.open)
        self.menu_file.add_command(
            label="Save...",
            command=self.save,
            accelerator='%s-S' % (COMMAND_KEY,)
        )
        self.bind_all("<%s-s>" % (COMMAND_KEY,), self.save)
        
        self.menu_edit = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_edit, label='Edit')
        self.menu_edit.add_command(
            label="Paste",
            command=self.hex_canvas.paste,
            accelerator='%s-V' % (COMMAND_KEY,)
        )
        self.bind_all("<%s-v>" % (COMMAND_KEY,), self.hex_canvas.paste)
        self.menu_edit.add_command(
            label="Copy Buffer",
            command=self.copy_buffer,
            accelerator='%s-C' % (COMMAND_KEY,)
        )
        self.bind_all("<%s-c>" % (COMMAND_KEY,), self.copy_buffer)
        
        self.menu_edit = tk.Menu(self.menubar)
        self.menubar.add_cascade(menu=self.menu_edit, label='Help')
        self.menu_edit.add_command(
            label="gEEProg help...",
            command=self.show_help
        )
    
    def show_help(self, event=None):
        top = tk.Toplevel()
        top.title("About gEEProg %s" % (__version__,))
        top.tk.call('wm', 'iconphoto', top._w, self.img)
        icon = tk.Label(top, image=self.img)
        icon.grid(row=0, column=0, sticky='NSEW', rowspan=7)
        
        title = tk.Label(
            top,
            text="gEEProg %s" % (__version__,),
            font=tkFont.Font(weight=tkFont.BOLD)
        )
        title.grid(row=0, column=1, sticky='NW')
        
        description = tk.Label(
            top,
            text=u"\u00A9 2014 Mark Chilenski\n"
                  "GUI to control D'Asaro Designs EEPROM programmers.",
            justify=tk.LEFT
        )
        description.grid(row=1, column=1, sticky='W')
        
        DD_link = tk.Label(top, text="www.dasarodesigns.com", foreground="#0000ff")
        DD_link.bind(
            "<1>",
            lambda event: webbrowser.open("http://www.dasarodesigns.com")
        )
        DD_link.grid(row=2, column=1, sticky='W')
        
        git_link = tk.Label(top, text="www.github.com/markchil/gEEProg", foreground="#0000ff")
        git_link.bind(
            "<1>",
            lambda event: webbrowser.open("http://www.github.com/markchil/gEEProg")
        )
        git_link.grid(row=3, column=1, sticky='W')
        
        license_text = tk.Label(
            top,
            text="Distributed under the terms of the GNU General Purpose License (GPL)."
        )
        license_text.grid(row=4, column=1, sticky='W')
        
        gpl_link = tk.Label(top, text="www.gnu.org/licenses/gpl.txt", foreground="#0000ff")
        gpl_link.bind(
            "<1>",
            lambda event: webbrowser.open("http://www.gnu.org/licenses/gpl.txt")
        )
        gpl_link.grid(row=5, column=1, sticky='W')
        
        button = tk.Button(top, text="OK", command=top.destroy)
        button.grid(row=6, column=1, sticky='E')
    
    def set_info(self, text):
        self.info_box.config(state=tk.NORMAL)
        self.info_box.delete(0.0, tk.END)
        self.info_box.insert(0.0, text)
        self.info_box.config(state=tk.DISABLED)
    
    def copy_buffer(self, event=None):
        self.clipboard_clear()
        self.clipboard_append("".join(self.data[:2 * gEEProg.NUM_BYTES[self.port_selector.type]]))
    
    def open(self, event=None):
        """Open and read a file.
        """
        filepath = tkFileDialog.askopenfilename()
        if filepath:
            self.read_file(filepath)
        else:
            self.status_box.update_status("No file selected!", "white")
    
    def read_file(self, filepath):
        """Read the file into the data area.
        """
        base, ext = os.path.splitext(filepath)
        read_str = ''
        if ext.lower() == '.txt':
            with open(filepath, 'r') as f:
                data = f.read()
            for char in data:
                if char in string.hexdigits:
                    read_str += char.upper()
        else:
            with open(filepath, 'rb') as f:
                data = f.read()
            for b in data:
                read_str += b.encode('hex').upper()
        if len(read_str) < 2 * gEEProg.NUM_BYTES[self.port_selector.type]:
            read_str += FILL_CHAR * (2 * gEEProg.NUM_BYTES[self.port_selector.type] - len(read_str))
        self.data = list(read_str)
        self.hex_canvas.render_data()
        self.status_box.update_status("Read complete.", "green")
    
    def save(self, event=None):
        """Save the data to a file.
        """
        filepath = tkFileDialog.asksaveasfilename()
        if filepath:
            self.save_file(filepath)
        else:
            self.status_box.update_status("No file selected!", "white")
    
    def save_file(self, filepath):
        """Save the data to a file.
        """
        base, ext = os.path.splitext(filepath)
        if ext == '.txt':
            with open(filepath, 'w') as outfile:
                outfile.write("".join(self.data))
        else:
            with open(filepath, 'wb') as outfile:
                for a, b in zip(self.data[::2], self.data[1::2]):
                    outfile.write(chr(int(a+b, 16)))
        self.status_box.update_status("Wrote file.", "green")
    
    def read(self):
        """Read the chip.
        """
        try:
            self.data = list(
                gEEProg.read_chip(
                    self.port_selector.port,
                    gEEProg.NUM_BYTES[self.port_selector.type]
                )
            )
            self.hex_canvas.render_data()
            self.status_box.update_status("Read complete.", "green")
        except:
            self.status_box.update_status("Read failed!", "red")
            self.bell()
    
    def program(self):
        """Program the chip.
        """
        try:
            success = gEEProg.program_chip(
                self.port_selector.port,
                "".join(self.data[:2 * gEEProg.NUM_BYTES[self.port_selector.type]])
            )
            if not success:
                self.status_box.update_status(
                    "Verification following program failed.",
                    "red"
                )
                self.bell()
            else:
                self.status_box.update_status("Program complete.", "green")
        except NotImplementedError:
            self.status_box.update_status("Could not perform program!", "red")
            self.bell()
    
    def verify(self):
        try:
            success = gEEProg.verify_chip(
                self.port_selector.port,
                "".join(self.data[:2 * gEEProg.NUM_BYTES[self.port_selector.type]])
            )
            if success:
                self.status_box.update_status(
                    "Chip passed verification.",
                    "green"
                )
            else:
                self.status_box.update_status(
                    "Chip failed verification!",
                    "red"
                )
                self.bell()
        except:
            self.status_box.update_status("Could not perform verify!", "red")
            self.bell()
    
    def erase(self):
        try:
            result = gEEProg.erase_chip(
                self.port_selector.port,
                gEEProg.NUM_BYTES[self.port_selector.type]
            )
            if (result != gEEProg.ERASE_CHAR[self.port_selector.type] *
                    2 * gEEProg.NUM_BYTES[self.port_selector.type]):
                self.status_box.update_status(
                    "Chip did not erase properly!",
                    "red"
                )
                self.bell()
            else:
                self.status_box.update_status("Chip has been erased.", "green")
        except:
            self.status_box.update_status("Could not perform erase!", "red")
            self.bell()

if __name__ == "__main__":
    root = GEEProgMainWindow()
    root.lift()
    root.mainloop()
