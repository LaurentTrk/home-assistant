"""
homeassistant.components.switch.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Demo platform that has two fake switches.
"""
import logging
from homeassistant.components.switch import SwitchDevice, DOMAIN
from homeassistant.components.zwave import (
    COMMAND_CLASS_SWITCH_BINARY, TYPE_BOOL, GENRE_USER, NETWORK,
    ATTR_NODE_ID, ATTR_VALUE_ID, ZWaveDeviceEntity)
    
LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo switches. """
    LOGGER.info('setup_platform for  %s', discovery_info)
    add_devices_callback([
        HarmonySwitch(discovery_info[ATTR_VALUE_ID], True, None)
    ])


class HarmonySwitch(SwitchDevice):
    """ Provides a demo switch. """
    def __init__(self, name, state, icon):
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._icon = icon

    @property
    def should_poll(self):
        """ No polling needed for a demo switch. """
        return False

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._name

    @property
    def icon(self):
        """ Returns the icon to use for device if any. """
        return self._icon

    @property
    def current_power_mwh(self):
        """ Current power usage in mwh. """
        if self._state:
            return 100

    @property
    def today_power_mw(self):
        """ Today total power usage in mw. """
        return 1500

    @property
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        self.update_ha_state()
