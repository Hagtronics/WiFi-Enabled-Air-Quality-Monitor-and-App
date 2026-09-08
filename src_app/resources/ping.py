"""
Useful little 'Ping' class.

Note: This will block the main thread.

Written by: Steve Hageman - August 2026
    License: https://unlicense.org/
"""
import subprocess


def ping_ip(ip_address, times=4):
    """
    Ping an IP address N times (selectable in code - see  below).

    Returns:
        True  - ping was successful
        False - ping failed, destination unreachable, timeout, or an exception occurred
    """

    try:
        # If you want to ping '4' times, change the '1' below to '4'
        result = subprocess.run(
            ["ping", "-n", str(times), "-w", "1000", ip_address],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        return result.returncode == 0

    except Exception:
        return False

# ----- FINI -----
