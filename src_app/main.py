"""
A Windows App to read the Adafruit Air Quality Monitors with my WiFi Network Code installed.
https://github.com/Hagtronics/WiFi-Enabled-Air-Quality-Monitor-and-App

Written by: Steve Hageman - August 2026
    License: https://unlicense.org/
"""

import os
import sys
import time

import regex as re

import ini  # Local INI file for AQM server information

try:
    from PyQt6 import QtCore, QtWidgets, uic
    from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QTableWidgetItem
    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, QTimer, QThreadPool
except ImportError:
    from PyQt5 import QtCore, QtWidgets, uic
    from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QTableWidgetItem
    from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, QTimer, QThreadPool

from resources.ui_main_window import Ui_MainWindow  # Compiled main_window.ui
from resources.info_popup import InfoPopup
from resources.aqm_client import AqmClient
from resources.ping import ping_ip
from resources.pyqt_threading import Worker, WorkerSignals


#$ ===== App Helper Functions =======================================
def set_dpi_awareness(state=True)->None:
    """
    Sets High DPI Awareness - must do this before spawning any window
    QT 6 sets awareness automatically
    A False state will turn DPI awareness off for PyQt 5 and 6

    Args:
        state (bool, optional): _description_. Defaults to True.
    """
    if state:  # True
        if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, on=True)
            print('Set: EnableHighDpiScaling')

        if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, on=True)
            print('Set: UseHighDpiPixmaps')

    else:  # False
        # This turns off DPI Scaling so that the font size does not change
        # Works on PyQt5 and PyQt6
        os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'Floor'
        os.environ['QT_FONT_DPI'] = '96'


# Fixes the PyQt window to the current size
def fix_window_to_current_size(window_reference)->None:
    width = window_reference.size().width()
    height = window_reference.size().height()
    window_reference.setFixedSize(width, height)


# AQI Color Code + Text as per EPA standard of 2024
# https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf
def get_color_coding(aqi):
    try:
        if aqi <= 50:
            color = 'QLabel { color: #00E400; }'
            text = 'Healthy'
        elif aqi <= 100:
            color = 'QLabel { color: #FFFF00; }'
            text = 'Moderate'
        elif aqi <= 150:
            color = 'QLabel { color: #FF8C00; }'
            text = 'Unhealthy for Sensitive Groups'
        elif aqi <= 200:
            color = 'QLabel { color: #FF4040; }'
            text = 'Unhealthy'
        elif aqi <= 300:
            color = 'QLabel { color: #D580E0; }'
            text = 'Very Unhealthy'
        else:
            color = 'QLabel { color: #FF3366; }'
            text = 'Hazardous'
    except:
        color = 'QLabel { color: #FFFFFF; }'
        text = 'No value'
    return (text, color)


#$ ===== Main Window Class ========================================================================
class MainWindow(QMainWindow):
    def __init__(self)->None:
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Air Quality Monitor WiFi App')

        # Server communication object
        self.selected_server = AqmClient(
            ip_prefix='192.168.68.',    # Default IP address prefix to start scan at
            ip_start=1,                 # Start of the scan range
            ip_end=254,                 # End of the scan range
            )

        # App server variables
        self.server_mac_address = ''

        self.thread_id = 0
        self.threadpool = QThreadPool()

        self.last_valid_reading_time = time.time()
        self.last_reading_elapsed_time = 0   # In seconds units
        self.reading_timeout = 60 * 10       # 10 is in minutes

        # Update GUI elements
        self.ui.lblStatus.setText('')

        # Update timer
        # Note timer interval CANNOT be less than the retry time of the get_data() function.
        # get_data() tries three times over 3 seconds total to make a reading.
        self.app_loop_timer = QTimer(self)
        self.app_loop_timer.timeout.connect(self.app_timing_loop)
        self.UPDATE_INTERVAL = 10_000  # milliSeconds
        #self.timer.start(self.UPDATE_INTERVAL)
        #self.timer.stop()  # Stop timer

        # Read Ini file server names and populate dropdown
        self.ui.cmbSelectServer.clear()
        self.ui.cmbSelectServer.addItem('Select Server...')
        try:
            for server in ini.AQM_MONITORS:
                self.ui.cmbSelectServer.addItem(server)
        except:
            popup = InfoPopup('Your ini.py list of servers is missing or invalid.', option='BUTTON')
            popup.open_popup()


        #$ ===== Slots UI Actions ===================================
        self.ui.cmbSelectServer.currentTextChanged.connect(self.on_server_selection)
        self.ui.btnExit.clicked.connect(self.on_exit_clicked)
        self.ui.btnPing.clicked.connect(self.on_ping_clicked)


    #$ ===== UI Slots Functions =====================================
    def on_server_selection(self, selection):
        # Stop the timer if a new server is going to be selected.
        self.app_loop_timer.stop()

        # Reset overview display and connection state.
        zero_data = {'TEMPERATURE_F': 0, 'AQI_EPA': 0, 'HUMIDITY_PCT': 0, 'CO2_PPM': 0}
        self.update_display(zero_data)
        self.server_mac_address = ''
        self.ui.lblStatus.setText('Connecting...')

        # Get the MAC address from ini.py.
        try:
            mac_addr = ini.AQM_MONITORS[selection]
        except KeyError:
            self.ui.lblStatus.setText('')
            InfoPopup(
                f'Your ini.py list of servers is invalid.\n'
                f'Key: {selection} could not be found.',
                option='BUTTON',
            ).open_popup()
            return

        # Validate the MAC address.
        if not isinstance(mac_addr, str) or not re.fullmatch(
            r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', mac_addr):
            self.ui.lblStatus.setText('')
            InfoPopup(
                f'Your ini.py list of servers is invalid.\n'
                f'Key: {selection} MAC address was "None" or "Invalid".',
                option='BUTTON',
            ).open_popup()
            return

        self.server_mac_address = mac_addr

        # Try to locate the server.
        popup_wait = InfoPopup('Trying to connect - Please wait...', option='NO_BUTTON')
        popup_wait.open_popup()

        self.selected_server.mac_address = self.server_mac_address

        if not self.selected_server.scan():
            popup_wait.close()
            InfoPopup(
                'Could not locate selected Server.\n'
                'Check the MAC Address in the "ini.py" file.\n'
                'Check that the Monitor is online.',
                option='BUTTON',
            ).open_popup()
            self.server_mac_address = ''
            self.ui.lblStatus.setText('No valid Server Selected.')
            return

        # Server found.
        print(f'Found: {self.server_mac_address} at {self.selected_server.ip_address}')
        popup_wait.close()
        self.ui.lblStatus.setText('Connected...')

        # Found the server, so start the update timer.
        self.app_loop_timer.start(self.UPDATE_INTERVAL)


    def on_ping_clicked(self):
        timer_state = self.app_loop_timer.isActive()
        if timer_state:
            self.app_loop_timer.stop()

        if self.server_mac_address == '' or self.selected_server.ip_address == '' or self.selected_server == '':
            popup = InfoPopup('Select a valid "AQM Server" first.', option='BUTTON')
            popup.open_popup()
            return

        popup = InfoPopup('PINGING - Please wait...', option='NO_BUTTON')
        popup.open_popup()

        result = ping_ip(self.selected_server.ip_address, times=4)
        popup.close_popup()

        if result:
            popup2 = InfoPopup('PING was successful!', option='BUTTON')
            popup2.open_popup()
        else:
            popup2 = InfoPopup('PING was not successful.\nServer could not be reached.', option='BUTTON')
            popup2.open_popup()

        if timer_state:
            self.app_loop_timer.start()


    def on_exit_clicked(self):
        sys.exit()


    #$ ===== Main App Timing Loop ===================================
    def app_timing_loop(self):
        if self.last_reading_elapsed_time > self.reading_timeout or self.selected_server.ip_address == '':
            # Rescan for the AQM Monitor Server because it has been gone a long time....
            self.ui.lblStatus.setText('No connection...')
            popup = InfoPopup('Server communication lost for more than 10 minutes.\nRescanning network...', option='NO_BUTTON')
            popup.open_popup()
            self.selected_server.reset_connection()
            if self.selected_server.scan():
                # Found the MAC address, and IP address. Restart normal timing loop.
                self.last_valid_reading_time = time.time()
                self.last_reading_elapsed_time = 0
                print(f'Found: {self.server_mac_address} at {self.selected_server.ip_address}')
                self.ui.lblStatus.setText('Connected...')

            time.sleep(2)
            popup.close_popup()
        else:
            # This is the normal path through the App Loop
            self.update_data_periodically()


    #$ ===== Update Data & Display ==================================
    def update_data_periodically(self):
        self.thread_id += 1

        # Make a worker
        worker = Worker(self.get_server_data, thread_id=self.thread_id)

        # This call gets the resulting data when the thread is done and updates the display
        worker.signals.result.connect(self.update_display)

        # Execute thread
        self.threadpool.start(worker)


    # Thread wrapper around actual get_data() call
    def get_server_data(self, progress_callback, thread_id):
        data = self.selected_server.get_data()
        return data


    # Called when 'get data' thread completes. See: update_data_periodically()
    def update_display(self, data):
        print(f'{data}')
        if data is not None:
            try:
                # === Info Tab ===
                self.ui.lcdAqi.display(data.get('AQI_EPA', 0))
                self.ui.lcdCo2.display(data.get('CO2_PPM', 0))
                temp = data.get('TEMPERATURE_F', 0)
                formatted_temp = f'{temp:.1f}'
                self.ui.lcdTemperature.display(formatted_temp)
                self.ui.lcdHumidity.display(data.get('HUMIDITY_PCT', 0))

                # Update AQI Index Label Text and Color
                text, color_style = get_color_coding(data.get('AQI_EPA', 0))
                self.ui.lblAqiQuality.setText(text)
                self.ui.lblAqiQuality.setStyleSheet(color_style)

                # === Details Tab ===
                self.ui.tableWidget.clearContents()

                # Sort dictionary keys alphabetically
                sorted_keys = sorted(data.keys(), key=str.lower)

                # Set up the table
                self.ui.tableWidget.setRowCount(len(sorted_keys))

                # Populate the table
                for row, key in enumerate(sorted_keys):
                    self.ui.tableWidget.setItem(row, 0, QTableWidgetItem(str(key)))
                    self.ui.tableWidget.setItem(row, 1, QTableWidgetItem(str(data[key])))
            except:
                pass

        # Update status bar and time since last good read, etc.
        status_txt = f'Connected to:{self.selected_server.ip_address}     '
        if data is None:
            self.last_reading_elapsed_time = time.time() - self.last_valid_reading_time  # Seconds
            formatted_time = time.strftime('%H:%M:%S', time.gmtime(self.last_reading_elapsed_time))
            status_txt += f'Last reading was: {formatted_time} ago (HH:MM:SS).'
        else:
            status_txt += 'Last read Ok...'
            self.last_valid_reading_time = time.time()  # Set to now()

        self.ui.lblStatus.setText(status_txt)


#$ ===== Main Function ==============================================
if __name__ == '__main__':

    set_dpi_awareness(True)
    app = QApplication(sys.argv)

    try:
        app.setStyleSheet(open('resources/python_org_style.qss').read())
    except:
        print('Could not read the style sheet. Using PyQt defaults.')

    window = MainWindow()
    fix_window_to_current_size(window)
    window.show()

    sys.exit(app.exec())

# ----- Fini -----
