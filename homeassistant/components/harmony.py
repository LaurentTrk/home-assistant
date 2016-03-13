"""
homeassistant.components.harmony
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a Logitech Harmony Hub.
Need pyharmony lib
"""
import logging
import time
import threading

from homeassistant.helpers import event
from homeassistant.const import ( EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED,
                                  STATE_OFF, STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                  CONF_PLATFORM)
import homeassistant.bootstrap as bootstrap

from pyharmony.client import create_and_connect_client
from pyharmony.auth import swap_auth_token, login
from http.server import BaseHTTPRequestHandler, HTTPServer

LOGGER = logging.getLogger(__name__)

DOMAIN = "harmony"
HUB = None
DEPENDENCIES = []

DISCOVER_SWITCHES = "harmony.switch"
ATTR_LOGITECH_ID = "logitech_id"
ATTR_LOGITECH_LABEL = "logitech_label"
SERVICE_SEND_DEVICE_COMMAND = "send_device_command"

# pylint: disable=unused-argument
def setup(hass, config):
    """
        Setup Harmony.
        Connect to configured Harmony hub.
        """
    # pylint: disable=global-statement, import-error
    global HUB

    LOGGER.info('Setup Harmony')
    ip = config['harmony']['ip']
    email = config['harmony']['email']
    password = config['harmony']['password']

    # Setup switches
    harmony_config = config.copy()
    harmony_config['switch'] = {CONF_PLATFORM: 'harmony'}
    bootstrap.setup_component(hass, 'switch', harmony_config)

    # Initialize connection with hub
    HUB = Harmony(email, password, ip, hass, event)
    HUB.initialize()

    # Start a roku emulated server to receive command from hub
    roku = RokuEmulatedServer(hass)
    roku.serveInAnotherThread()

    return True

class Harmony():

    def __init__(self, email, password, ip, hass, event):
        self.email = email
        self.password = password
        self.ip = ip   
        self.hass = hass        
        self.port = 5222
        self.poweroff_id = "-1"
        self.event = event
        self.monitor_hub_events=False
        self.logitech_auth_url = ('https://svcs.myharmony.com/CompositeSecurityServices/Security.svc/json/GetUserAuthToken')
        self.devices = []

        self.hass.services.register(DOMAIN, SERVICE_TURN_ON, self.turn_on)
        self.hass.services.register(DOMAIN, SERVICE_TURN_OFF, self.turn_off)
        self.hass.services.register(DOMAIN, SERVICE_SEND_DEVICE_COMMAND, self.send_device_command)

        self.session_token = None
    
    def connect(self):
        
        if self.session_token == None:
            #try again with new token
            self.get_token()
                                        
        try:
            self.client = create_and_connect_client(self.ip, self.port, self.session_token, self.message_from_hub)
        except:
            LOGGER.error('Could not connect to Harmony. Retry with new token.')
            self.get_token()
            self.client = create_and_connect_client(self.ip, self.port, self.session_token, self.message_from_hub)

    def message_from_hub(self, msg):
        if len(msg.get_payload()) == 1 and msg.get_payload()[0].tag == '{connect.logitech.com}event':
            # Receive spontaneous event from hub
            payload = msg.get_payload()[0]
            LOGGER.info('Receive logitech event from Hub : %s, %s', payload.attrib['type'], payload)
            if (payload.attrib['type'] == 'harmony.engine?startActivityFinished'):
                self.update_activities_from_hub()

        
    def disconnect(self):
        self.client.disconnect(send_close=False)
            
    def get_token(self, event=None):
        # Log into the Logitech Harmony web service to get token
        token = login(self.email, self.password)        
        # Swap it for a session token
        self.session_token = swap_auth_token(self.ip, self.port, token)
        
    def initialize(self, event=None):
                        
        LOGGER.info('Updating Harmony entities')
        self.connect()
        self.update_activities_from_hub()

    def update_activities_from_hub(self):
        # Get the current activity so we can set the state
        LOGGER.info('Getting current activity')
        active_activity = str(self.client.get_current_activity())#[7:]
                
        # Get the configuration from the hub
        LOGGER.info('Getting configuration')
        data = self.client.get_config()
        
        self.activities = []
        for activity in data['activity']:
            if not activity['id'] == self.poweroff_id:
                self.add_activity_from_hub(activity, active_activity)


        for device in data['device']:
            if not device['id'] in self.devices:
                self.devices.append(device['id'])
                self.hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_SWITCHES,
                    ATTR_DISCOVERED: {
                        ATTR_LOGITECH_ID: device['id'],
                        ATTR_LOGITECH_LABEL: device['label']
                    }
                })


    def add_activity_from_hub(self, activity, active_activity):
        LOGGER.info('Adding activity %s' % activity['label'])
        activity_dict = {}
        activity_dict['harmony_name'] = activity['label']
        activity_dict['harmony_id'] = activity['id']
        activity_dict['entity_id'] = activity['label'].replace (" ", "_").lower()

        if activity_dict['harmony_id'] == str(active_activity):
            state = STATE_ON
        else:
            state = STATE_OFF

        self.hass.states.set('harmony.' + activity_dict['entity_id'], state)
        self.activities.append(activity_dict)   
       	
    def get_activity_by_entity(self, entity_id):
        entity = entity_id.split('.')
        for activity in self.activities:
            if activity['entity_id'] == entity[1]:
                return activity
        return False
        
    def turn_off(self, service):
        
        entity_id = service.data['entity_id']
        if type(entity_id) == list:
            entity_id = entity_id[0]

        activity = self.get_activity_from_service(service)
        self.client.start_activity(self.poweroff_id)
        self.hass.states.set(entity_id, STATE_OFF)

    def turn_on(self, service):

        activity = self.get_activity_from_service(service)
        self.client.start_activity(activity['harmony_id'])
        
        self.hass.states.set(activity['entity_id'], STATE_ON)

    def send_device_command(self, service):
        if service.data is not None and 'entity_id' in service.data and 'command' in service.data:
            LOGGER.info("sending '%s' command to device '%s' " % (service.data['command'], service.data['entity_id']))
            self.client.send_command(service.data['entity_id'], service.data['command'])
        else:
            LOGGER.warn("Incorrect send_device_command service '%s'" % service)

    def change_device_state(self, device_id, device_state):
        # TODO : handle PowerToggle
        if device_state:
            LOGGER.info("sending 'PowerOn' command to device '%s' " % device_id)
            self.client.send_command(device_id, 'PowerOn')
        else:
            LOGGER.info("sending 'PowerOff' command to device '%s' " % device_id)
            self.client.send_command(device_id, 'PowerOff')

    def get_activity_from_service(self, service):
        entity_id = service.data['entity_id']
        if type(entity_id) == list:
            entity_id = entity_id[0]

        return self.get_activity_by_entity(entity_id)


class RokuRequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        current_date = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
        self.send_response(200)
        self.send_header('Date', current_date)
        self.send_header('Server', 'Roku UPnP/1.0 MiniUPnPd/1.4')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write(bytes("<html><body><h1>hi!</h1></body></html>", "utf-8"))

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        self._set_headers()
        print ("Receive '%s' request" % self.path)
        # Extract key
        path_parts = self.path.split('/')
        if len(path_parts) == 3:
            self.server.hass().bus.fire('harmony.%s' % path_parts[1], { 'key': path_parts[2] })


class RokuEmulatedServer(HTTPServer):

    ROKU_PORT = 8060

    def __init__(self, hass, port = ROKU_PORT):
        _server_address = ('', port)
        self._hass = hass
        super().__init__(_server_address, RokuRequestHandler)

    def hass(self):
        return self._hass

    def serveInAnotherThread(self):
        thread = threading.Thread(target = self.serve_forever)
        thread.daemon = True

        try:
            thread.start()
        except KeyboardInterrupt:
            self.shutdown()
