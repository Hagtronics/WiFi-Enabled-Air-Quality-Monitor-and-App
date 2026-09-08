## WiFi enabled Air Quality Monitor PC Based App.  
Tested on Windows 7, 10 & 11  
Python 3.12+  
PyQt5 or 6  

Note: The file: 'main_window.ui' is the original QT6 Designer file - it is included in case anyone wants to make changes or additions to the form layout. This file should be compiled with the 'pyuic6' compiler to a file named: 'ui_main_window.py'. Also be sure to include the PyQt5 imports at the top of the compiled python file if PyQt5 compatibility is required.  

The command to compile the .ui file for windows is shown here: ```pyuic6 -x main_window.ui -o ui_main_window.py```
   
You need the files here and the files in the directory: 'resources' for the App to function correctly.  

The directory tree on your PC should look like,  

PC Side  
├── resources  
│   ├── __init__.py  
│   ├── aqm_client.py  
│   ├── info_popup.py  
│   ├── main_window.ui  
│   ├── ping.py  
│   ├── pyqt_threading.py  
│   ├── python_org_style.qss  
│   └── ui_main_window.py  
├── ini.py  
└── main.py  

--- Fini ---
  
