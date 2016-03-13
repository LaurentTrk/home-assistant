"""
homeassistant.components.switch.harmony
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Switch for Harmony hub controlled devices.
"""
import logging
from homeassistant.components.switch import SwitchDevice
from homeassistant.components import harmony
LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return demo switches. """
    if discovery_info is not None:
        LOGGER.info('setup_platform for  %s', discovery_info)
        add_devices_callback([
            HarmonySwitch(harmony.HUB, discovery_info,  True, None)
        ])


class HarmonySwitch(SwitchDevice):
    """ Provides a demo switch. """
    def __init__(self, hub, discovery_info, state, icon):
        self._name = discovery_info[harmony.ATTR_LOGITECH_LABEL]
        self._id = discovery_info[harmony.ATTR_LOGITECH_ID]
        self._state = state
        self._hub = hub
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
    def is_on(self):
        """ True if device is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._state = True
        self._hub.change_device_state(self._id, self._state)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._state = False
        self._hub.change_device_state(self._id, self._state)
        self.update_ha_state()
