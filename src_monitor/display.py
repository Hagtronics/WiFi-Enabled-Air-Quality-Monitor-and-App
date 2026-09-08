"""
Provides a Grid Layout Display Class

Written by: Steve Hageman - August 2026
  License: https://unlicense.org/
"""
import time
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
from conversions import hex_string_to_int, aqi_epa_to_color

class Display:
    def __init__(self):
        SIZE = 3

        display = board.DISPLAY
        main_group = displayio.Group()
        display.root_group = main_group

        layout = GridLayout(
            x=0,
            y=0,
            width=240,
            height=135,
            grid_size=(2, 2),
            cell_padding=20,
        )
        self.labels = []

        self.labels.append(label.Label(terminalio.FONT, scale=SIZE, x=0, y=0, text=''))
        layout.add_content(self.labels[0], grid_position=(0, 0), cell_size=(1, 1))

        self.labels.append(label.Label(terminalio.FONT, scale=SIZE, x=0, y=0, text=''))
        layout.add_content(self.labels[1], grid_position=(1, 0), cell_size=(1, 1))

        self.labels.append(label.Label(terminalio.FONT, scale=SIZE, x=0, y=0, text=''))
        layout.add_content(self.labels[2], grid_position=(0, 1), cell_size=(1, 1))

        self.labels.append(label.Label(terminalio.FONT, scale=SIZE, x=0, y=0, text=''))
        layout.add_content(self.labels[3], grid_position=(1, 1), cell_size=(1, 1))

        main_group.append(layout)


    def _update_grid_label(self, index=0, text='', fg_color=None, bg_color=None):
        """ Index is 0-3, colors are in hex form: 0xFFFFFF """
        self.labels[index].text = text
        if fg_color is not None:
            self.labels[index].color = fg_color
        if bg_color is not None:
            self.labels[index].background_color = bg_color


    def play_splash_screen(self):
        self._update_grid_label(0, 'Starting', 0xFF0000)
        time.sleep(1.0)
        self._update_grid_label(0, 'Starting', 0xFF4500)
        time.sleep(1.0)
        self._update_grid_label(0, 'Starting', 0xFF8C00)
        time.sleep(1.0)
        self._update_grid_label(0, 'Starting', 0xFFF000)
        time.sleep(1.0)
        self._update_grid_label(0, 'Starting', 0x7FFF00)
        time.sleep(1.0)
        self._update_grid_label(0, 'Starting', 0x00FF00)
        time.sleep(1.0)
        self._update_grid_label(0, 'Connecting', 0x0000FF)
        self._update_grid_label(2, 'To WiFi', 0x0000FF)


    def update_display(self, data):
        try:
            aqi_epa = round(data.get('AQI_EPA', 999))  # If something is amiss - returns '999'
            temp_f = round(data.get('TEMPERATURE_F', 999))
            rh = round(data.get('HUMIDITY_PCT', 999))
            co2 = round(data.get('CO2_PPM', 999))
        except:
            pass

        # Update main label
        fg_color = hex_string_to_int(aqi_epa_to_color(aqi_epa))

        txt = f'Q={aqi_epa}'
        self._update_grid_label(0, text=txt, fg_color=fg_color)

        #txt = f'C={co2}'
        txt = f'T={temp_f}'
        self._update_grid_label(1, text=txt, fg_color=0x00FF00)

        #txt = f'T={temp_f}'
        txt = f'C={co2}'
        self._update_grid_label(2, text=txt, fg_color=0x00FF00)

        txt = f'H={rh}'
        self._update_grid_label(3, text=txt, fg_color=0x00FF00)

# - Fini -
