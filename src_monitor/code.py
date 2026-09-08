"""
Air Quality Monitor Embedded Code for Adafruit Reverse TFT Feather ESP32-S3

Non-blocking HTTP server with Wi-Fi recovery and watchdog

A simple http call to the IP address serves up a simple webpage,
while a /data retrieves all the current data as a JSON dictionary of values.

The HTTP server is non-blocking so the Feather can perform
other tasks while waiting for HTTP requests.

Wi-Fi is monitored continuously.

If Wi-Fi is unavailable at startup:
    - The Feather continues running.
    - Wi-Fi is retried periodically.

If Wi-Fi goes offline:
    - The HTTP server is closed.
    - Sensor/display processing continues.
    - Wi-Fi is retried periodically.

When Wi-Fi returns:
    - The HTTP server is recreated.
    - mDNS is recreated.

A hardware watchdog will reboot the Feather if the main
program stops running.

Hardware is 100% based on the Adafruit Air Quality Monitor project,
  https://learn.adafruit.com/aqi-case

Written by: Steve Hageman - August 2026
  License: https://unlicense.org/
  
Github Source: https://github.com/Hagtronics/WiFi-Enabled-Air-Quality-Monitor-and-App

"""

import os
import wifi
import socketpool
import time
import json
import mdns
from microcontroller import watchdog as wdt
from watchdog import WatchDogMode

import sensors as sen
import display as dis
import leds
from conversions import aqi_epa_to_color

# ------------------------------------------------------------
# Configuration Section
# ------------------------------------------------------------
print('...Starting configuration...')

HTTP_PORT = 8080

# Try to reconnect to Wi-Fi at most once every X seconds.
WIFI_RETRY_INTERVAL = 20.0

# Update display interval - seconds
LED_UPDATE_INTERVAL = 1

# Update sensors interval - seconds
SENSOR_UPDATE_INTERVAL = 10

# ------------------------------------------------------------
# Watchdog
# ------------------------------------------------------------
wdt.timeout = 60  # Seconds
wdt.mode = WatchDogMode.RESET
wdt.feed()

# ------------------------------------------------------------
# Wi-Fi credentials from settings.toml
# ------------------------------------------------------------
MDNS_HOSTNAME = os.getenv('MDNS_HOSTNAME')
WIFI_SSID = os.getenv('CIRCUITPY_WIFI_SSID')
WIFI_PASSWORD = os.getenv('CIRCUITPY_WIFI_PASSWORD')

if not WIFI_SSID or not WIFI_PASSWORD or not MDNS_HOSTNAME:
    raise RuntimeError(
        'CIRCUITPY_WIFI_SSID or CIRCUITPY_WIFI_PASSWORD or MDNS_HOSTNAME'
        ' not found in settings.toml'
    )

# ------------------------------------------------------------
# Sensor Offsets from settings.toml
# ------------------------------------------------------------
OFFSET_TEMPERATURE_F = float(os.getenv('OFFSET_TEMPERATURE_F') or 0)
OFFSET_CO2_PPM = int(os.getenv('OFFSET_CO2_PPM') or 0)
OFFSET_HUMIDITY_PCT = int(os.getenv('OFFSET_HUMIDITY_PCT') or 0)
OFFSET_PM25 = int(os.getenv('OFFSET_PM25') or 0)

# ------------------------------------------------------------
# Network state
# ------------------------------------------------------------
pool = None
server = None
mdns_server = None
network_active = False
last_wifi_attempt = 0.0

# ------------------------------------------------------------
# Start HTTP server
# ------------------------------------------------------------
def start_http_server():

    global pool
    global server

    # --------------------------------------------------------
    # Make sure an old server is gone.
    # --------------------------------------------------------
    stop_http_server()

    # --------------------------------------------------------
    # Create a new socket pool for the current Wi-Fi connection.
    # --------------------------------------------------------
    pool = socketpool.SocketPool(wifi.radio)

    server = pool.socket(
        pool.AF_INET,
        pool.SOCK_STREAM,
    )

    server.setsockopt(
        pool.SOL_SOCKET,
        pool.SO_REUSEADDR,
        1,
    )
    server.bind(('0.0.0.0', HTTP_PORT))
    server.listen(1)

    # IMPORTANT:
    # Do not allow accept() to block the main program.
    server.setblocking(False)

    print('HTTP server listening on port', HTTP_PORT)

# ------------------------------------------------------------
# Stop HTTP server
# ------------------------------------------------------------
def stop_http_server():
    global pool
    global server

    if server is not None:
        try:
            server.close()
        except OSError:
            pass

        server = None
    pool = None

# ------------------------------------------------------------
# Start mDNS
# ------------------------------------------------------------
def start_mdns():
    global mdns_server
    mdns_server = None
    try:
        mdns_server = mdns.Server(wifi.radio)
        mdns_server.hostname = MDNS_HOSTNAME
        mdns_server.advertise_service(
            service_type='_http',
            protocol='_tcp',
            port=HTTP_PORT
        )
        print('mDNS HTTP service advertised')

    except Exception as e:
        # mDNS failure should not kill the application.
        mdns_server = None
        print('mDNS error:', e)

# ------------------------------------------------------------
# Stop mDNS
# ------------------------------------------------------------
def stop_mdns():
    global mdns_server
    # A new Server object will be created after reconnection.
    mdns_server = None

# ------------------------------------------------------------
# Wi-Fi connected
# ------------------------------------------------------------
def wifi_connected():
    global network_active

    print('\nWi-Fi connected')
    print('IP address:', wifi.radio.ipv4_address)
    print('Hostname:', wifi.radio.hostname)

    # Rebuild network services for this connection.
    try:
        start_mdns()
        start_http_server()
        network_active = True
        print('Network services started')

    except Exception as e:
        print('Network service startup error:', e)
        stop_http_server()
        stop_mdns()
        network_active = False

# ------------------------------------------------------------
# Wi-Fi disconnected
# ------------------------------------------------------------
def wifi_disconnected():
    global network_active
    stop_http_server()
    stop_mdns()
    network_active = False

# ------------------------------------------------------------
# Try to connect to Wi-Fi
# ------------------------------------------------------------
def try_wifi_connect():
    global last_wifi_attempt
    now = time.monotonic()

    # Already connected.
    if wifi.radio.connected:
        return

    # Do not attempt another connection too soon.
    if now - last_wifi_attempt < WIFI_RETRY_INTERVAL:
        return

    last_wifi_attempt = now
    print('\nAttempting Wi-Fi connection...')

    try:
        wifi.radio.hostname = MDNS_HOSTNAME
        wifi.radio.connect(
            WIFI_SSID,
            WIFI_PASSWORD
        )

        # connect() returned successfully. Verify the actual radio state.
        if wifi.radio.connected:
            wifi_connected()
        else:
            print('Wi-Fi connection attempt failed')

    except Exception as e:
        print('Wi-Fi connection failed:', e)

# ------------------------------------------------------------
# HTTP service
# ------------------------------------------------------------
def service_http():
    global current_sensor_data

    # No server means Wi-Fi/network services are unavailable.
    if server is None:
        return

    client = None
    # Check for an incoming connection.
    #
    # Because the server socket is non-blocking, this will
    # immediately raise EAGAIN (11) if nobody is connecting.
    try:
        client, addr = server.accept()
    except OSError as e:
        if e.errno == 11:
            return
        # Any other accept error probably means the network
        # socket is no longer valid.
        print('Server accept error:', e)
        return

    # Valid client.
    try:
        # Receive HTTP request - no blocking
        client.setblocking(False)
        buffer = bytearray(1024)
        try:
            length = client.recv_into(buffer)
        except OSError as e:
            if e.errno == 11:  # Resource temporarily unavailable.
                return
            if e.errno == 128:  # socket isn't connected.
                return
            raise

        if length <= 0:
            return

        request = buffer[:length]

        # Request is for JSON data
        if b'GET /data ' in request:
            data = dict(current_sensor_data)
            # Add RSSI to data. Only read RSSI while actually connected.
            if wifi.radio.connected:
                try:
                    data['RSSI_DB'] = wifi.radio.ap_info.rssi
                except Exception:
                    data['RSSI_DB'] = None
            else:
                data['RSSI_DB'] = None
            status = '200 OK'
            print('Sent: Sensors')

            # Convert data to JSON, Newline terminates the message.
            json_data = json.dumps(data) + '\n'
            body = json_data.encode('utf-8')

            # Build complete HTTP response
            header = (
                'HTTP/1.1 ' + status + '\r\n'
                'Content-Type: application/json\r\n'
                'Content-Length: ' + str(len(body)) + '\r\n'
                'Connection: close\r\n'
                '\r\n'
            ).encode('utf-8')

        # Request is for webpage
        elif b'GET / ' in request:
            # Get the current sensor values.
            aqi_epa = current_sensor_data.get('AQI_EPA', 999)
            co2_ppm = current_sensor_data.get('CO2_PPM', 999)
            temperature_f = current_sensor_data.get('TEMPERATURE_F', 999)
            humidity_pct = current_sensor_data.get('HUMIDITY_PCT', 999)
            aqi_color = aqi_epa_to_color(aqi_epa)

            # HTML page template
            html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <meta http-equiv='Content-type' content='text/html;charset=utf-8'>
                <meta name='viewport' content='width=device-width, initial-scale=1'>
                <title>{MDNS_HOSTNAME}</title>
                <style>
                    html {{
                        font-family: sans-serif;
                        background-color: white;
                        text-align: center;
                    }}
                    h1 {{
                        font-size: 5em;
                        font-weight: bold;
                        margin: 20px;
                    }}
                    .aqm {{
                        font-size: 4em;
                        color: {aqi_color};
                        margin: 20px;
                    }}
                    .value {{
                        font-size: 1em;
                        color: black;
                        margin: 10px;
                    }}
                </style>
                </head>
                <body>
                    <h1>{MDNS_HOSTNAME}</h1>
                    <div class='aqm'>Air Quality Index (EPA) = {aqi_epa}</div>
                    <div class='value'>CO2 = {co2_ppm} ppm</div>
                    <div class='value'>Temperature = {temperature_f:.1f} ℉</div>
                    <div class='value'>Humidity = {humidity_pct} %</div>
                </body>
                </html>
            """
            status = '200 OK'
            body = html.encode('utf-8')
            print('Sent: HTML page')

            # Build complete HTTP response
            header = (
                'HTTP/1.1 ' + status + '\r\n'
                'Content-Type: text/html; charset=utf-8\r\n'
                'Content-Length: ' + str(len(body)) + '\r\n'
                'Connection: close\r\n'
                '\r\n'
            ).encode('utf-8')

        # Unknown request
        else:
            data = {
                'error': 'Unknown endpoint',
            }
            status = '404 Not Found'
            print(f'Received: Invalid request = {request}')

            body = b'\n'  # Empty body
            # Build complete HTTP response
            header = (
                'HTTP/1.1 ' + status + '\r\n'
                'Content-Type: application/json\r\n'
                'Content-Length: ' + str(len(body)) + '\r\n'
                'Connection: close\r\n'
                '\r\n'
            ).encode('utf-8')

        response = header + body

        # Actually send complete response
        sent = 0
        while sent < len(response):
            try:
                sent_count = client.send(
                    response[sent:],
                )
                if sent_count > 0:

                    sent += sent_count
                else:
                    time.sleep(0.001)

            except OSError as e:
                if e.errno == 11:  # Resource temporarily unavailable.
                    # Socket isn't ready to accept more data.
                    time.sleep(0.001)
                    continue

                if e.errno == 128:  # Socket isn't connected
                    # PC closed the connection.
                    break
                raise

    except OSError as e:
        # ----------------------------------------------------
        # Normal connection-level failures.
        # ----------------------------------------------------
        if e.errno not in (11, 128):
            print('Socket error:', e)
    finally:
        if client is not None:
            try:
                client.close()
            except OSError:
                pass


# ------------------------------------------------------------
# Start of main code block
# ------------------------------------------------------------

# Initialize Wi-Fi
wifi.radio.hostname = MDNS_HOSTNAME
try_wifi_connect()

# Board / Sensors / Display Startup
current_sensor_data = {}    # The Global Sensor Data

sensors = sen.Sensors()
sensors.pm25_offset = OFFSET_PM25
sensors.co2_offset = OFFSET_CO2_PPM
sensors.temperature_offset = OFFSET_TEMPERATURE_F
sensors.humidity_offset = OFFSET_HUMIDITY_PCT

# Start display class, play splash screen
display = dis.Display()
display.play_splash_screen()

# Make reading after startup delay of about 5 seconds.
current_sensor_data = sensors.sensors_read()

# Onboard Red LED
onboard_leds = leds.Leds()
red_led = True
onboard_leds.set_led(True)

# ------------------------------------------------------------
# Main program loop
# ------------------------------------------------------------
last_led_update = time.monotonic()
last_update_sensors = time.monotonic()

print('...Entering main loop...')

while True:
    wdt.feed()
    now = time.monotonic()

    # Monitor Wi-Fi connection.
    if wifi.radio.connected:
        # We have Wi-Fi but our services aren't active.
        if not network_active:
            wifi_connected()
    else:
        # Wi-Fi is not connected, kill services.
        if network_active:
            wifi_disconnected()

        # Periodically attempt reconnection.
        try_wifi_connect()

    # Onboard LED Update every X seconds
    if now - last_led_update >= LED_UPDATE_INTERVAL:
        last_led_update = now

        if red_led is True:
            onboard_leds.set_led(False)
            red_led = False
        else:
            onboard_leds.set_led(True)
            red_led = True

    # Sensor and Display update once every X seconds.
    # This continues even while Wi-Fi is unavailable.
    if now - last_update_sensors >= SENSOR_UPDATE_INTERVAL:
        last_update_sensors = now
        current_sensor_data = sensors.sensors_read()
        display.update_display(current_sensor_data)
        # Spit data out the serial port.
        print(current_sensor_data)

    # Service HTTP without blocking.
    if wifi.radio.connected and network_active:
        service_http()
        onboard_leds.set_neopixel_color(red=0, blue=255, green=0)
    else:
        onboard_leds.set_neopixel_color(red=0, blue=0, green=0)

# - FINI -
