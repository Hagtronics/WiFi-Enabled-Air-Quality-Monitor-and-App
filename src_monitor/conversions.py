"""
Environmental math conversions - all static functions

Written by: Steve Hageman - August 2026
  License: https://unlicense.org/
"""

def degc_to_degf(temperature_celsius):
    """
    Converts Degrees Celsius to Degrees Fahrenheit
    """
    temperature_fahrenheit = temperature_celsius * 9 / 5 + 32
    return temperature_fahrenheit


def pm25_to_aqi_epa(pm25_raw):
    """
    Convert PM2.5 concentration (µg/m³) to AQI
    using current EPA PM2.5 AQI breakpoints as of 2024
    https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf

    pm25_raw : float
        PM2.5 concentration in µg/m³.

    Returns:
        AQI as an integer, limited to 0-500.
    """

    breakpoints = [
        # (C_low, C_high, I_low, I_high)
        (0.0,    9.0,    0,  50),
        (9.1,   35.4,   51, 100),
        (35.5,  55.4,  101, 150),
        (55.5, 125.4,  151, 200),
        (125.5, 225.4, 201, 300),
        (225.5, 325.4, 301, 500),
    ]

    for C_low, C_high, I_low, I_high in breakpoints:
        if C_low <= pm25_raw <= C_high:
            aqi = (
                ((I_high - I_low) / (C_high - C_low))
                * (pm25_raw - C_low)
                + I_low
            )
            return round(aqi)

    # Above the highest displayed AQI range
    return 500


def aqi_epa_to_color(aqi_epa):
    """ Returns a string of the current (2026) EPA hex color numbers.
    https://www.epa.gov/system/files/documents/2024-02/pm-naaqs-air-quality-index-fact-sheet.pdf
    These colors, especially the red ones, are probably not discernable on the Feather TFT display.
    """
    if aqi_epa <= 50:
        aqi_color = '#00e400'   # Good
    elif aqi_epa <= 100:
        aqi_color = '#FFFF00'   # Moderate
    elif aqi_epa <= 150:
        aqi_color = '#FF7E00'   # Unhealthy for SG
    elif aqi_epa <= 200:
        aqi_color = '#FF0000'   # Unhealthy
    elif aqi_epa <= 300:
        aqi_color = '#99004C'   # Very Unhealthy
    else:
        aqi_color = '#7E0023'   # Unhealthy+ = red

    return aqi_color


def hex_string_to_int(hex_color):
    """
    When you need a color number like: #99004C converted
    to a real number for use in a integer color number.
    """
    return int(hex_color.lstrip('#'), 16)


def dew_point_f(temp_f, humidity):
    """
    Approximate dew point (°F) using a lookup table
    and bilinear interpolation.

    Designed for:
        Temperature: 30-90°F
        Humidity:    20-80%

    Inputs outside the range are clamped.
    """

    temps = [30, 40, 50, 60, 70, 80, 90]
    hums  = [20, 30, 40, 50, 60, 70, 80]

    # Dew point lookup table (°F)
    dew_point_table = [
        [-6,  2,  9, 14, 18, 21, 25],  # 30°F
        [ 2, 11, 18, 23, 27, 31, 34],  # 40°F
        [10, 20, 27, 32, 37, 41, 44],  # 50°F
        [19, 28, 36, 41, 46, 50, 54],  # 60°F
        [27, 37, 45, 51, 55, 60, 64],  # 70°F
        [35, 46, 54, 60, 65, 69, 73],  # 80°F
        [44, 54, 62, 69, 74, 79, 83],  # 90°F
    ]

    # Clamp inputs
    temp_f = max(30.0, min(90.0, temp_f))
    humidity = max(20.0, min(80.0, humidity))

    # Find temperature interval
    ti = min(int((temp_f - 30.0) // 10), 5)

    # Find humidity interval
    hi = min(int((humidity - 20.0) // 10), 5)

    # Interpolation fractions
    ft = (temp_f - temps[ti]) / 10.0
    fh = (humidity - hums[hi]) / 10.0

    # Four surrounding values
    q11 = dew_point_table[ti][hi]
    q12 = dew_point_table[ti][hi + 1]
    q21 = dew_point_table[ti + 1][hi]
    q22 = dew_point_table[ti + 1][hi + 1]

    # Bilinear interpolation
    return (
        q11 * (1 - ft) * (1 - fh) +
        q21 * ft       * (1 - fh) +
        q12 * (1 - ft) * fh       +
        q22 * ft       * fh
    )

# - FINI -
