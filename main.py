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
from game import Game
import buttons
import icons
import messages
import person
from person import Person
import utility
import jsonUtil
import utility
import parameters
import render_results

########################
WORK_IN_PROGRESS = False
########################

STATES = {
    1:   'Start State',
    20:  'Game Lobby',
    30:  'Game Room: choose own card',
    31:  'Game Room: critics guess a card',
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

def broadcast(sender, msg, restart_user=False, curs=None, enabledCount = 0):
    #return

    BROADCAST_COUNT_REPORT = utility.unindent(
        """
        Mesage sent to {} people
        Enabled: {}
        Disabled: {}
        """
    )

    users, next_curs, more = Person.query().fetch_page(50, start_cursor=curs)
    try:
        for p in users:
            if p.enabled:
                enabledCount += 1
                if restart_user:
                    restart(p)
                tell(p.chat_id, msg, sleepDelay=True)
    except datastore_errors.Timeout:
        sleep(1)
        deferredSafeHandleException(broadcast, sender, msg, restart_user, curs, enabledCount)
        return
    if more:
        deferredSafeHandleException(broadcast, sender, msg, restart_user, next_curs, enabledCount)
    else:
        total = Person.query().count()
        disabled = total - enabledCount
        msg_debug = BROADCAST_COUNT_REPORT.format(total, enabledCount, disabled)
        tell(sender.chat_id, msg_debug)

def tellMaster(msg, markdown=False, one_time_keyboard=False):
    for id in key.MASTER_CHAT_ID:
        tell(id, msg, markdown=markdown, one_time_keyboard = one_time_keyboard, sleepDelay=True)

def tell(chat_id, msg, kb=None, markdown=True, inline_keyboard=False, one_time_keyboard=False,
         sleepDelay=False, remove_keyboard=False, force_reply=False):

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
    elif remove_keyboard:
        replyMarkup = { #ReplyKeyboardHide
            'remove_keyboard': remove_keyboard
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

def sendPhoto(chat_id, file_id_or_url):
    try:
        data = {
            'chat_id': chat_id,
            'photo': file_id_or_url,
        }
        resp = requests.post(key.BASE_URL + 'sendPhoto', data)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()

def sendPhotoData(chat_id, file_data, filename):
    try:
        files = [('photo', (filename, file_data, 'image/png'))]
        data = {
            'chat_id': chat_id,
        }
        resp = requests.post(key.BASE_URL + 'sendPhoto', data=data, files=files)
        logging.info('Response: {}'.format(resp.text))
    except urllib2.HTTPError, err:
        report_exception()


def sendScoreTest(chat_id):
    result_table = [
        ['', '👺🃏(x3)', '🕵🔭(x2)', '🕵🃏(x2)', 'TOTAL'],
        ['👺 player1_xx', '4+1', '1', '2', '21'],
        ['🕵 player2_xx', '2', '5+0', '3+1', '24'],
        ['🕵 player3_xx', '1', '4+1', '3+0', '19']
    ]
    imgData = render_results.getResultImage(result_table)
    sendPhotoData(chat_id, imgData, 'results.png')


def sendTextImage(chat_id, text):
    text = text.replace('+', '%2b')
    text = text.replace(' ', '+')
    text = text.replace('\n','%0B')
    # see http://img4me.com/
    # see https://developers.google.com/chart/image/docs/gallery/dynamic_icons
    # see https://dummyimage.com/
    # see https://placehold.it/
    #img_url = "http://chart.apis.google.com/chart?chst=d_text_outline&chld=000000|20|l|FFFFFF|_|" + text
    img_url = "https://placeholdit.imgix.net/~text?bg=ffffff&txtcolor=000000&txtsize=15&txt={}&w=400&h=200".format(text)
    logging.debug("img_url: {}".format(img_url))
    #img_url = "http://chart.apis.google.com/chart?chst=d_fnote&chld=sticky_y|2|0088FF|h|" + text
    sendPhoto(chat_id, img_url)

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
# GAME FUNCTIONS
# ================================

def terminateGame(g, msg=''):
    winners = g.getWinnerNames()
    msg += '\n\n'
    if winners:
        winners_str = ', '.join(winners)
        if len(winners) > 1:
            msg += '{} The winners of the game are: {}'.format(icons.TROPHY, winners_str)
        else:
            msg += '{} The winner of the game is {}'.format(icons.TROPHY, winners_str)
    for id in g.getPlayerIds():
        p = person.getPersonById(id)
        p.setGameRoom(None)
        tell(p.chat_id, msg, remove_keyboard=True, sleepDelay=True)
        restart(p)
    if g.isPublic():
        g.resetGame()
    else:
        game.deleteGame(g)

def broadcastMsgToPlayers(g, msg):
    for id in g.getPlayerIds():
        tell(id, msg, sleepDelay=True)

def broadcastResultImageToPlayers(g, file_data):
    for id in g.getPlayerIds():
        sendPhotoData(id, file_data, 'results.png')
        sleep(0.1)

def redirectPlayersToState(g, new_state):
    for id in g.getPlayerIds():
        p = person.getPersonById(id)
        redirectToState(p, new_state)

def sendPlayersWaitingAction(g, sleep_time=None):
    for chat_id in g.getCriticsId():
        sendWaitingAction(chat_id, sleep_time = sleep_time)

def tellPlayers(g, msg):
    for chat_id in g.getCriticsId():
        tell(chat_id, msg, sleepDelay=True)

def tellCritics(g, msg):
    for chat_id in g.getPlayersId():
        tell(chat_id, msg, sleepDelay=True)

def tellBadPressOfficer(g, msg):
    tell(g.getBadPressOfficerId(), msg, sleepDelay=True)

def updateAndSendScoresToPlayers(g):
    handScores = g.computeHandScores()
    bpo_id = g.getBadPressOfficerId()
    for p_id, scores in handScores.iteritems():
        bpo_disguiser_reward, detective_reward, critic_disguiser_reward = handScores[p_id]
        if p_id == bpo_id:
            if bpo_disguiser_reward>0:
                msg_bpo = '😀 You got {0} {1} (bad press officer disguiser rewards): ' \
                      '{0} critics did not discover that your card was fake!'.format(
                    bpo_disguiser_reward, icons.BPO_DISGUISER_REWARD)
            else:
                msg_bpo = '😕 You got 0 {} (bad press officer disguiser rewards): ' \
                      'all critics discovered that your card was fake.'.format(icons.BPO_DISGUISER_REWARD)
            tell(bpo_id, msg_bpo, sleepDelay=True, remove_keyboard=True)
        else:
            if detective_reward>0:
                msg = '😀 You got the {} (detective reward): ' \
                      "you were able to recognize the bad press officer's fake card".format(icons.DETECTIVE_REWARD)
            else:
                msg = '😕 You did not get the {} (detective reward): ' \
                      "you were not able to recognize the bad press officer's fake card".format(icons.DETECTIVE_REWARD)
            msg += '\n'
            if critic_disguiser_reward>0:
                msg += '😀 You got {0} {1} (critic disguiser rewards): ' \
                      '{0} critic(s) thought that your card was fake.'.format(
                    critic_disguiser_reward, icons.CRITIC_DISGUISER_REWARD)
            else:
                msg += '😕 You got 0 {} (critic disguiser rewards): ' \
                      'no critic thought that your card was fake.'.format(icons.CRITIC_DISGUISER_REWARD)
            tell(p_id, msg, sleepDelay=True, remove_keyboard=True)


    score_table = g.updateGameScores()
    imgData = render_results.getResultImage(score_table)
    broadcastResultImageToPlayers(g, imgData)

# ================================
# GO TO STATE 1: Initial Screen
# ================================
def goToState1(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    kb = [[buttons.ENTER_GAME], [buttons.HELP]]
    if giveInstruction:
        msg = 'Press {} if you want to enter a game'.format(buttons.ENTER_GAME)
        tell(p.chat_id, msg, kb)
    else:
        if input in ['/help', buttons.HELP]:
            tell(p.chat_id, messages.INSTRUCTIONS)
        elif input == buttons.ENTER_GAME:
            redirectToState(p, 20)
        elif p.chat_id in key.MASTER_CHAT_ID:
            if input.startswith('/sendText'):
                sendText(p, input, markdown=True)
            elif input == '/testScore':
                sendScoreTest(p.chat_id)
            else:
                tell(p.chat_id, messages.NOT_VALID_INPUT, kb=kb)
        else: # including input == ''
            tell(p.chat_id, messages.NOT_VALID_INPUT, kb=kb)

# ================================
# GO TO STATE 20: Game Lobby
# ================================
def goToState20(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    public_games = [game.getGame(x) for x in parameters.PUBLIC_GAME_ROOM_NAMES]
    public_game_room_names_or_refresh = [
        x.getGameRoomName() if x.areMorePlayersAccepted() else buttons.REFRESH for x in public_games
    ]
    kb = [public_game_room_names_or_refresh,[buttons.NEW_GAME_ROOM],[buttons.BACK]]
    if giveInstruction:
        msg = "YOU ARE IN THE *LOBBY*\n" \
              "Please select one of the public rooms below, " \
              "enter the name of a private room, " \
              "or create a new one."
        tell(p.chat_id, msg, kb)
    else:
        if input == buttons.REFRESH:
            repeatState(p)
        elif input == buttons.BACK:
            restart(p)
        elif input == buttons.NEW_GAME_ROOM:
            p.setTmpVariable(person.VAR_CREATE_GAME, {'stage': 0})
            redirectToState(p, 21)
        elif input != '':
            public = input in parameters.PUBLIC_GAME_ROOM_NAMES
            if not public:
                input = input.upper()
            g = game.getGame(input)
            if g:
                if g.addPlayer(p):
                    redirectToState(p, 22)
                else:
                    msg = "Sorry, there are no more places available in this game room, choose another room or try later."
                    tell(p.chat_id, msg)
                    sendWaitingAction(p.chat_id, sleep_time=1)
                    repeatState(p)
            else:
                msg = "{} You didn't enter a valid game room name, " \
                      "if you want to create a new one press {}.".format(icons.EXCLAMATION_ICON, buttons.NEW_GAME_ROOM)
                tell(p.chat_id, msg)
        else:  # input == ''
            tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# GO TO STATE 21: Create new game
# ================================
def goToState21(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    if input == '':
        tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())
        return
    if input == buttons.BACK:
        redirectToState(p, 20)  # lobby
        return
    giveInstructions = input is None
    game_parameters = p.getTmpVariable(person.VAR_CREATE_GAME)
    stage = game_parameters['stage']
    if stage == 0: # game name
        if giveInstructions:
            kb = [[buttons.BACK]]
            p.setLastKeyboard(kb)
            msg = "Please enter the name of a new game."
            tell(p.chat_id, msg, kb)
        else:
            input = input.upper()
            if game.gameExists(input):
                msg = "{} A game with this name already exists. Please try again.".format(icons.EXCLAMATION_ICON)
                tell(p.chat_id, msg)
            else:
                game_parameters['stage'] = 1
                game_parameters['game_name'] = input
                repeatState(p, put=True)
    elif stage == 1: # number of players
        if giveInstructions:
            kb = [['3','4','5','6'],[buttons.BACK]]
            p.setLastKeyboard(kb)
            msg = "Please enter the number of people."
            tell(p.chat_id, msg, kb)
        else:
            if utility.representsIntBetween(input, 2, 30):
                sendWaitingAction(p.chat_id)
                number_players = int(input)
                game_name = game_parameters['game_name']
                g = game.createGame(game_name, number_players)
                g.addPlayer(p)
                redirectToState(p, 22)
            else:
                msg = "{} Please enter a number between 3 and 30.".format(icons.EXCLAMATION_ICON)
                tell(p.chat_id, msg)

# ================================
# GO TO STATE 22: Game: Waiting for start
# ================================
def goToState22(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    g = p.getGame()
    if giveInstruction:
        msg = "Entering the game *{}*".format(g.getGameRoomName())
        tell(p.chat_id, msg, remove_keyboard=True)
        broadcastMsgToPlayers(g, "Player {} joined the game!".format(p.getFirstName()))
        if g.readyToStart():
            msg = "Starting the game..."
            broadcastMsgToPlayers(g, msg)
            g.startGame()
            redirectPlayersToState(g, 30)
        else:
            msg = "Waiting for {} other players...".format(g.remainingSeats())
            broadcastMsgToPlayers(g, msg)
    else:
        msg = "{} Please wait for the other players to join the game.".format(icons.EXCLAMATION_ICON)
        tell(p.chat_id, msg)


# ================================
# GO TO STATE 30: Game: Choose Own Card
# ================================
def goToState30(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    g = p.getGame()
    if g == None:
        return # game deleted because no more cards
    giveInstruction = input is None
    isBadPressOfficer = p.chat_id == g.getBadPressOfficerId()
    kb = utility.distributeElementMaxSize([str(r) for r in range(1, parameters.CARDS_PER_PLAYER + 1)])
    if giveInstruction:
        cards = g.givePlayersCards(p.chat_id)
        if cards:
            msg = "✋ HAND {}\n".format(g.getHandNumber())
            if isBadPressOfficer:
                msg += "YOU ARE THE {} *BAD PRESS OFFICER*!!\n" \
                       "These are your *FAKE NEWS*, " \
                       "please choose the one that looks *MOST REALISTIC* to you:\n".format(icons.BAD_PRESS_OFFICER)
            else:
                msg += "YOU ARE A {} *CRITIC*!\n" \
                       "The *bad press officer* is {}\n" \
                       "These are your *RELIABLE NEWS*, " \
                       "please choose the one it looks *MOST FAKE* to you:\n".format(icons.CRITIC, g.getBadPressOfficerName())
            tell(p.chat_id, msg)
            msg = "\n".join(['/{} {}'.format(n, utility.escapeMarkdown(c)) for n, c in enumerate(cards, 1)])
            tell(p.chat_id, msg, kb)
        else:
            #g.sendFinalScores()
            msg = "The game is terminated because there are no more cards to play."
            terminateGame(g, msg)
    else:
        if input.startswith('/'):
            numberStr = input[1:]
        else:
            numberStr = input
        if utility.representsIntBetween(numberStr, 1, parameters.CARDS_PER_PLAYER):
            index = int(numberStr) - 1
            g.storePlayerChosenCard(p.chat_id, index)
            if g.haveAllPlayersChosenACard():
                g.computePlayersCardsShuffle()
                redirectPlayersToState(g, 31)
            else:
                msg = "👍 Thanks for your selection!\n" \
                      "Let's wait for all players to choose a card."
                tell(p.chat_id, msg, remove_keyboard=True)
        else: #including input == ''
            tell(p.chat_id, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# GO TO STATE 31: Game: Critics Guess Card
# ================================
def goToState31(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    g = p.getGame()
    if g == None:
        return # game deleted because no more cards
    giveInstruction = input is None
    isBadPressOfficer = p.chat_id == g.getBadPressOfficerId()
    if giveInstruction:
        msg = "👍 Great, all players have chosen a card!\n" \
              "Now the critics should guess a card.\n"
        if isBadPressOfficer:
            msg += "⌛ Please wait..."
        else:
            msg = "Try to detect the *FAKE NEWS* from the followings:"
        tell(p.chat_id, msg, remove_keyboard=True)
        if not isBadPressOfficer:
            cards_shuffle = g.getCriticCardsShuffle(p.chat_id)
            kb = utility.distributeElementMaxSize([str(r) for r in range(1, len(cards_shuffle) + 1)])
            msg = "\n".join(['/{} {}'.format(n, utility.escapeMarkdown(c)) for n, c in enumerate(cards_shuffle, 1)])
            tell(p.chat_id, msg, kb)
            p.setLastKeyboard(kb)
    else:
        if isBadPressOfficer:
            msg = "{} Please wait for the critics to guess a card.".format(icons.EXCLAMATION_ICON)
            tell(p.chat_id, msg)
            return
        if input.startswith('/'):
            numberStr = input[1:]
        else:
            numberStr = input
        if utility.representsIntBetween(numberStr, 1, parameters.CARDS_PER_PLAYER):
            cardsShufflePlayer = g.getCriticCardsShuffle(p.chat_id)
            card = cardsShufflePlayer[int(numberStr) - 1]
            if g.storeCriticGuessedCard(p.chat_id, card):
                if g.haveAllCriticsGuessedACard():
                    msg = "👍 Great, all critics have guessed a card!"
                    tellPlayers(g, msg)
                    sendPlayersWaitingAction(g)
                    updateAndSendScoresToPlayers(g)
                    if g.isThereASingleWinner():
                        terminateGame(g, "The game has terminated because there is a winner!")
                    else:
                        g.nextHand()
                        sendPlayersWaitingAction(g, sleep_time=2)
                        redirectPlayersToState(g, 30)
                else:
                    msg = "⌛ Waiting for the other critics to guess a card."
                    tell(p.chat_id, msg, remove_keyboard=True)
            else:
                msg = "{} You cannot choose your own card, please try again.".format(icons.EXCLAMATION_ICON)
                tell(p.chat_id, msg, kb=p.getLastKeyboard())
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

class CheckExpiredGames(SafeRequestHandler):
    def get(self):
        for g in Game.query():
            if g.isGameExpired():
                msg = "{} The game has terminated because it has been idle for too long".format(icons.TIME_ICON)
                terminateGame(g, msg)


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
            elif text.startswith("/start"):
                if p.getGame()!=None:
                    msg = "{} You are still in a game!".format(icons.EXCLAMATION_ICON)
                    tell(p.chat_id, msg)
                else:
                    msg = "Hi {}, welcome back to KriticosBot!\n\n".format(p.getFirstName())
                    tell(p.chat_id, msg)
                    p.setEnabled(True, put=False)
                    restart(p)
            elif text.startswith("/exit"):
                g = p.getGame()
                if g==None:
                    msg = "{} You are not in a game!".format(icons.EXCLAMATION_ICON)
                    tell(p.chat_id, msg)
                else:
                    terminateGame(g, "The game has terminated because {} exited.".format(p.getFirstName()))
            elif WORK_IN_PROGRESS and p.chat_id not in key.TEST_PLAYERS:
                logging.debug('person {} not in {}'.format(p.chat_id, key.TEST_PLAYERS))
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
    ('/delete_webhook', DeleteWebhook),
    ('/get_webhook_info', GetWebhookInfo),
    (key.WEBHOOK_PATH, WebhookHandler),
    ('/checkExpiredGames', CheckExpiredGames),
    ('/gamestatus', game.getGameStatus),
    ('/gamestatusjson', game.getGameStatusJson),
], debug=True)

possibles = globals().copy()
possibles.update(locals())
