"""Client module for interacting with Sector Alarm API."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout

from .const import LOGGER
from .endpoints import get_data_endpoints, get_action_endpoints

_LOGGER = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Exception raised for authentication errors."""


class SectorAlarmAPI:
    """Class to interact with the Sector Alarm API."""

    API_URL = "https://mypagesapi.sectoralarm.net"

    def __init__(self, email, password, panel_id, panel_code):
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.panel_id = panel_id
        self.panel_code = panel_code
        self.access_token = None
        self.headers = {}
        self.session = None
        self.data_endpoints = get_data_endpoints(self.panel_id)
        self.action_endpoints = get_action_endpoints()

    async def login(self):
        """Authenticate with the API and obtain an access token."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        login_url = f"{self.API_URL}/api/Login/Login"
        payload = {
            "userId": self.email,
            "password": self.password,
        }
        try:
            async with async_timeout.timeout(10):
                async with self.session.post(login_url, json=payload) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Login failed with status code {response.status}")
                        raise AuthenticationError("Invalid credentials")
                    data = await response.json()
                    self.access_token = data.get("AuthorizationToken")
                    if not self.access_token:
                        _LOGGER.error("Login failed: No access token received")
                        raise AuthenticationError("Invalid credentials")
                    self.headers = {
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                    }
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout occurred during login")
            raise AuthenticationError("Timeout during login")
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Client error during login: {e}")
            raise AuthenticationError("Client error during login")

    async def retrieve_all_data(self):
        """Retrieve all relevant data from the API."""
        data = {}

        # Iterate over data endpoints
        for key, (method, url) in self.data_endpoints.items():
            if method == "GET":
                response = await self._get(url)
            elif method == "POST":
                # For POST requests, we need to provide the panel ID in the payload
                payload = {"PanelId": self.panel_id}
                response = await self._post(url, payload)
            else:
                _LOGGER.error(f"Unsupported HTTP method {method} for endpoint {key}")
                continue

            if response:
                data[key] = response
            else:
                _LOGGER.info(f"No data retrieved for {key}")

        locks_status = await self.get_lock_status()
        data["Lock Status"] = locks_status

        return data

    async def get_lock_status(self):
        """Retrieve the lock status."""
        url = f"{self.API_URL}/api/panel/GetLockStatus?panelId={self.panel_id}"
        response = await self._get(url)
        if response:
            return response
        else:
            _LOGGER.error("Failed to retrieve lock status")
            return []

    async def _get(self, url):
        """Helper method to perform GET requests with timeout."""
        try:
            async with async_timeout.timeout(10):
                async with self.session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            return await response.json()
                        else:
                            text = await response.text()
                            _LOGGER.error(f"Received non-JSON response from {url}: {text}")
                            return None
                    else:
                        text = await response.text()
                        _LOGGER.error(f"GET request to {url} failed with status code {response.status}, response: {text}")
                        return None
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout occurred during GET request to {url}")
            return None
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Client error during GET request to {url}: {e}")
            return None

    async def _post(self, url, payload):
        """Helper method to perform POST requests with timeout."""
        try:
            async with async_timeout.timeout(10):
                async with self.session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' in content_type:
                            return await response.json()
                        else:
                            text = await response.text()
                            _LOGGER.error(f"Received non-JSON response from {url}: {text}")
                            return None
                    else:
                        text = await response.text()
                        _LOGGER.error(f"POST request to {url} failed with status code {response.status}, response: {text}")
                        return None
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout occurred during POST request to {url}")
            return None
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Client error during POST request to {url}: {e}")
            return None

    async def arm_system(self, mode):
        """Arm the alarm system."""
        url = self.action_endpoints["Arm"][1]
        payload = {
            "ArmCode": self.panel_code,
            "PanelId": self.panel_id,
            "ArmType": mode,  # 'total' or 'partial'
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("System armed successfully")
            return True
        else:
            _LOGGER.error("Failed to arm system")
            return False

    async def disarm_system(self):
        """Disarm the alarm system."""
        url = self.action_endpoints["Disarm"][1]
        payload = {
            "DisarmCode": self.panel_code,
            "PanelId": self.panel_id,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug("System disarmed successfully")
            return True
        else:
            _LOGGER.error("Failed to disarm system")
            return False

    async def lock_door(self, serial_no):
        """Lock a specific door."""
        url = self.action_endpoints["Lock"][1]
        payload = {
            "LockSerial": serial_no,
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug(f"Door {serial_no} locked successfully")
            return True
        else:
            _LOGGER.error(f"Failed to lock door {serial_no}")
            return False

    async def unlock_door(self, serial_no):
        """Unlock a specific door."""
        url = self.action_endpoints["Unlock"][1]
        payload = {
            "LockSerial": serial_no,
            "PanelCode": self.panel_code,
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug(f"Door {serial_no} unlocked successfully")
            return True
        else:
            _LOGGER.error(f"Failed to unlock door {serial_no}")
            return False

    async def turn_on_smartplug(self, plug_id):
        """Turn on a smart plug."""
        url = f"{self.API_URL}/api/Panel/TurnOnSmartplug"
        payload = {
            "PanelId": self.panel_id,
            "DeviceId": plug_id,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug(f"Smart plug {plug_id} turned on successfully")
            return True
        else:
            _LOGGER.error(f"Failed to turn on smart plug {plug_id}")
            return False

    async def turn_off_smartplug(self, plug_id):
        """Turn off a smart plug."""
        url = f"{self.API_URL}/api/Panel/TurnOffSmartplug"
        payload = {
            "PanelId": self.panel_id,
            "DeviceId": plug_id,
        }
        result = await self._post(url, payload)
        if result is not None:
            _LOGGER.debug(f"Smart plug {plug_id} turned off successfully")
            return True
        else:
            _LOGGER.error(f"Failed to turn off smart plug {plug_id}")
            return False

    async def get_camera_image(self, serial_no):
        """Retrieve the latest image from a camera."""
        url = f"{self.API_URL}/api/camera/GetCameraImage"
        payload = {
            "PanelId": self.panel_id,
            "SerialNo": serial_no,
        }
        response = await self._post(url, payload)
        if response and response.get("ImageData"):
            import base64
            image_data = base64.b64decode(response["ImageData"])
            return image_data
        else:
            _LOGGER.error(f"Failed to retrieve image for camera {serial_no}")
            return None

    async def logout(self):
        """Logout from the API."""
        logout_url = f"{self.API_URL}/api/Login/Logout"
        await self._post(logout_url, {})
        await self.close()

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
