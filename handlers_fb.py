# -*- coding: utf-8 -*-

import logging
import requests
from google.appengine.api import urlfetch

import webapp2
import jsonUtil
import key

requests.packages.urllib3.disable_warnings()

def setMenu(menu_items):
    response_data = {
        #"recipient": {"id": sender_id},
        "setting_type": "call_to_actions",
        "thread_state": "existing_thread",
        "call_to_actions": [
            {
                "type": "postback",
                "title": i,
                "payload": i
            }
            for i in menu_items
        ]
    }

    logging.info('sending menu with json: {}'.format(response_data))
    resp = requests.post(key.FACEBOOK_TRD_API_URL, json=response_data)
    logging.info('responding to request: {}'.format(resp.text))

def sendMessage(sender_id, msg):
    response_data = {
        "recipient": {"id": sender_id},
        "message": {
            "text": msg,
        }
    }
    logging.info('responding to request with message: {}'.format(response_data))
    resp = requests.post(key.FACEBOOK_MSG_API_URL, json=response_data)
    logging.info('responding to request: {}'.format(resp.text))

def sendMessageWithQuickReplies(sender_id, msg, reply_items):
    response_data = {
        "recipient": {"id": sender_id},
        "message": {
            "text": msg,
            "quick_replies": [
                {
                    "content_type": "text",
                    "title": i,
                    "payload": i
                }
                for i in reply_items
            ]
        }
    }
    logging.info('responding to request with message with quick replies: {}'.format(response_data))
    resp = requests.post(key.FACEBOOK_MSG_API_URL, json=response_data)
    logging.info('responding to request: {}'.format(resp.text))

def sendMessageWithButtons(sender_id, msg, button_items):
    response_data = {
        "recipient": {"id": sender_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": msg,
                    "buttons": [
                        {
                            "type": "postback",
                            "title": i,
                            "payload": i
                        }
                        for i in button_items
                    ]
                }
            }
        }
    }
    logging.info('responding to request with message with buttons: {}'.format(response_data))
    resp = requests.post(key.FACEBOOK_MSG_API_URL, json=response_data)
    logging.info('responding to request: {}'.format(resp.text))

def sendPhotoData(sender_id, file_data, filename):
    import json

    response_data = {
        "recipient": json.dumps(
            {"id": sender_id}
        ),
        "message": json.dumps(
            {
                "attachment": {
                    "type": "image",
                    "payload": {}
                }
            }
        ),
    }

    files = {
        "filedata": (filename, file_data, 'image/png')
    }

    logging.info('sending photo data: {}'.format(response_data))
    resp = requests.post(key.FACEBOOK_MSG_API_URL, data=response_data, files=files)

    logging.info('responding to photo request: {}'.format(resp.text))


def getUserInfo(user_id):
    url = 'https://graph.facebook.com/v2.6/{}?fields=first_name,last_name,profile_pic,locale,timezone,gender&access_token={}'.format(user_id, key.FACEBOOK_PAGE_ACCESS_TOKEN)
    logging.debug('Sending user info request: {}'.format(url))
    r = requests.get(url)
    json = r.json()
    first_name = json.get('first_name', None)
    last_name = json.get('last_name', None)
    logging.debug('Getting first name = {} and last name = {}'.format(first_name, last_name))
    return first_name, last_name

class WebhookHandler(webapp2.RequestHandler):

    # to confirm the webhook url
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        challange = self.request.get('hub.challenge')
        self.response.write(challange)

    # to handle user interaction
    def post(self):
        from main import dealWithUserInteraction
        # urlfetch.set_default_fetch_deadline(60)
        body = jsonUtil.json_loads_byteified(self.request.body)
        logging.info('request body: {}'.format(body))
        data = body['entry'][0]['messaging'][0]
        chat_id = data['sender']['id']
        if 'message' in data:
            message = data['message']['text']
        elif 'postback' in data:
            message = data['postback']['payload']
        else:
            return


        logging.info('got message ({}) from {}'.format(message, chat_id))

        dealWithUserInteraction(chat_id, first_name=None, last_name=None, username=None, facebook=True, user_input=message)

