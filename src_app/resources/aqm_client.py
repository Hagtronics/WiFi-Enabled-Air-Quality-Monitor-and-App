"""
A PC based WiFi Client for the Air Quality Monitors

Written by: Steve Hageman - August 2026
    License: https://unlicense.org/
"""
import json
import urllib.request
import urllib.error
import subprocess
import re
import threading
import time
from datetime import datetime


class AqmClient:
    def __init__(self, ip_prefix='192.168.68.', ip_start=1, ip_end=254, port=8080, timeout=1.0) -> None:
        # ----------------------------------------------------
        # IP address scan range
        # ----------------------------------------------------
        self._ip_prefix = ip_prefix
        self._ip_start = ip_start
        self._ip_end = ip_end
        self._port = port
        self._timeout = timeout

        # General class properties users can get/set
        self.mac_address = ''   # Read/Write Must set to valid MAC address before scan()
        self.ip_address = ''    # Read only - IP Address currently in use
        self.last_error = ''    # Read only - Last error recorded


    # Normalize MAC address
    def _normalize_mac(self, mac_address):
        """Convert MAC address to Windows ARP format."""
        mac = mac_address.upper()
        mac = mac.replace(':', '-')
        return mac

    # Ping one IP address, 1 time
    def _ping(self, ip_address):
        """Ping one IP address."""
        try:
            subprocess.run(['ping', '-n', '1', '-w', '250', ip_address], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
        except Exception:
            pass

    # Ping entire IP range simultaneously
    def _ping_range(self):
        """Ping all IP addresses concurrently."""
        threads = []

        for address in range(self._ip_start, self._ip_end + 1):
            ip_address = f'{self._ip_prefix}{address}'
            thread = threading.Thread(target=self._ping, args=(ip_address,))
            thread.daemon = True
            thread.start()
            threads.append(thread)

        # Wait for all ping threads to finish.
        for thread in threads:
            thread.join()

    # Get ARP table
    def _get_arp_table(self):
        """Return the current Windows ARP table."""
        try:
            result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=2)
            return result.stdout
        except Exception:
            return ''

    # Find MAC address in ARP table
    def _find_mac_in_arp(self):
        """Return IP address associated with our MAC."""
        arp_table = self._get_arp_table()

        # ARP format is: ac-27-6e-b1-97-8c, Normal MAC address format is: AC:27:6E:B1:97:8C
        # So uppercase the ARP and replace the mac_address ':' with '-' so a match can be found
        for line in arp_table.splitlines():
            if self._normalize_mac(self.mac_address) in line.upper():
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    return match.group(1)

        return None


    # Scan network for MAC address
    def scan(self):
        """
        Scan the specified IP range looking for the
        specified MAC address.

        Returns:
            True  = Monitor found
            False = Monitor not found
        """
        if len(self.mac_address) == 0:
            return False

        self.ip_address = ''
        self.last_error = ''

        print(f'Scanning {self._ip_prefix}{self._ip_start}-{self._ip_end} for MAC {self.mac_address}...')

        start_time = time.monotonic()

        # First check the existing ARP table.
        # This makes repeated scans very fast when the
        # Monitor is already in the ARP cache.
        ip_addr = self._find_mac_in_arp()

        if ip_addr and ip_addr.startswith(self._ip_prefix):
            self.ip_address = ip_addr
            elapsed = time.monotonic() - start_time
            print(f'Monitor found at {self.ip_address} ({elapsed:.2f} seconds)')
            return True

        # MAC was not already in the ARP table. A successful Ping will (should?) add it.
        self._ping_range()
        time.sleep(0.1)
        ip_addr = self._find_mac_in_arp()

        if ip_addr and ip_addr.startswith(self._ip_prefix):
            # Still can't find it, so search for it.
            self.ip_address = ip_addr
            elapsed = time.monotonic() - start_time
            print(f'Monitor found at {self.ip_address} ({elapsed:.2f} seconds)')
            return True

        # Nothing found.
        elapsed = time.monotonic() - start_time
        self.last_error = f'Unable to find Monitor {self.mac_address}'
        print(f'Monitor not found in ({elapsed:.2f} seconds)')
        return False


    # Internal HTTP request
    def _get(self, endpoint):
        """Send a GET request and return decoded JSON."""
        if self.ip_address == '':
            self.last_error = 'Monitor IP address is not known. Call scan() first.'
            return None

        url = f'http://{self.ip_address}:{self._port}{endpoint}'

        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as response:
                data = response.read()

            result = json.loads(data.decode('utf-8'))

            # Request succeeded
            self.last_error = None
            return result

        except urllib.error.URLError as e:
            self.last_error = f'Unable to connect to AQM: {e}'
            return None

        except json.JSONDecodeError as e:
            self.last_error = f'Monitor returned invalid JSON: {e}'
            return None

        except Exception as e:
            self.last_error = f'Unexpected error: {e}'
            return None


    # ===== User Access =============================================
    def get_data(self):
        """Get the latest data."""
        print('starting get_data()')
        result = None

        # The usual - try three times pattern!
        for attempt in range(3):
            result = self._get('/data')
            if result is not None:
                break
            else:
                print(f'Reading Attempt = {attempt + 1}')
                time.sleep(1)

        return result

    # Forget current IP address
    def reset_connection(self):
        """
        Forget the current IP address.

        Call scan() afterward to rediscover the Monitor.
        """
        self.ip_address = ''
        self.last_error = ''


# ===== Simple live polling demonstration ===========================
if __name__ == '__main__':
    monitor = AqmClient(ip_prefix='192.168.68.', ip_start=1, ip_end=254, timeout=1)
    monitor.mac_address = 'AC:27:6E:B1:97:8C' # You have to have a valid MAC address here!
    if not monitor.scan():
        print(f'Unable to find MAC Address. Error: {monitor.last_error}')
        exit()
    else:
        print(f'Found MAC address: {monitor.mac_address} at IP address: {monitor.ip_address}')

    # Now you can interact with the monitor with a call such as,
    data = monitor.get_data()
    print(f'Data = {data}')

# ----- FINI -----
