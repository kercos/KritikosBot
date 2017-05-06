# -*- coding: utf-8 -*-

# standard app engine imports
from google.appengine.api import urlfetch

import jsonUtil

import urllib
import urllib2
import webapp2
import requests
import logging
import json
from time import sleep

import key

import person
from person import Person


# ================================
# Telegram Send Request
# ================================
def sendRequest(url, data, recipient_chat_id, debugInfo):
    resp = requests.post(url, data)
    logging.info('Response: {}'.format(resp.text))
    respJson = json.loads(resp.text)
    success = respJson['ok']
    if success:
        return True
    else:
        status_code = resp.status_code
        error_code = respJson['error_code']
        description = respJson['description']
        p = Person.get_by_id(recipient_chat_id)
        if error_code == 403:
            # Disabled user
            logging.info('Disabled user: ' + p.getUserInfoString())
        elif error_code == 400 and description == "INPUT_USER_DEACTIVATED":
            p = Person.get_by_id(recipient_chat_id)
            p.setEnabled(False, put=True)
            debugMessage = '❗ Input user disactivated: ' + p.getUserInfoString()
            logging.debug(debugMessage)
            tell(key.FEDE_CHAT_ID, debugMessage, markdown=False)
        else:
            debugMessage = '❗ Raising unknown err ({}).' \
                      '\nStatus code: {}\nerror code: {}\ndescription: {}.'.format(
                debugInfo, status_code, error_code, description)
            logging.error(debugMessage)
            #logging.debug('recipeint_chat_id: {}'.format(recipient_chat_id))
            logging.debug('Telling to {} who is in state {}'.format(p.chat_id, p.state))
            tell(key.FEDE_CHAT_ID, debugMessage, markdown=False)

# ================================
# TELL FUNCTIONS
# ================================

def tell(chat_id, msg, kb=None, markdown=True, inline_keyboard=False, one_time_keyboard=False,
         sleepDelay=False, remove_keyboard=False, force_reply=False):

    # reply_markup: InlineKeyboardMarkup or ReplyKeyboardMarkup or ReplyKeyboardHide or ForceReply
    if inline_keyboard:
        replyMarkup = {  # InlineKeyboardMarkup
            'inline_keyboard': kb
        }
    elif kb:
        replyMarkup = {  # ReplyKeyboardMarkup
            'keyboard': kb,
            'resize_keyboard': True,
            'one_time_keyboard': one_time_keyboard,
        }
    elif remove_keyboard:
        replyMarkup = {  # ReplyKeyboardHide
            'remove_keyboard': remove_keyboard
        }
    elif force_reply:
        replyMarkup = {  # ForceReply
            'force_reply': force_reply
        }
    else:
        replyMarkup = {}

    data = {
        'chat_id': chat_id,
        'text': msg,
        'disable_web_page_preview': 'true',
        'parse_mode': 'Markdown' if markdown else '',
        'reply_markup': json.dumps(replyMarkup),
    }
    debugInfo = "tell function with msg={} and kb={}".format(msg, kb)
    success = sendRequest(key.BASE_URL + 'sendMessage', data, chat_id, debugInfo)
    if success:
        if sleepDelay:
            sleep(0.1)
        return True

# ================================
# SEND PHOTO
# ================================

def sendPhotoData(chat_id, file_data, filename):
    files = [('photo', (filename, file_data, 'image/png'))]
    data = {
        'chat_id': chat_id,
    }
    resp = requests.post(key.BASE_URL + 'sendPhoto', data=data, files=files)
    logging.info('Response: {}'.format(resp.text))


# ================================
# SEND WAITING ACTION
# ================================

def sendWaitingAction(chat_id, action_type='typing', sleep_time=None):
    try:
        resp = urllib2.urlopen(key.BASE_URL + 'sendChatAction', urllib.urlencode({
            'chat_id': chat_id,
            'action': action_type,
        })).read()
        logging.info('send venue: {}'.format(resp))
        if sleep_time:
            sleep(sleep_time)
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id == chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getUserInfoString())
        else:
            logging.info('Unknown exception: ' + str(err))

# ================================
# HANDLERS
# ================================

class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(key.BASE_URL + 'getMe'))))

class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        allowed_updates = ["message", "inline_query", "chosen_inline_result", "callback_query"]
        data = {
            'url': key.WEBHOOK_URL,
            'allowed_updates': json.dumps(allowed_updates),
        }
        resp = requests.post(key.BASE_URL + 'setWebhook', data)
        logging.info('SetWebhook Response: {}'.format(resp.text))
        self.response.write(resp.text)

class GetWebhookInfo(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        resp = requests.post(key.BASE_URL + 'getWebhookInfo')
        logging.info('GetWebhookInfo Response: {}'.format(resp.text))
        self.response.write(resp.text)

class DeleteWebhook(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        resp = requests.post(key.BASE_URL + 'deleteWebhook')
        logging.info('DeleteWebhook Response: {}'.format(resp.text))
        self.response.write(resp.text)


# ================================
# ================================
# ================================

class WebhookHandler(webapp2.RequestHandler):

    def post(self):
        from main import dealWithUserInteraction
        body = jsonUtil.json_loads_byteified(self.request.body)
        logging.info('request body: {}'.format(body))

        if 'message' not in body:
            return
        message = body['message']

        if 'chat' not in message:
            return

        chat = message['chat']
        chat_id = chat['id']
        if 'first_name' not in chat:
            return
        text = message.get('text') if 'text' in message else ''
        name = chat['first_name']
        last_name = chat['last_name'] if 'last_name' in chat else None
        username = chat['username'] if 'username' in chat else None
        #location = message['location'] if 'location' in message else None
        #contact = message['contact'] if 'contact' in message else None
        #photo = message.get('photo') if 'photo' in message else None
        #document = message.get('document') if 'document' in message else None
        #voice = message.get('voice') if 'voice' in message else None



        dealWithUserInteraction(chat_id, name, last_name, username, facebook=False, user_input=text)


