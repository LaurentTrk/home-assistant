"""
homeassistant.components.harmony
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a Logitech Harmony Hub.
Need pyharmony lib
"""

import logging
import json
import re
import time
import requests
import sleekxmpp
import pprint
from sleekxmpp.xmlstream import ET

from homeassistant.helpers import event

from pyharmony.client import HarmonyClient, create_and_connect_client
from pyharmony.auth import SwapAuthToken, swap_auth_token, login

LOGGER = logging.getLogger(__name__)

from homeassistant.const import (
    STATE_OFF, STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF)

DOMAIN = "harmony"
DEPENDENCIES = []

# pylint: disable=unused-argument
def setup(hass, config):
    LOGGER.info('Setup Harmony')
    ip = config['harmony']['ip']
    email = config['harmony']['email']
    password = config['harmony']['password']

    harmony = Harmony(email, password, ip, hass, event)
    harmony.initialize()
    
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
        
        self.hass.services.register(DOMAIN, SERVICE_TURN_ON, self.turn_on)
        self.hass.services.register(DOMAIN, SERVICE_TURN_OFF, self.turn_off)

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
        LOGGER.info('Receive message from Hub')
        if self.monitor_hub_events:
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
        self.monitor_hub_events = False
        LOGGER.info('Getting current activity')
        active_activity = str(self.client.get_current_activity())#[7:]
                
        # Get the configuration from the hub
        LOGGER.info('Getting configuration')
        data = self.client.get_config()
        
        self.activities = []
        for activity in data['activity']:
            if not activity['id'] == self.poweroff_id:
                self.add_activity_from_hub(activity, active_activity)
        self.monitor_hub_events=True        

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
        
        self.client.start_activity(self.poweroff_id)
        
        self.hass.states.set(activity['entity_id'], STATE_OFF)        

    def turn_on(self, service):
        
        activity = self.get_activity_from_service(service)
        self.client.start_activity(activity['harmony_id'])
        
        self.hass.states.set(activity['entity_id'], STATE_ON)

    def get_activity_from_service(self, service):
        entity_id = service.data['entity_id']
        if type(entity_id) == list:
            entity_id = entity_id[0]

        return self.get_activity_by_entity(entity_id)
    

