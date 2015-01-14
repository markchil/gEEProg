gEEProg
=======

Python module and GUI for controlling the 2801Prog, 2006Prog and other EEPROM
programmers.

Homepage: http://www.dasarodesigns.com/

Source home: https://github.com/markchil/gEEProg

Primary test configuration:

- Mac OS X 10.9.5
- Python 2.7.9
- PySerial 2.7
- Tkinter 2.7.9

Tested with comparable installations on Windows XP, Windows 7, Red Hat and
Ubuntu.

To install/run from source:

1) Ensure you have Python 2.7 installed: https://www.python.org/downloads/

2) Ensure you have Tkinter installed for Python 2.7:
   http://tkinter.unpythonic.net/wiki/How_to_install_Tkinter or
   http://www.tkdocs.com/tutorial/install.html

3) Ensure you have pip installed for Python 2.7:
   https://pip.pypa.io/en/latest/installing.html

4) Execute the command::
    
    pip install gEEProg
    
   (You may need to use sudo with this, or you can use
   `pip install --user gEEProg` to install the software only in your user
   directory.)

5) You can now access the gEEProg package's raw commands with `import gEEProg`.

6) The GUI is a pure Python script called gEEProgGUI. This will be installed in
   whatever bin directory pip uses. Typically there will be a line towards the
   end of pip's output that contains the path to the installed file (from when
   it changes its mode to 775). Assuming the directory containing gEEProgGUI is
   on your PATH, you can now launch the GUI simply by typing `gEEProgGUI` from
   the shell. If Python 2.7 is not the version of Python that is called when you
   type `python` at the shell, then you should modify the shebang statement at
   the beginning of the gEEProgGUI script to ensure it gets run with the correct
   version of Python.
