# -*- coding: utf-8 -*-

# import json
import json
import logging
import urllib
import urllib2
import datetime
from datetime import datetime
from time import sleep
import re

# standard app engine imports
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext import deferred
from google.appengine.ext.db import datastore_errors
import requests
import webapp2

import key
import game
import buttons
import icons
import messages
import person
from person import Person
import utility
import jsonUtil
import utility
import parameters

########################
WORK_IN_PROGRESS = False
########################

STATES = {
    1:   'Start State',
    2:   'Game: choose own card',
    3:   'Game: guess a card',
}


# ================================
# Telegram Send Request
# ================================
def sendRequest(url, data, recipient_chat_id, debugInfo):
    try:
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
            p = person.getPersonById(recipient_chat_id)
            if error_code == 403:
                # Disabled user
                logging.info('Disabled user: ' + p.getUserInfoString())
            elif error_code == 400 and description == "INPUT_USER_DEACTIVATED":
                p = person.getPersonById(recipient_chat_id)
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
    except:
        report_exception()

# ================================
# TELL FUNCTIONS
# ================================


def tellMaster(msg, markdown=False, one_time_keyboard=False):
    for id in key.MASTER_CHAT_ID:
        tell(id, msg, markdown=markdown, one_time_keyboard = one_time_keyboard, sleepDelay=True)

def tell(chat_id, msg, kb=None, markdown=False, inline_keyboard=False, one_time_keyboard=False,
         sleepDelay=False, hide_keyboard=False, force_reply=False):

    # reply_markup: InlineKeyboardMarkup or ReplyKeyboardMarkup or ReplyKeyboardHide or ForceReply
    if inline_keyboard:
        replyMarkup = { #InlineKeyboardMarkup
            'inline_keyboard': kb
        }
    elif kb:
        replyMarkup = { #ReplyKeyboardMarkup
            'keyboard': kb,
            'resize_keyboard': True,
            'one_time_keyboard': one_time_keyboard,
        }
    elif hide_keyboard:
        replyMarkup = { #ReplyKeyboardHide
            'hide_keyboard': hide_keyboard
        }
    elif force_reply:
        replyMarkup = { #ForceReply
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

def tell_person(chat_id, msg, markdown=False):
    tell(chat_id, msg, markdown=markdown)
    p = person.getPersonById(chat_id)
    if p and p.enabled:
        return True
    return False

def sendText(p, text, markdown=False, restartUser=False):
    split = text.split()
    if len(split) < 3:
        tell(p.chat_id, 'Commands should have at least 2 spaces')
        return
    if not split[1].isdigit():
        tell(p.chat_id, 'Second argumnet should be a valid chat_id')
        return
    id = int(split[1])
    text = ' '.join(split[2:])
    if tell_person(id, text, markdown=markdown):
        user = person.getPersonById(id)
        if restartUser:
            restart(user)
        tell(p.chat_id, 'Successfully sent text to ' + user.getFirstName())
    else:
        tell(p.chat_id, 'Problems in sending text')


# ================================
# SEND LOCATION
# ================================

def sendLocation(chat_id, latitude, longitude, kb=None):
    try:
        resp = urllib2.urlopen(key.BASE_URL + 'sendLocation', urllib.urlencode({
            'chat_id': chat_id,
            'latitude': latitude,
            'longitude': longitude,
        })).read()
        logging.info('send location: {}'.format(resp))
    except urllib2.HTTPError, err:
        if err.code == 403:
            p = Person.query(Person.chat_id == chat_id).get()
            p.enabled = False
            p.put()
            logging.info('Disabled user: ' + p.getUserInfoString())
        else:
            logging.info('Unknown exception: ' + str(err))

# ================================
# SEND VOICE
# ================================

def sendVoice(chat_id, file_id):
    try:
        data = {
            'chat_id': chat_id,
            'voice': file_id,
        }
        resp = requests.post(key.BASE_URL + 'sendVoice', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()

# ================================
# SEND PHOTO
# ================================

def sendPhoto(chat_id, file_id):
    try:
        data = {
            'chat_id': chat_id,
            'photo': file_id,
        }
        resp = requests.post(key.BASE_URL + 'sendPhoto', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()

# ================================
# SEND DOCUMENT
# ================================

def sendDocument(chat_id, file_id):
    try:
        data = {
            'chat_id': chat_id,
            'document': file_id,
        }
        resp = requests.post(key.BASE_URL + 'sendDocument', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()

def sendExcelDocument(chat_id, sheet_tables, filename='file'):
    try:
        xlsData = utility.convert_data_to_spreadsheet(sheet_tables)
        files = [('document', ('{}.xls'.format(filename), xlsData, 'application/vnd.ms-excel'))]
        data = {
            'chat_id': chat_id,
        }
        resp = requests.post(key.BASE_URL + 'sendDocument', data=data, files=files)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()


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
# RESTART
# ================================
def restart(p, msg=None):
    if msg:
        tell(p.chat_id, msg)
    redirectToState(p, 1)


# ================================
# SWITCH TO STATE
# ================================
def redirectToState(p, new_state, **kwargs):
    if p.state != new_state:
        logging.debug("In redirectToState. current_state:{0}, new_state: {1}".format(str(p.state),str(new_state)))
        p.setState(new_state)
    repeatState(p, **kwargs)

# ================================
# REPEAT STATE
# ================================
def repeatState(p, put=False, **kwargs):
    methodName = "goToState" + str(p.state)
    method = possibles.get(methodName)
    if not method:
        tell(p.chat_id, "A problem has been detected (" + methodName +
              "). Write to @kercos." + '\n' +
              "You will be now redirected to the initial screen.")
        restart(p)
    else:
        if put:
            p.put()
        method(p, **kwargs)

# ================================
# PLAYERS FUNCTIONS
# ================================

def broadcastPlayers(msg):
    for id in game.getPlayersId():
        tell(id, msg, sleepDelay=True)

def redirectPlayersToState(new_state):
    for id in game.getPlayersId():
        p = person.getPersonById(id)
        if p==None:
            logging.debug("p is none: {}".format(id))
        redirectToState(p, new_state)

def tellCheckers(msg):
    for chat_id in game.getCheckersId():
        tell(chat_id, msg, sleepDelay=True)

def tellDealer(msg):
    tell(game.getDealerId(), msg, sleepDelay=True)


# ================================
# GO TO STATE 1: Initial Screen
# ================================
def goToState1(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    if giveInstruction:
        if game.areMorePlayersAccepted():
            msg = 'Game instructions...'.format(p.getFirstName())
            kb = [[buttons.ENTER_GAME],[buttons.HELP]]
        else:
            msg = 'Game instructions...'.format(p.getFirstName())
            kb = [[buttons.REFRESH],[buttons.HELP]]
        p.setLastKeyboard(kb)
        tell(p.chat_id, msg, kb)
    else:
        if input in ['/help', buttons.HELP]:
            tell(p.chat_id, messages.INSTRUCTIONS)
        elif input == buttons.ENTER_GAME:
            if game.addPlayer(p):
                broadcastPlayers("Player {} joined the game!".format(p.getFirstName()))
                if game.readyToStart():
                    msg = "Starting the game..."
                    broadcastPlayers(msg)
                    redirectPlayersToState(2)
                else:
                    msg = "Waiting for {} other players...".format(game.remainingSeats())
                    broadcastPlayers(msg)
            else:
                msg = "Sorry, there are no more place available, try later."
                tell(p.chat_id, msg)
                sendWaitingAction(p.chat_id, sleep_time=1)
                repeatState(p)
        elif input == buttons.REFRESH:
            repeatState(p)
        elif p.chat_id in key.MASTER_CHAT_ID:
            if input.startswith('/sendText'):
                sendText(p, input, markdown=True)
            elif input == '/resetGame':
                game.resetGame()
                tell(p.chat_id, "Game resetted")
            else:
                tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())
        else: # including input == ''
            tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# GO TO STATE 2: Game: Choose Own Card
# ================================
def goToState2(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    isDealer = p.chat_id == game.getDealerId()
    kb = utility.distributeElementMaxSize([str(r) for r in range(1, parameters.CARDS_PER_PLAYER + 1)])
    if giveInstruction:
        cards = game.givePlayersCards(isDealer)
        p.setCards(cards, put=True)
        #true_false_dealer_str = "✅ TRUE" if game.getDealerHandTrueFalse() else "❌ FALSE"
        #true_false_checker_str = "✅ FALSE" if game.getDealerHandTrueFalse() else "❌ TRUE"
        msg = "✋ HAND {}\n" \
              "The bad press officer is {}\n" \
              "These are your cards, please choose one:\n".format(game.getHandNumber(), game.getDealerName())
        tell(p.chat_id, msg)
        msg = "\n".join(['/{} {}'.format(n, c) for n, c in enumerate(cards, 1)])
        tell(p.chat_id, msg, kb)
    else:
        if input.startswith('/'):
            numberStr = input[1:]
        else:
            numberStr = input
        if utility.representsIntBetween(numberStr, 1, parameters.CARDS_PER_PLAYER):
            card = p.getCard(int(numberStr) - 1)
            game.storePlayerChosenCard(p.chat_id, card)
            if game.haveAllPlayersPlayedTheirCards():
                game.computePlayersCardsShuffle()
                redirectPlayersToState(3)
            else:
                msg = "Waiting for all players to choose a card."
                tell(p.chat_id, msg)
        else: #including input == ''
            tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# GO TO STATE 3: Game: Guess Card
# ================================
def goToState3(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    isDealer = p.chat_id == game.getDealerId()
    if giveInstruction:
        msg = "Great, all players have chosen a card!" \
              "Now the critics should guess a card."
        tell(p.chat_id, msg)
        if not isDealer:
            cards_shuffle = game.getPlayersCardsShuffle()
            kb = utility.distributeElementMaxSize([str(r) for r in range(1, len(cards_shuffle) + 1)])
            msg = "\n".join(['/{} {}'.format(n, c) for n, c in enumerate(cards_shuffle, 1)])
            tell(p.chat_id, msg, kb)
    else:
        if isDealer:
            tell(p.chat_id, "Not supposed to tell me anything here, please wait")
            return
        if input.startswith('/'):
            numberStr = input[1:]
        else:
            numberStr = input
        if utility.representsIntBetween(numberStr, 1, parameters.CARDS_PER_PLAYER):
            card = p.getCard(int(numberStr) - 1)
            game.storeCheckerGuessedCard(p.chat_id, card)
            if game.haveAllCheckersGuessedTheirCards():
                msg = "Great, all checkers have guessed a card!"
                tell(p.chat_id, msg)
                score = game.howManyPeopleChoseMyCard(p.chat_id)
                msg = "Your card has been chosen by {} people.".format(score)
                tell(p.chat_id, msg)
                if isDealer:
                    game.nextHand()
                    redirectPlayersToState(1)
            else:
                msg = "Waiting for other critics to guess a card."
                tell(p.chat_id, msg)
        else: #including input == ''
            tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())


# ================================
# HANDLERS
# ================================

class SafeRequestHandler(webapp2.RequestHandler):
    def handle_exception(self, exception, debug_mode):
        report_exception()

class MeHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.write(json.dumps(json.load(urllib2.urlopen(key.BASE_URL + 'getMe'))))

class SetWebhookHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        url = self.request.get('url')
        if url:
            self.response.write(
                json.dumps(json.load(urllib2.urlopen(key.BASE_URL + 'setWebhook', urllib.urlencode({'url': url})))))

# ================================
# ================================
# ================================

class WebhookHandler(SafeRequestHandler):
    def post(self):
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
        contact = message['contact'] if 'contact' in message else None
        photo = message.get('photo') if 'photo' in message else None
        document = message.get('document') if 'document' in message else None
        voice = message.get('voice') if 'voice' in message else None

        p = person.getPersonById(chat_id)

        if p is None:
            # new user
            logging.info("Text: " + text)
            if text == '/help':
                tell(chat_id, messages.INSTRUCTIONS)
            elif text.startswith("/start"):
                p = person.addPerson(chat_id, name, last_name, username)
                msg = "Hi {}, welcome to KriticosBot!\n".format(p.getFirstName()) # + START_MESSAGE
                tell(chat_id, msg)
                restart(p)
                tellMaster("New user: " + p.getFirstNameLastNameUserName())
            else:
                msg = "Press on /start if you want to enter. If you encounter any problem, please contact @kercos"
                tell(chat_id, msg)
        else:
            # known user
            p.updateInfo(name, last_name, username)
            if text == '/state':
                if p.state in STATES:
                    tell(p.chat_id, "You are in state " + str(p.state) + ": " + STATES[p.state])
                else:
                    tell(p.chat_id, "You are in state " + str(p.state))
            elif text.startswith('/getTmpVar '):
                varName = text[11:]
                result = p.tmp_variables[varName] if varName in p.tmp_variables else None
                tell(p.chat_id, '{}:{}'.format(varName, result), markdown=False)
            elif text.startswith("/start"):
                tell(p.chat_id, "Hi {}, welcomeback in KriticosBot!\n\n".format(p.getFirstName()))
                p.setEnabled(True, put=False)
                restart(p)
            elif WORK_IN_PROGRESS and p.chat_id != key.FEDE_CHAT_ID:
                tell(p.chat_id, icons.UNDER_CONSTRUCTION + " System under maintanence, try later.")
            else:
                logging.debug("Sending {} to state {} with input {}".format(p.getFirstName(), p.state, text))
                repeatState(p, input=text, contact=contact, photo=photo, document=document, voice=voice)

def deferredSafeHandleException(obj, *args, **kwargs):
    #return
    try:
        deferred.defer(obj, *args, **kwargs)
    except: # catch *all* exceptions
        report_exception()

def report_exception():
    import traceback
    msg = "❗ Detected Exception: " + traceback.format_exc()
    tell(key.FEDE_CHAT_ID, msg, markdown=False)
    logging.error(msg)

app = webapp2.WSGIApplication([
    ('/me', MeHandler),
    ('/set_webhook', SetWebhookHandler),
    ('/webhook', WebhookHandler),
    ('/gamestatus', game.getGameStatus),
    ('/gamestatusjson', game.getGameStatusJson),
], debug=True)

possibles = globals().copy()
possibles.update(locals())
