"""
Feather on-board LED Drivers.

Written by: Steve Hageman - August 2026
  License: https://unlicense.org/
"""
import board
import neopixel
import digitalio

class Leds():
    def __init__(self):
        # Initialize the onboard NeoPixel
        self.pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, auto_write=True)
        self.pixel.brightness = 0.3  # A reasonable default

        # Initialize the onboard Red LED
        self.led = digitalio.DigitalInOut(board.LED)
        self.led.direction = digitalio.Direction.OUTPUT

    def set_neopixel_color(self, red, green, blue):
        """ Color is a int = 0-255 """
        self.pixel[0] = (red, green, blue)
        # pixel.show()

    def set_neopixel_brightness(self, brightness):
        """ Brightness is a float = 0.0 to 1.0 """
        self.pixel.brightness = brightness
        # pixel.show()

    def set_led(self, on_state):
        # True = ON
        self.led.value = on_state

# - FINI -
