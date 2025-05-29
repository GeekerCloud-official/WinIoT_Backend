# WinIoT_Backend

Restful API backend for remote control Windows peripherals devices

## Current features

1. Monitor power control via Restful API

2. Monitor brightness control via Restful API

3. Volume mute/unmute control via Restful API

4. More features are under devloping

## API Documentation

Base URL: http://<FLASK_HOST>:<FLASK_PORT>
(The values for <FLASK_HOST> and <FLASK_PORT> are determined by the .env file or default values in the code, defaulting to http://0.0.0.0:5000)
Authentication:
If API_AUTH_ENABLED is set to True in the .env file (or app.config['API_AUTH_ENABLED'] is True in the code), all API endpoints require authentication.
Authentication is performed by including an X-API-Key in the request header, whose value should match the API_KEY configured in the .env file or the code.

1. Monitor Control (via Twinkle Tray)

1.1. Turn On Specified Monitor (VCP)
Path: /api/monitor/<monitor_num>/on
Method: GET, POST
Path Parameters:
monitor_num (integer): The monitor number (starting from 1).
Description: Sends a VCP power-on command (0xD6:1) to the specified monitor.

1.2. Turn Off/Standby Specified Monitor (VCP)
Path: /api/monitor/<monitor_num>/off
Method: GET, POST
Path Parameters:
monitor_num (integer): The monitor number (starting from 1).
Description: Sends a VCP power-off/standby command (0xD6:5) to the specified monitor.

1.3. Set Monitor Brightness
Path: /api/monitor/<monitor_num_str>/brightness/<level>
Method: GET, POST
Path Parameters:
monitor_num_str (path/string):
Can be a single monitor number (e.g., "1", "2").
Can be "0" or "all" to represent all monitors.
level (integer): Brightness level, ranging from 0 to 100.
Description: Sets the brightness for a specified monitor or all monitors.

1.4. Get Monitor Status (Placeholder)
Path: /api/monitor/<monitor_num>/status-placeholder
Method: GET
Path Parameters:
monitor_num (integer): The monitor number (starting from 1).
Description: This is a placeholder endpoint for querying monitor status; it does not currently return actual status information.

2. System Audio Control (via pycaw)

2.1. Mute System Audio
Path: /api/audio/mute
Method: GET, POST
Description: Mutes the system's master audio volume.

2.2. Unmute System Audio
Path: /api/audio/unmute
Method: GET, POST
Description: Unmutes the system's master audio volume.

2.3. Toggle System Audio Mute
Path: /api/audio/mute/toggle
Method: GET, POST
Description: Toggles the mute state of the system's master audio volume.

2.4. Get System Audio Status
Path: /api/audio/status
Method: GET
Description: Gets the current mute status of the system's master audio volume.

## Additional Instructions

1. For monitors control [TwinkleTray](https://github.com/xanderfrangos/twinkle-tray) must be installed first

2. You can integrate these api to [HomeAssistant](https://github.com/home-assistant) in order to make your PC Peripherals intelligently



