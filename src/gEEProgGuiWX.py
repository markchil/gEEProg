#!/opt/local/bin/python
#arch -i386 /opt/local/bin/python
# must be run 32 bit on OS X for wxPython to play nice.

# Copyright 2013 Mark Chilenski
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

import wx

import serial
import serial.tools.list_ports
import gEEProg
import string
#import os
import os.path
import time
import math

LICENSE_TEXT = 'Distributed under the terms of the GNU General Purpose License (GPL). Refer to http://www.gnu.org/licenses/gpl.txt'

PROG_NAME = '2801Prog'          # program name
VERSION_STR = '1.0'     # version as a string

NULL_PORT_NAME = 'disconnected' # port name for when there is no connection
SERIAL_TIMEOUT = 2              # seconds
FILL_CHAR = '0'                 # character to fill in on incomplete entries
TIME_FMT = '%H:%M:%S: '         # timestamp format (for time.strftime)
BORDER_OFFSET = 10              # number of pixels to offset the text_entry height, 10 is proven for RedHat

class EntryValidator(wx.PyValidator):
    """Extension of PyValidator to scrub input into uppercase hexadecimal,
    also enforces the 2 * gEEProg.NUM_BYTES length limit."""
    def __init__(self):
        wx.PyValidator.__init__(self)
        self.Bind(wx.EVT_CHAR, self.OnChar)
    
    def Clone(self):
        """Required dummy method."""
        return EntryValidator()
    
    def Validate(self, win):
        """Required dummy method."""
        return True
    
    def TransferToWindow(self):
        """Required dummy method."""
        return True
    
    def TransferFromWindow(self):
        """Required dummy method."""
        return True
    
    def OnChar(self, event):
        """Handle character events. Only allow valid hexadecimal/binary digits,
        (depending on state of self.in_hex_mode), automatically capitalize
        lowercase a-f and limit length to gEEProg.NUM_BYTES of data."""
        keycode = int(event.GetKeyCode())
        # handle extended ASCII, let other special keys go through
        # also let backspace and delete go through:
        if keycode < 256 and keycode != wx.WXK_BACK and keycode != wx.WXK_DELETE:
            selection = self.GetWindow().GetSelection()
            
            key = chr(keycode)
            if self.GetWindow().in_hex_mode:
                valid_digit = key in string.hexdigits
                invalid_length = len(self.GetWindow().GetValue()) + 1 \
                                    > 2 * gEEProg.NUM_BYTES \
                                    and selection[0] == selection[1]
            else:
                valid_digit = key in ('0', '1')
                invalid_length = len(self.GetWindow().GetValue()) + 1 \
                                    > 8 * gEEProg.NUM_BYTES \
                                    and selection[0] == selection[1]
            
            if invalid_length or not valid_digit:
                wx.Bell()
                return None
            
            # switch lowercase to uppercase:
            if self.GetWindow().in_hex_mode and 123 > keycode > 96:
                keycode = keycode - 32
                key = chr(keycode)
                self.GetWindow().WriteText(key)
                return None
        event.Skip()

class MyFileDropTarget(wx.FileDropTarget):
    """Class to implement drag-and-drop of file."""
    def __init__(self, frame):
        wx.FileDropTarget.__init__(self)
        self.frame = frame
    
    def OnDropFiles(self, x, y, filenames):
        """Handler for dropped files. Only allows one file to be dropped,
        sends an error dialog if multiple files are dropped."""
        if len(filenames) > 1:
            wx.Bell()
            self.frame.status_bar.SetStatusText('No file read. '\
                'Only drop one file!')
            self.frame.status_bar.SetBackgroundColour('RED')
            dlg = wx.MessageDialog(self.frame,
                                   'Only drop one file to read at a time!',
                                   '2801Prog: File Error',
                                   style=wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            self.frame.read_file(filenames[0])

class HexBox(wx.TextCtrl):
    """Extension of wx.TextCtrl to handle input of hexadecimal/binary data of
    fixed length. Keeps track of whether it is in hex or binary edit mode with
    the flag self.in_hex_mode. Sets allowable lengths based on
    gEEProg.NUM_BYTES."""
    def __init__(self, in_hex_mode, *args, **kwargs):
        """Sets font to monospaced and sets size to that appropriate for the
        content, as inferred from gEEProg.NUM_BYTES."""
        wx.TextCtrl.__init__(self, *args, **kwargs)
        self.in_hex_mode = in_hex_mode
        # set monospaced font for proper editing
        # Courier should be a safe assumption for almost all systems.
        self.mono_font = wx.Font(18,
                                 family=wx.FONTFAMILY_TELETYPE,
                                 style=wx.FONTSTYLE_NORMAL,
                                 weight=wx.FONTWEIGHT_NORMAL)
        # used to use: faceName='Courier'
        # changed to more platform-independent call
        self.SetFont(self.mono_font)
        # get line dimensions:
        hex_line_dims = self.GetTextExtent('DDDD')
        self.hex_size = (BORDER_OFFSET + hex_line_dims[0],
                         BORDER_OFFSET + (gEEProg.NUM_BYTES // 2) * hex_line_dims[1])
        bin_line_dims = self.GetTextExtent('0000000000000000')
        self.bin_size = (BORDER_OFFSET + bin_line_dims[0],
                         BORDER_OFFSET + (gEEProg.NUM_BYTES // 2) * bin_line_dims[1])
        if self.in_hex_mode:
            self.SetSize(self.hex_size)
        else:
            self.SetSize(self.bin_size)
        self.SetMinSize(self.GetSize())
    
    def hex_rep_to_bin_rep(self, hex_rep):
        """Converts the passed hexadecimal string representation to an
        appropriately-padded binary string representation."""
        num_bits_present = len(hex_rep) * 4
        return bin(int(hex_rep, 16))[2:].strip('L').zfill(num_bits_present)
    
    def bin_rep_to_hex_rep(self, bin_rep):
        """Converts the passed binary string representation to an
        appropriately-padded hexadecimal string representation. Pads internal
        value with zeros at end to get an integral number of nibbles."""
        num_nibbles_present = int(math.ceil(len(bin_rep) / 4))
        # note that there could be an incomplete number of nibbles, so pad with zeros:
        bin_rep = self.pad_with_fill(string=bin_rep, required_length=num_nibbles_present * 4,
                                     char='0')
        # some verisions put an 'L' suffix for long hex, need to strip it:
        # the zfill is there in case the leading nibble(s) are 0.
        return hex(int(bin_rep, 2))[2:].upper().strip('L').zfill(num_nibbles_present)
    
    def set_hex_mode(self, new_hex_mode):
        """Updates the widget to represent the passed new value for
        self.in_hex_mode. Resizes window and converts data contained. Note that
        the GTK implementation doesn't seem to support wxTE_NO_VSCROLL. The
        commented Refresh, Update and Yield commands are an attempt at a hack
        to fix this behavior (that didn't work)."""
        if self.in_hex_mode != new_hex_mode:
            self.in_hex_mode = new_hex_mode
            val = self.GetValue()
            new_rep = ''
            self.Clear()
            #self.Refresh()
            #self.Update()
            #wx.Yield()
            
            if self.in_hex_mode:
                self.SetMinSize(self.hex_size)
                self.SetSize(self.hex_size)
                # must convert from binary to hex:
                if val != '':
                    new_rep = self.bin_rep_to_hex_rep(val)
            else:
                self.SetSize(self.bin_size)
                #self.Refresh()
                #self.Update()
                self.SetMinSize(self.bin_size)
                # must convert from hex to binary:
                if val != '':
                    new_rep = self.hex_rep_to_bin_rep(val)
            
            # do the resize here as an attempted hack to get scroll bars to go
            # away on RedHat
            self.Refresh()
            self.Update()
            parent = self.GetParent()
            parent.GetSizer().SetSizeHints(parent)
            parent.Layout()
            parent.Fit()
            parent.Refresh()
            parent.Update()
            
            # make sure everything has been processed before putting text back:
            wx.Yield()
            
            # set at very end as an attempted hack to get scroll bars to go
            # away on RedHat
            self.SetValue(new_rep)
            #self.Refresh()
            #self.Update()
    
    def pad_with_fill(self, string=None, required_length=None, char=FILL_CHAR):
        """Pad the data with a relevant fill character. If no required length
        is given, fills up to gEEProg.NUM_BYTES, otherwise the length of
        string to fill to is passed as required_length. The character to fill
        with is given as char, which defaults to FILL_CHAR='0'."""
        update_self = False
        if string is None:
            update_self = True
            string = self.GetValue()
        if required_length is None:
            if self.in_hex_mode:
                required_length = 2 * gEEProg.NUM_BYTES
            else:
                required_length = 8 * gEEProg.NUM_BYTES
        entry_len = len(string)
        if entry_len < required_length:
            string = string + char * (required_length - entry_len)
        if update_self:
            self.SetValue(string)
        return string
    
    def Clear(self):
        """Overrides native Clear method to fix a bug with the custom font.
        (This may in fact only be needed for OS X...)"""
        wx.TextCtrl.Clear(self)
        self.SetFont(self.mono_font)
    
    def Cut(self):
        """OVerrides native Cut method to fix a bug with the custom font when
        all text is selected and cut. (This may in fact only be needed for
        OS X...)"""
        wx.TextCtrl.Cut(self)
        self.SetFont(self.mono_font)

class MasterFrame(wx.Frame):
    """Frame with edit mode radio buttons, hex/binary editing window, serial
    port selector and buttons to perform. Also supports contextual help."""
    def __init__(self, parent, title):
        wx.Frame.__init__(self, parent, title=title,
                          style=wx.DEFAULT_FRAME_STYLE|wx.WS_EX_CONTEXTHELP)
        self.SetExtraStyle(wx.FRAME_EX_CONTEXTHELP)
        
        self.SetHelpText('Drag a binary or text file to the window to read.')
        
        # set program icon:
        # get resource path if stuck in exe file -- pyInstaller uses the
        # _MEIPASS variable to point to where the files get unpacked
        # if the variable is empty (i.e., when developing), just use
        # ./icon_file to get from local directory
        icon_file = 'favicon.ico'
        if wx.Platform == '__WXMSW__':
            import sys
            if getattr(sys, 'frozen', None):
                basedir = sys._MEIPASS
            else:
                basedir = os.path.dirname(__file__)
            icon_file = os.path.join(basedir, icon_file)
        icon = wx.Icon(icon_file, wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)
        
        # entry box:
        self.text_entry = HexBox(True,
                                 self,
                                 style=wx.TE_MULTILINE|wx.TE_CHARWRAP|wx.TE_NO_VSCROLL,
                                 validator=EntryValidator())
        self.text_entry.SetHelpText('Type or paste your code here, ' \
                                    'or use File > Open to load from a binary ' \
                                    'or text file.')
        # set up for drag-and-drop:
        self.SetDropTarget(MyFileDropTarget(self))
        self.text_entry.SetDropTarget(MyFileDropTarget(self))
        
        # mode select radio buttons:
        self.hex_rb = wx.RadioButton(self, -1, 'hex', style=wx.RB_GROUP)
        self.Bind(wx.EVT_RADIOBUTTON, self.set_mode, id=self.hex_rb.GetId())
        self.hex_rb.SetHelpText('Switch to hex input mode. ' \
                                'Any incomplete nibbles will be padded with ' \
                                'zeros.')
        self.bin_rb = wx.RadioButton(self, -1, 'bin')
        self.Bind(wx.EVT_RADIOBUTTON, self.set_mode, id=self.bin_rb.GetId())
        self.bin_rb.SetHelpText('Switch to binary input mode.')
        self.hex_rb.SetValue(True)
        
        # serial selector:
        self.port = None        
        self.port_selector = wx.ComboBox(self,
                                         -1,
                                         value=NULL_PORT_NAME,
                                         choices=[NULL_PORT_NAME],
                                         name='port',
                                         style=wx.CB_READONLY)
        self.Bind(wx.EVT_COMBOBOX, self.update_port, id=self.port_selector.GetId())
        self.port_selector.SetHelpText("Select the serial port you have " \
                                       "connected the device to. Select " \
                                       "'{null}' to disconnect.".format(null=NULL_PORT_NAME))
        # apply default values at end once status_bar is setup (attempt to fix bug on Ubuntu...)
        #self.update_available_ports()
        #self.port_selector.SetValue(NULL_PORT_NAME)
        
        # buttons:
        self.refresh_ports_button = wx.Button(self, -1, 'find ports')
        self.Bind(wx.EVT_BUTTON, self.refresh_ports_press, id=self.refresh_ports_button.GetId())
        self.refresh_ports_button.SetHelpText('Update list of available serial ports. ' \
                                     'Useful if you did not plug in a USB to ' \
                                     'serial adaptor before loading the program.')
        
        self.read_button = wx.Button(self, -1, 'read')
        self.Bind(wx.EVT_BUTTON, self.read_press, id=self.read_button.GetId())
        self.read_button.SetHelpText('Read the contents of the chip.')
        
        self.program_button = wx.Button(self, -1, 'program')
        self.Bind(wx.EVT_BUTTON, self.program_press, id=self.program_button.GetId())
        self.program_button.SetHelpText('Program the chip with what you have ' \
                                        'entered. If input is too short, it ' \
                                        'will be padded with zeros.')
        
        self.verify_button = wx.Button(self, -1, 'verify')
        self.Bind(wx.EVT_BUTTON, self.verify_press, id=self.verify_button.GetId())
        self.verify_button.SetHelpText('Verify the chip against what you have ' \
                                       'entered. If input is too short, it ' \
                                       'will be padded with zeros.')
        
        self.erase_button = wx.Button(self, -1, 'erase')
        self.Bind(wx.EVT_BUTTON, self.erase_press, id=self.erase_button.GetId())
        self.erase_button.SetHelpText('Erase the chip. You will be warned if ' \
                                      'the chip does not end up zeroed.')
        
        # only show help button for non-windows:
        if wx.Platform != '__WXMSW__':
            self.help_button = wx.ContextHelpButton(self)
        
        # put in ugly status indicator for windows:
        if wx.Platform == '__WXMSW__':
            self.status_box = wx.StaticText(self,
                                            id=-1,
                                            size=self.port_selector.GetSize(),
                                            style=wx.ST_NO_AUTORESIZE|wx.ALIGN_CENTRE)
            self.status_box.SetHelpText('Status indicator. Colors indicate ' \
                                        'result of previous operation: green ' \
                                        'for success, yellow for warnings and ' \
                                        'red for errors/failures.')
            self.status_box.SetBackgroundColour('BLACK')
            self.normal_status_box_color = 'BLACK'
        
        # menu bar:
        self.menu_bar = wx.MenuBar()
        
        self.file_menu = wx.Menu()
        
        self.file_menu.Append(wx.ID_ABOUT,
                              "&About 2801Prog",
                              'Information about this program.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_about, id=wx.ID_ABOUT)
        
        self.file_menu.Append(wx.ID_OPEN,
                              '&Open\tCtrl-O',
                              'Open binary or text file. Type is determined by ' \
                              'file extension.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_open, id=wx.ID_OPEN)
        
        self.file_menu.Append(wx.ID_SAVE,
                              '&Save\tCtrl-S',
                              'Save binary or text file. Type is determined by ' \
                              'selected format. Extension is used if no format ' \
                              'is selected.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_save, id=wx.ID_SAVE)
        
        self.file_menu.Append(wx.ID_EXIT,
                              "E&xit",
                              'Terminate the program',
                              wx.ITEM_NORMAL)
        # bind both close and exit to ensure program exit is handled properly:
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        self.menu_bar.Append(self.file_menu, "&File")
        
        self.edit_menu = wx.Menu()
        
        self.edit_menu.Append(wx.ID_CUT,
                              "&Cut\tCtrl-X",
                              'Cut selected text.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_cut, id=wx.ID_CUT)
        
        self.edit_menu.Append(wx.ID_COPY,
                              "&Copy\tCtrl-C",
                              'Copy selected text.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_copy, id=wx.ID_COPY)
        
        self.edit_menu.Append(wx.ID_PASTE,
                              "&Paste\tCtrl-V",
                              'Paste from clipboard. Up to the first 64 valid ' \
                              'hex digits will be used.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_paste, id=wx.ID_PASTE)
        
        self.edit_menu.Append(wx.ID_SELECTALL,
                              "Select &All\tCtrl-A",
                              'Select all text.',
                              wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.on_selectall, id=wx.ID_SELECTALL)
        
        self.menu_bar.Append(self.edit_menu, "&Edit")
        
        self.SetMenuBar(self.menu_bar)
        
        # keyboard shortcuts:
        self.accel_tbl = wx.AcceleratorTable([(wx.ACCEL_CTRL, ord('x'), wx.ID_CUT),
                                         (wx.ACCEL_CTRL, ord('c'), wx.ID_COPY),
                                         (wx.ACCEL_CTRL, ord('v'), wx.ID_PASTE),
                                         (wx.ACCEL_CTRL, ord('a'), wx.ID_SELECTALL),
                                         (wx.ACCEL_CTRL, ord('o'), wx.ID_OPEN),
                                         (wx.ACCEL_CTRL, ord('s'), wx.ID_SAVE)])
        self.SetAcceleratorTable(self.accel_tbl)
        
        # layout: outer horizontal BoxSizer with three columns inside
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        col_1_sizer = wx.BoxSizer(wx.VERTICAL)
        col_1_sizer.AddSpacer(5)
        col_1_sizer.Add(self.hex_rb)
        col_1_sizer.Add(self.bin_rb)
        col_1_sizer.AddSpacer(5)
        
        col_2_sizer = wx.BoxSizer(wx.VERTICAL)
        col_2_sizer.AddSpacer(5)
        col_2_sizer.Add(self.text_entry, proportion=1, flag=wx.EXPAND)
        col_2_sizer.AddSpacer(5)
        
        col_2_sizer.SetItemMinSize(self.text_entry, self.text_entry.GetMinSize())
        
        col_3_sizer = wx.BoxSizer(wx.VERTICAL)
        col_3_sizer.AddSpacer(5)
        col_3_sizer.Add(self.port_selector)
        col_3_sizer.AddSpacer(5)
        col_3_sizer.Add(self.refresh_ports_button)
        col_3_sizer.AddSpacer(15)
        col_3_sizer.Add(self.read_button)
        col_3_sizer.AddSpacer(5)
        col_3_sizer.Add(self.program_button)
        col_3_sizer.AddSpacer(5)
        col_3_sizer.Add(self.verify_button)
        col_3_sizer.AddSpacer(5)
        col_3_sizer.Add(self.erase_button)
        col_3_sizer.AddSpacer(15)
        col_3_sizer.AddStretchSpacer(prop=1)
        if wx.Platform != '__WXMSW__':
            col_3_sizer.Add(self.help_button, flag=wx.ALIGN_BOTTOM|wx.ALIGN_RIGHT)
        else:
            col_3_sizer.Add(self.status_box, flag=wx.ALIGN_BOTTOM)
        col_3_sizer.AddSpacer(5)
        
        h_sizer.AddSpacer(5)
        h_sizer.Add(col_1_sizer)
        h_sizer.AddSpacer(5)
        h_sizer.Add(col_2_sizer, proportion=1, flag=wx.EXPAND)
        h_sizer.AddSpacer(5)
        h_sizer.Add(col_3_sizer, proportion=0, flag=wx.EXPAND)
        h_sizer.AddSpacer(5)
        
        #h_sizer.SetSizeHints(self)
        self.SetSizer(h_sizer)
        
        # status bar:
        self.status_bar = self.CreateStatusBar()
        if wx.Platform == '__WXMSW__':
            self.status_bar.SetHelpText('Displays status information.')
        else:
            self.status_bar.SetHelpText('Displays status information. Colors ' \
                                        'indicate results: green is success, ' \
                                        'yellow is a warning, red is an error.')
        # store system default color:
        self.normal_status_color = self.status_bar.GetBackgroundColour()
        
        self.update_available_ports()
        #self.port_selector.SetValue(NULL_PORT_NAME)
        
        self.status_bar.SetStatusText('Select the appropriate serial port ' \
                                      'from the list to begin.')
        
        self.GetSizer().SetSizeHints(self)
        self.Layout()
        self.Fit()
        
        # prefill with zeros:
        #self.text_entry.pad_with_fill()
        # moved below as a hack to fix scrollbars on MED's RedHat machine.
        
        self.Show(True)
    
    def update_available_ports(self):
        """Updates list of available ports and puts it into the port_selector
        ComboBox."""
        ports = [NULL_PORT_NAME]
        for port in serial.tools.list_ports.comports():
            ports.append(port[0])
        current_port = self.port_selector.GetValue()
        self.port_selector.SetItems(ports)
        if current_port in ports:
            self.port_selector.SetValue(current_port)
            self.update_status('Available ports list refreshed.')
        else:
            wx.Bell()
            self.port_selector.SetValue(NULL_PORT_NAME)
            self.update_port(None)
            self.update_status("Port '{port}' unexpectedly disappeared. Please check connections and find ports again.".format(port=current_port),
                               'ERROR', 'RED')
            dlg = wx.MessageDialog(self,
                                   "Port '{port}' unexpectedly disappeared. Please check connections and find ports again.".format(port=current_port),
                                   style=wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
    
    def refresh_ports_press(self, event):
        """Handles presses of the refresh_ports_button."""
        self.update_available_ports()
    
    def update_status(self, long_text, short_text='', color=None):
        """Updates the status box and Windows status indicator. The long_text
        goes in the status box, the short_text goes in the Windows indicator."""
        if color == None:
            color = self.normal_status_color
            if wx.Platform == '__WXMSW__':
                box_color = self.normal_status_box_color
        else:
            if wx.Platform == '__WXMSW__':
                box_bolor = color
        self.status_bar.SetBackgroundColour(color)
        self.status_bar.SetStatusText(time.strftime(TIME_FMT) + long_text)
        if wx.Platform == '__WXMSW__':
            self.status_box.SetBackgroundColour(color)
            self.status_box.SetLabel(short_text)
    
    def update_port(self, event):
        """Update the port to that selected from the ComboBox. Tells the old
        port to exit automation mode and closes it before opening the new port.
        If the new port fails to acknowledge automation mode, raises an error
        dialog."""
        try:
            gEEProg.exit_automation_mode(self.port)
            self.port.close()
        except:
            pass
        port = self.port_selector.GetValue()
        if port == NULL_PORT_NAME:
            self.port = None
            self.update_status('No serial port selected.', color='YELLOW')
        else:
            try:
                self.port = serial.Serial(port, timeout=SERIAL_TIMEOUT)
                gEEProg.enter_automation_mode(self.port)
                self.update_status("Successfully connected to port '{port}'".format(port=port),
                                   'OK', 'GREEN')
            except:
                # if cannot connect, set port back to NULL_PORT_NAME and set
                # internally to None.
                self.port_selector.SetValue(NULL_PORT_NAME)
                self.port = None
                wx.Bell()
                self.update_status("Failed to connect to port '{port}'".format(port=port),
                                   'ERROR', 'RED')
                dlg = wx.MessageDialog(self,
                                       'Could not connect to that port. ' \
                                       'Please try another.',
                                       '2801Prog: Serial Connection Error',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
    
    def on_cut(self, event):
        """Pass cut events to the text_entry box."""
        self.text_entry.Cut()
    
    def on_copy(self, event):
        """Pass copy events to the text_entry box."""
        self.text_entry.Copy()
    
    def on_paste(self, event):
        """Handle paste events for the text_entry box. Pulls valid hex or bin
        characters, in sequence, from the clipboard and puts them into the
        text_entry up to the point it is full."""
        if not wx.TheClipboard.IsOpened():
            try:
                wx.TheClipboard.Open()
                do = wx.TextDataObject()
                success = wx.TheClipboard.GetData(do)
                if success:
                    text = do.GetText()
                    selection = self.text_entry.GetSelection()
                    if self.text_entry.in_hex_mode:
                        max_len = 2 * gEEProg.NUM_BYTES
                        valid_chars = string.hexdigits
                    else:
                        max_len = 8 * gEEProg.NUM_BYTES
                        valid_chars = ('0', '1')
                    safe_text = ''
                    for char in text:
                        if len(self.text_entry.GetValue()) + len(safe_text) - selection[1] + selection[0] >= max_len:
                            wx.Bell()
                            break
                        if char in valid_chars:
                            safe_text = safe_text + char.upper()
                        else:
                            wx.Bell()
                else:
                    wx.Bell()
                self.text_entry.WriteText(safe_text)
            except:
                 wx.Bell()
            finally:
                wx.TheClipboard.Close()
        else:
            wx.Bell()
    
    def on_selectall(self, event):
        """Pass select all events to the text_entry box."""
        self.text_entry.SelectAll()
    
    def set_mode(self, event):
        """Handle the mode selection radio buttons: convert entry text and 
        resize window."""
        old_state = self.text_entry.in_hex_mode
        self.text_entry.set_hex_mode(self.hex_rb.GetValue())
        if self.text_entry.in_hex_mode:
            self.update_status('Hexadecimal entry mode active.')
        else:
            self.update_status('Binary entry mode active.')
        
        # self.GetSizer().SetSizeHints(self)
        # self.Layout()
        # self.Fit()
    
    def on_about(self, event):
        """Display an AboutBox with program information."""
        info = wx.AboutDialogInfo()
        info.Name = PROG_NAME
        info.Version = VERSION_STR
        info.Copyright = '(C) 2013 Mark Chilenski'
        info.Description = 'GUI to control the 2801Prog EEPROM programmer.'
        info.WebSite = ('http://www.6540rom.com', 'www.6540rom.com')
        info.Developers = ['Mark Chilenski', "Matthew D'Asaro"]
        # bypass shitty license handling on Win and Mac:
        if wx.Platform in ('__WXMSW__', '__WXMAC__'):
            license = LICENSE_TEXT
        else:
            try:
                gpl_f = open('gpl-3.0.txt', 'r')
                license = gpl_f.read()
            except:
                license = LICENSE_TEXT
            finally:
                gpl_f.close()
        info.License = license
        wx.AboutBox(info)
    
    def read_file(self, file_path):
        """Reads a file into the text_entry. Determines type from file
        extension: .txt is read as ASCII representation of hex, .bin and all
        others are read as raw binary. For text, first 64 valid hex digits are
        read. For binary, first 32 bytes are read."""
        if self.text_entry.in_hex_mode:
            max_length = 2 * gEEProg.NUM_BYTES
        else:
            max_length = 8 * gEEProg.NUM_BYTES
        try:
            file_name, file_extension = os.path.splitext(file_path)
            
            # build up read characters on at a time:
            read_chr = ''
            if file_extension.lower() == '.txt':
                input_file = open(file_path, 'r')
                data = input_file.read()
                for char in data:
                    # just skip over non-hex characters:
                    if char in string.hexdigits:
                        if self.text_entry.in_hex_mode:
                            read_chr = read_chr + char.upper()
                        else:
                            read_chr = read_chr + bin(int(char, 16))[2:].strip('L').zfill(4)
                        if len(read_chr) == max_length:
                            break
            else:
                # treat as binary file:
                input_file = open(file_path, 'rb')
                data = input_file.read(gEEProg.NUM_BYTES)
                if self.text_entry.in_hex_mode:
                    for b in data:
                        read_chr = read_chr + b.encode('hex').upper()
                else:
                    for b in data:
                        read_chr = read_chr + bin(ord(b))[2:].strip('L').zfill(8)
            
            self.text_entry.SetValue(read_chr)
            
            self.update_status('Reading: ' + file_path)
        except:
            wx.Bell()
            self.update_status("Failed to read data from file '{path}'".format(path=file_path),
                               'ERROR', 'RED')
        else:
            base_name = os.path.basename(file_path)
            if len(read_chr) == max_length:
                if file_extension.lower() == '.txt':
                    self.update_status("Read first 64 valid digits (32 bytes) from text file '{name}'".format(name=base_name),
                                       'OK', 'GREEN')
                elif file_extension.lower() == '.bin':
                    self.update_status("Read first 32 bytes from binary file '{name}'".format(name=base_name),
                                       'OK', 'GREEN')
                else:
                    self.update_status("Unrecognized file extension ({ext}), treated as binary. Read first 32 bytes from file '{name}'".format(ext=file_extension, name=base_name),
                                       '', 'YELLOW')
            else:
                self.update_status("File too short. All valid data found read in. '{name}'".format(name=base_name),
                                   '', 'YELLOW')
        finally:
            input_file.close()
    
    def on_open(self, event):
        """Handle opening files. Dialog defaults to binary files, provides text
        and all files as other filter options."""
        filters = 'Binary files (*.bin)|*.bin|Text files (*.txt)|*.txt|All files (*.*)|*.*'
        dlg = wx.FileDialog(None, style=wx.OPEN,
                            message='Select file to open...', wildcard=filters)
        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.GetPath()
        else:
            file_path = None
            self.status_bar.SetStatusText('No file selected.')
            self.status_bar.SetBackgroundColour(self.normal_status_color)
        dlg.Destroy()
        
        if file_path is not None:
            self.read_file(file_path)
    
    def on_save(self, event):
        """Handle saving of files. Dialog defaults to all formats, picks format
        based on extension. If an explicit format is selected from the menu,
        this overrides the typed file extension. Pads incomplete entries with
        zeros before writing."""
        filters = 'All files (*.*)|*.*|Binary file (*.bin)|*.bin|Text file (*.txt)|*.txt'
        filter_equiv = (None, '.bin', '.txt')
        dlg = wx.FileDialog(None, style=wx.SAVE|wx.OVERWRITE_PROMPT,
                            message='Save file as...', wildcard=filters)
        if dlg.ShowModal() == wx.ID_OK:
            file_path = dlg.GetPath()
            file_type = filter_equiv[dlg.GetFilterIndex()]
        else:
            file_path = None
            self.update_status('No file saved.')
        dlg.Destroy()
        
        if file_path is not None:
            self.text_entry.pad_with_fill()
            file_name, file_extension = os.path.splitext(file_path)
            base_name = os.path.basename(file_path)
            try:
                if file_type is None:
                    file_type = file_extension
                    
                if file_type.lower() == '.txt':
                    outfile = open(file_path, 'w')
                    if self.text_entry.in_hex_mode:
                        outfile.write(self.text_entry.GetValue())
                    else:
                        outfile.write(self.text_entry.bin_rep_to_hex_rep(self.text_entry.GetValue()))
                    
                    if file_extension.lower() == '.txt':
                        color = 'GREEN'
                        short_text = 'OK'
                    else:
                        color = 'YELLOW'
                        short_text = ''
                    self.update_status("Wrote text file '{name}'".format(name=base_name), short_text, color)
                else:
                    outfile = open(file_path, 'wb')
                    if self.text_entry.in_hex_mode:
                        data = self.text_entry.GetValue()
                    else:
                        data = self.text_entry.bin_rep_to_hex_rep(self.text_entry.GetValue())
                    for a, b in zip(data[::2], data[1::2]):
                        outfile.write(chr(int(a+b, 16)))
                    
                    if file_extension == '.txt':
                        color = 'YELLOW'
                        short_text = ''
                    else:
                        color = 'GREEN'
                        short_text = 'OK'
                    self.update_status("Wrote binary file '{name}'".format(name=base_name),
                                       short_text, color)
            except:
                wx.Bell()
                self.update_status("Failed to write file '{name}'".format(name=base_name),
                                   'ERROR', 'RED')
            finally:
                outfile.close()
    
    def on_exit(self, event):
        """Handles exit events, just passes to close."""
        self.Close(True)
    
    def on_close(self, event):
        """Handles close events. Ensure that the currently open port is
        instructed to exit automation mode and is then closed."""
        if self.port is not None:
            try:
                gEEProg.exit_automation_mode(self.port)
                time.sleep(0.2)
                self.port.close()
            except:
                pass
        self.Destroy()
    
    def read_press(self, event):
        """Handles presses of the read button. Clears the entry screen, then
        gets the contents of the chip."""
        try:
            new_text = gEEProg.read_chip(self.port)
            
            if self.text_entry.in_hex_mode:
                self.text_entry.SetValue(new_text)
            else:
                self.text_entry.SetValue(self.text_entry.hex_rep_to_bin_rep(new_text))
            self.update_status('Read complete.', 'OK', 'GREEN')
        except:
            # if read is successful, text will be written in
            # otherwise make it clear that read failed by wiping slate:
            self.text_entry.Clear()
            wx.Bell()
            self.update_status('Could not perform read.', 'ERROR', 'RED')
            if self.port is not None:
                dlg = wx.MessageDialog(self,
                                       'Could not perform read operation. ' \
                                       'Please ensure that the device is powered ' \
                                       'and that you have selected the correct serial port.',
                                       '2801Prog: Read Error',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
    
    def program_press(self, event):
        """Handles presses of the program button. Pads incomplete entries with
        zeros, then sends to the chip. Performs a verify to make sure the chip
        got written properly."""
        self.text_entry.pad_with_fill()
        if self.text_entry.in_hex_mode:
            value = self.text_entry.GetValue()
        else:
            value = self.text_entry.bin_rep_to_hex_rep(self.text_entry.GetValue())
        try:
            success = gEEProg.program_chip(self.port, value)
            if not success:
                wx.Bell()
                self.update_status('Verification following program failed', 'FAIL', 'RED')
                dlg = wx.MessageDialog(self,
                                       'Verification of program operation failed. ' \
                                       'This may indicate your chip is bad. ' \
                                       'Please check connections and try again.',
                                       '2801Prog: Program Verification Failure',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
            else:
                self.update_status('Program complete.', 'OK', 'GREEN')
        except:
            wx.Bell()
            self.update_status('Could not perform program.', 'ERROR', 'RED')
            if self.port is not None:
                dlg = wx.MessageDialog(self,
                                       'Could not perform program operation. ' \
                                       'Please ensure that the device is powered ' \
                                       'and that you have selected the correct serial port.',
                                       '2801Prog: Program Error',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
    
    def verify_press(self, event):
        """Handles presses of the verify button. Pads incomplete entries with
        zeros, then checks against chip. If verify fails, brings up a dialog
        with the present chip contents."""
        self.text_entry.pad_with_fill()
        if self.text_entry.in_hex_mode:
            value = self.text_entry.GetValue()
        else:
            value = self.text_entry.bin_rep_to_hex_rep(self.text_entry.GetValue())
        try:
            success = gEEProg.verify_chip(self.port, value)
            if success:
                self.update_status('Chip passed verification.', 'OK', 'GREEN')
            else:
                wx.Bell()
                self.update_status('Chip failed verification.', 'FAIL', 'RED')
                dlg = wx.MessageDialog(self,
                                       'Chip fails: contents do not match what ' \
                                       'is on your screen.\n' \
                                       'Actual contents of chip are:\n' \
                                       + gEEProg.read_chip(self.port) + \
                                       '\nScreen has:\n' \
                                       + value,
                                       '2801Prog: Verification Failure',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
        except:
            wx.Bell()
            self.update_status('Could not perform verify.', 'ERROR', 'RED')
            if self.port is not None:
                dlg = wx.MessageDialog(self,
                                       'Could not perform verify operation. ' \
                                       'Please ensure that the device is powered ' \
                                       'and that you have selected the correct serial port.',
                                       '2801Prog: Verification Error',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
    
    def erase_press(self, event):
        """Handles press of the erase button. Erases the chip, then verifies
        that it was erased by checking chip value. If chip is not all zeros,
        raises error dialog. Does NOT change what is entered on the screen."""
        try:
            result = gEEProg.erase_chip(self.port)
            if result != '0' * 2 * gEEProg.NUM_BYTES:
                wx.Bell()
                self.update_status('Chip did not erase properly.', 'FAIL', 'RED')
                dlg = wx.MessageDialog(self,
                                       'Erase operation was NOT successful. ' \
                                       'Chip still reads:\n' \
                                       + result + \
                                       '\nThis may indicate your chip is bad.',
                                       '2801Prog: Erase Not Successful',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
            else:
                self.update_status('Chip has been erased.', 'OK', 'GREEN')
        except:
            wx.Bell()
            self.update_status('Could not perform erase.', 'ERROR', 'RED')
            if self.port is not None:
                dlg = wx.MessageDialog(self,
                                       'Could not perform erase operation. ' \
                                       'Please ensure that the device is powered ' \
                                       'and that you have selected the correct serial port.',
                                       '2801Prog: Erase Error',
                                       style=wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()

if __name__ == '__main__':
    provider = wx.SimpleHelpProvider()
    wx.HelpProvider_Set(provider)

    app = wx.App(False)
    app.SetAppName(PROG_NAME)
    frame = MasterFrame(None, PROG_NAME)
    app.SetTopWindow(frame)

    # wait until very last minute to fill -- this is a hack to get the scrollbar
    # to go away under Redhat.
    frame.text_entry.pad_with_fill()
    # try to fix status bar bug on Ubuntu:
    #frame.SendSizeEvent()

    app.MainLoop()
