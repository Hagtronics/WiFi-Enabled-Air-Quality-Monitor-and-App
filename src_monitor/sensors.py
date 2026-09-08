"""
Sensor reading and data dictionary generation functionality.

Written by: Steve Hageman - August 2026
  License: https://unlicense.org/
"""
import random
import time
import board
from adafruit_ticks import ticks_ms, ticks_add, ticks_diff
from adafruit_pm25.i2c import PM25_I2C
import adafruit_scd4x
import adafruit_max1704x
from conversions import degc_to_degf, pm25_to_aqi_epa, dew_point_f


class Sensors:
    """ Sensors Class """
    def __init__(self):
        self._pm25_reading = 0           # ug/cubic ml
        self._pm10_reading = 0           # ug/cubic ml
        self._pm100_reading = 0          # ug/cubic ml
        self._co2_reading = 0            # ppm
        self._temperature_reading = 0    # Degrees F
        self._humidity_reading = 0       # Percent
        self._dew_point = 0              # Degrees F
        self._battery_reading = 0        # Volts
        self._battery_percentage = 0     # Percent
        self._aqi_epa = 0                # AQI Index 0-500

        # Calibration properties
        self.pm25_offset = 0
        self.co2_offset = 0
        self.humidity_offset = 0
        self.temperature_offset = 0.0

        # Start all the interfaces
        self.i2c = board.STEMMA_I2C()
        self.pm25 = PM25_I2C(self.i2c, None)

        self.scd4x = adafruit_scd4x.SCD4X(self.i2c)
        self.scd4x.start_periodic_measurement()

        self.max1704x = adafruit_max1704x.MAX17048(self.i2c)


    def _read_max1704x(self):
        self._battery_reading = self.max1704x.cell_voltage
        self._battery_percentage = self.max1704x.cell_percent

    def _read_scd4x(self):
        # Only updates once every 5 seconds when on periodic measurements
        self._co2_reading = self.scd4x.CO2 + self.co2_offset
        self._temperature_reading = degc_to_degf(self.scd4x.temperature) + self.temperature_offset
        self._humidity_reading = self.scd4x.relative_humidity + self.humidity_offset

    def _read_pm25(self):
        # PM25 Sensor only updates > once per second.
        # This appears to throw an exception if we try to read the sensor when it is internally updating
        # just retry.
        for attempt in range(3):
            try:
                aqdata = self.pm25.read()  # This is what will cause an exception
                self._pm25_reading = aqdata.get("pm25 env", 0) + self.pm25_offset
                self._pm10_reading = aqdata.get("pm10 env", 0)
                self._pm100_reading = aqdata.get("pm100 env", 0)
                self._aqi_epa = pm25_to_aqi_epa(self._pm25_reading)
                return True

            except Exception as e:
                print(f"PM25 read exception. Atempt #{attempt + 1}")
                time.sleep(1)

        print("PM25 read failed three try's.")
        return False


    def sensors_read(self):
        """ Reads all the sensors and stuffs the values in a dictionary """

        self._read_max1704x()
        self._read_scd4x()
        self._dew_point = dew_point_f(self._temperature_reading, self._humidity_reading)

        result = self._read_pm25()
        if result is False:
            # Set all PM25 an AQI values to None, because the sensor failed
            # to get a reading in 3 attempts over 3 seconds.
            self._pm10_reading = None
            self._pm25_reading = None
            self._pm100_reading = None
            self._aqi_epa = None

        return {
            'PM1.0' : self._pm10_reading,
            'PM2.5' : self._pm25_reading,
            'PM10.0': self._pm100_reading,
            'AQI_EPA': self._aqi_epa,
            'TEMPERATURE_F' : round(self._temperature_reading, 1),
            'HUMIDITY_PCT' : round(self._humidity_reading),
            'CO2_PPM' : self._co2_reading,
            'DEW_POINT_F' : round(self._dew_point, 1),
            'BATTERY_V' : round(self._battery_reading, 2),
            'BATTERY_PCT' :round(self._battery_percentage),
        }
