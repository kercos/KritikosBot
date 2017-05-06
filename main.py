# -*- coding: utf-8 -*-

from google.appengine.ext import deferred

import webapp2
import logging
from time import sleep

import key
import handlers_tg
import handlers_fb

import buttons, icons, messages
import person
import utility
import parameters
import render_results
import game
from game import Game
from person import Person



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
# TEMPLATE API CALLS
# ================================

def sendMessageTemplateChatId(chat_id, facebook, msg, kb=None, markdown=True,
                              inline_keyboard=False, one_time_keyboard=False,
                              sleepDelay=False, remove_keyboard=False, force_reply=False):
    try:
        if facebook:
            if kb:
                kb_flat = [b for line in kb for b in line]
                handlers_fb.sendMessageWithQuickReplies(chat_id, msg, kb_flat)
            else:
                handlers_fb.sendMessage(chat_id, msg)
        else:
            handlers_tg.tell(chat_id, msg, kb, markdown, inline_keyboard, one_time_keyboard,
                             sleepDelay, remove_keyboard, force_reply)
    except:
        report_exception()

def sendMessageTemplate(p, msg, kb=None, markdown=True, inline_keyboard=False, one_time_keyboard=False,
                        sleepDelay=False, remove_keyboard=False, force_reply=False):
    sendMessageTemplateChatId(p.chat_id, p.facebook, msg, kb, markdown, inline_keyboard, one_time_keyboard,
                              sleepDelay, remove_keyboard, force_reply)

def sendPhotoDataTemplate(p, file_data, filename):
    try:
        if p.facebook:
            handlers_fb.sendPhotoData(p.chat_id, file_data, filename)
        else:
            handlers_tg.sendPhotoData(p.chat_id, file_data, filename)
    except:
        report_exception()

def sendWaitingActionTemplate(p, action_type='typing', sleep_time=None):
    try:
        if p.facebook:
            pass
        else:
            handlers_tg.sendWaitingAction(p.chat_id, action_type, sleep_time)
    except:
        report_exception()

def tellMaster(msg, markdown=False, one_time_keyboard=False):
    try:
        for id in key.MASTER_CHAT_ID:
            handlers_tg.tell(id, msg, markdown=markdown, one_time_keyboard=one_time_keyboard, sleepDelay=True)
    except:
        report_exception()


# ================================
# RESTART
# ================================
def restart(p, msg=None):
    if msg:
        sendMessageTemplate(p, msg)
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
        sendMessageTemplate(p, "A problem has been detected (" + methodName +
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
    players = person.getPersonByIdMulti(g.getPlayerIds())
    for p in players:
        if p:
            p.setGameRoom(None)
            sendMessageTemplate(p, msg, remove_keyboard=True, sleepDelay=True)
            restart(p)
    if g.isPublic():
        g.resetGame()
    else:
        game.deleteGame(g)

def broadcastResultImageToPlayers(g, file_data):
    players = person.getPersonByIdMulti(g.getPlayerIds())
    for p in players:
        sendPhotoDataTemplate(p, file_data, 'results.png')
        sleep(0.1)

def redirectPlayersToState(g, new_state):
    players = person.getPersonByIdMulti(g.getPlayerIds())
    for p in players:
        redirectToState(p, new_state)

def sendPlayersWaitingAction(g, sleep_time=None):
    players = person.getPersonByIdMulti(g.getPlayerIds())
    for p in players:
        sendWaitingActionTemplate(p, sleep_time = sleep_time)

def tellPlayers(g, msg):
    players = person.getPersonByIdMulti(g.getPlayerIds())
    for p in players:
        sendMessageTemplate(p, msg, sleepDelay=True)

def tellCritics(g, msg):
    critics = person.getPersonByIdMulti(g.getCriticsId())
    for p in critics:
        sendMessageTemplate(p, msg, sleepDelay=True)

def tellBadPressOfficer(g, msg):
    p = Person.get_by_id(g.getBadPressOfficerId())
    sendMessageTemplate(p, msg, sleepDelay=True)

def updateAndSendScoresToPlayers(g):
    handScores = g.computeHandScores()
    bpo_id = g.getBadPressOfficerId()
    for p_id, scores in handScores.iteritems():
        bpo_disguiser_reward, detective_reward, critic_disguiser_reward = handScores[p_id]
        if p_id == bpo_id:
            if bpo_disguiser_reward>0:
                msg_bpo = '😀 You got {0} {1} (bad press officer disguiser rewards): ' \
                      '{0} critics did not discover that your headline was shady!'.format(
                    bpo_disguiser_reward, icons.BPO_DISGUISER_REWARD)
            else:
                msg_bpo = '😕 You got 0 {} (bad press officer disguiser rewards): ' \
                      'all critics discovered that your headline was shady.'.format(icons.BPO_DISGUISER_REWARD)
            bpo = Person.get_by_id(bpo_id)
            sendMessageTemplate(bpo, msg_bpo, sleepDelay=True, remove_keyboard=True)
        else:
            if detective_reward>0:
                msg = '😀 You got the {} (detective reward): ' \
                      "you were able to recognize the bad press officer's shady headline".format(icons.DETECTIVE_REWARD)
            else:
                msg = '😕 You did not get the {} (detective reward): ' \
                      "you were not able to recognize the bad press officer's shady headline".format(icons.DETECTIVE_REWARD)
            msg += '\n'
            if critic_disguiser_reward>0:
                msg += '😀 You got {0} {1} (critic disguiser rewards): ' \
                      '{0} critic(s) thought that your headline was shady.'.format(
                    critic_disguiser_reward, icons.CRITIC_DISGUISER_REWARD)
            else:
                msg += '😕 You got 0 {} (critic disguiser rewards): ' \
                      'no critic thought that your headline was shady.'.format(icons.CRITIC_DISGUISER_REWARD)
            p = Person.get_by_id(p_id)
            sendMessageTemplate(p, msg, sleepDelay=True, remove_keyboard=True)


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
        sendMessageTemplate(p, msg, kb)
    else:
        if input in ['/help', buttons.HELP]:
            sendMessageTemplate(p, messages.INSTRUCTIONS)
        elif input == buttons.ENTER_GAME:
            redirectToState(p, 20)
        elif p.chat_id in key.MASTER_CHAT_ID:
            sendMessageTemplate(p, messages.NOT_VALID_INPUT, kb=kb)
        else: # including input == ''
            sendMessageTemplate(p, messages.NOT_VALID_INPUT, kb=kb)

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
        sendMessageTemplate(p, msg, kb)
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
                    sendMessageTemplate(p, msg)
                    sendWaitingActionTemplate(p, sleep_time=1)
                    repeatState(p)
            else:
                msg = "{} You didn't enter a valid game room name, " \
                      "if you want to create a new one press {}.".format(icons.EXCLAMATION_ICON, buttons.NEW_GAME_ROOM)
                sendMessageTemplate(p, msg)
        else:  # input == ''
            sendMessageTemplate(p, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# GO TO STATE 21: Create new game
# ================================
def goToState21(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    if input == '':
        sendMessageTemplate(p, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())
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
            sendMessageTemplate(p, msg, kb)
        else:
            input = input.upper()
            if game.gameExists(input):
                msg = "{} A game with this name already exists. Please try again.".format(icons.EXCLAMATION_ICON)
                sendMessageTemplate(p, msg)
            else:
                game_parameters['stage'] = 1
                game_parameters['game_name'] = input
                repeatState(p, put=True)
    elif stage == 1: # number of players
        if giveInstructions:
            kb = [['3','4','5','6'],[buttons.BACK]]
            p.setLastKeyboard(kb)
            msg = "Please enter the number of people."
            sendMessageTemplate(p, msg, kb)
        else:
            if utility.representsIntBetween(input, 2, 30):
                sendWaitingActionTemplate(p)
                number_players = int(input)
                game_name = game_parameters['game_name']
                g = game.createGame(game_name, number_players)
                g.addPlayer(p)
                redirectToState(p, 22)
            else:
                msg = "{} Please enter a number between 3 and 30.".format(icons.EXCLAMATION_ICON)
                sendMessageTemplate(p, msg)

# ================================
# GO TO STATE 22: Game: Waiting for start
# ================================
def goToState22(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    giveInstruction = input is None
    g = p.getGame()
    if giveInstruction:
        msg = "Entering the game *{}*".format(g.getGameRoomName())
        sendMessageTemplate(p, msg, remove_keyboard=True)
        tellPlayers(g, "Player {} joined the game!".format(p.getFirstName()))
        if g.readyToStart():
            msg = "Starting the game..."
            tellPlayers(g, msg)
            g.startGame()
            redirectPlayersToState(g, 30)
        else:
            msg = "Waiting for {} other players...".format(g.remainingSeats())
            tellPlayers(g, msg)
    else:
        msg = "{} Please wait for the other players to join the game.".format(icons.EXCLAMATION_ICON)
        sendMessageTemplate(p, msg)


# ================================
# GO TO STATE 30: Game: Choose Own Card
# ================================
def goToState30(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    g = p.getGame()
    if g == None:
        return # game deleted because no more cards
    giveInstruction = input is None
    isBadPressOfficer = p.getId() == g.getBadPressOfficerId()
    kb = utility.distributeElementMaxSize([str(r) for r in range(1, parameters.CARDS_PER_PLAYER + 1)])
    if giveInstruction:
        cards = g.givePlayersCards(p.getId())
        if cards:
            msg = "✋ HAND {}\n".format(g.getHandNumber())
            if isBadPressOfficer:
                msg += "YOU ARE THE {} *BAD PRESS OFFICER*!!\n" \
                       "These are your *SHADY NEWS*, " \
                       "please choose the one that looks *MOST REALISTIC* to you:\n".format(icons.BAD_PRESS_OFFICER)
            else:
                msg += "YOU ARE A {} *CRITIC*!\n" \
                       "The *bad press officer* is {}\n" \
                       "These are your *RELIABLE NEWS*, " \
                       "please choose the one it looks *MOST SHADY* to you:\n".format(icons.CRITIC, g.getBadPressOfficerName())
            sendMessageTemplate(p, msg)
            msg = "\n".join(['/{} {}'.format(n, utility.escapeMarkdown(c)) for n, c in enumerate(cards, 1)])
            sendMessageTemplate(p, msg, kb)
        else:
            #g.sendFinalScores()
            msg = "The game is terminated because there are no more headlines to play."
            terminateGame(g, msg)
    else:
        if input.startswith('/'):
            numberStr = input[1:]
        else:
            numberStr = input
        if utility.representsIntBetween(numberStr, 1, parameters.CARDS_PER_PLAYER):
            index = int(numberStr) - 1
            g.storePlayerChosenCard(p.getId(), index)
            if g.haveAllPlayersChosenACard():
                g.computePlayersCardsShuffle()
                redirectPlayersToState(g, 31)
            else:
                msg = "👍 Thanks for your selection!\n" \
                      "Let's wait for all players to choose an headline."
                sendMessageTemplate(p, msg, remove_keyboard=True)
        else: #including input == ''
            sendMessageTemplate(p, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# GO TO STATE 31: Game: Critics Guess Card
# ================================
def goToState31(p, **kwargs):
    input = kwargs['input'] if 'input' in kwargs.keys() else None
    g = p.getGame()
    if g == None:
        return # game deleted because no more cards
    giveInstruction = input is None
    isBadPressOfficer = p.getId() == g.getBadPressOfficerId()
    if giveInstruction:
        msg = "👍 Great, all players have chosen an headline!\n" \
              "Now the critics should try to guess the shady headline.\n"
        if isBadPressOfficer:
            msg += "⌛ Please wait..."
        else:
            msg = "Try to detect the *SHADY NEWS* from the followings:"
        sendMessageTemplate(p, msg, remove_keyboard=True)
        if not isBadPressOfficer:
            cards_shuffle = g.getCriticCardsShuffle(p.getId())
            kb = utility.distributeElementMaxSize([str(r) for r in range(1, len(cards_shuffle) + 1)])
            msg = "\n".join(['/{} {}'.format(n, utility.escapeMarkdown(c)) for n, c in enumerate(cards_shuffle, 1)])
            sendMessageTemplate(p, msg, kb)
            p.setLastKeyboard(kb)
    else:
        if isBadPressOfficer:
            msg = "{} Please wait for the critics to guess the shady headline.".format(icons.EXCLAMATION_ICON)
            sendMessageTemplate(p, msg)
            return
        if input.startswith('/'):
            numberStr = input[1:]
        else:
            numberStr = input
        if utility.representsIntBetween(numberStr, 1, parameters.CARDS_PER_PLAYER):
            cardsShufflePlayer = g.getCriticCardsShuffle(p.getId())
            card = cardsShufflePlayer[int(numberStr) - 1]
            if g.storeCriticGuessedCard(p.getId(), card):
                if g.haveAllCriticsGuessedACard():
                    msg = "👍 Great, all critics have made their choice!"
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
                    msg = "⌛ Waiting for the other critics to pick an headline."
                    sendMessageTemplate(p, msg, remove_keyboard=True)
            else:
                msg = "{} You cannot choose your own headline, please try again.".format(icons.EXCLAMATION_ICON)
                sendMessageTemplate(p, msg, kb=p.getLastKeyboard())
        else: #including input == ''
            sendMessageTemplate(p, messages.NOT_VALID_INPUT, kb=p.getLastKeyboard())

# ================================
# HANDLERS
# ================================

class SafeRequestHandler(webapp2.RequestHandler):
    def handle_exception(self, exception, debug_mode):
        report_exception()

def deferredSafeHandleException(obj, *args, **kwargs):
    #return
    try:
        deferred.defer(obj, *args, **kwargs)
    except: # catch *all* exceptions
        report_exception()

def report_exception():
    import traceback
    msg = "❗ Detected Exception: " + traceback.format_exc()
    tellMaster(msg)
    logging.error(msg)


class CheckExpiredGames(SafeRequestHandler):
    def get(self):
        for g in Game.query():
            if g.isGameExpired():
                msg = "{} The game has terminated because it has been idle for too long".format(icons.TIME_ICON)
                terminateGame(g, msg)

# ================================
# Main user interaction function
# ================================

def setFB_Menu():
    handlers_fb.setMenu(['HELP','START'])

def dealWithUserInteraction(chat_id, first_name, last_name, username, facebook, user_input):
    p = person.getPersonByIdAndApp(chat_id,facebook)
    if p is None:
        # new user
        logging.info("Text: " + user_input)
        if user_input == '/help':
            sendMessageTemplateChatId(chat_id, facebook, messages.INSTRUCTIONS)
        elif user_input.startswith("/start"):
            if facebook:
                first_name, last_name = handlers_fb.getUserInfo(chat_id)
            p = person.addPerson(chat_id, first_name, last_name, username, facebook)
            msg = "Hi {}, welcome to KriticosBot!\n".format(p.getFirstName())  # + START_MESSAGE
            sendMessageTemplate(p, msg)
            restart(p)
            tellMaster("New user: " + p.getFirstNameLastNameUserName())
        else:
            msg = "Please type START if you want to begin."
            sendMessageTemplateChatId(chat_id, facebook, msg)
    else:
        # known user
        if not facebook:
            p.updateInfo(first_name, last_name, username)
        if user_input == '/state':
            if p.state in STATES:
                sendMessageTemplate(p, "You are in state " + str(p.state) + ": " + STATES[p.state])
            else:
                sendMessageTemplate(p, "You are in state " + str(p.state))
        elif user_input.strip() in ["/start","START"]:
            if p.getGame() != None:
                msg = "{} You are still in a game!".format(icons.EXCLAMATION_ICON)
                sendMessageTemplate(p, msg)
            else:
                msg = "Hi {}, welcome back to KriticosBot!\n\n".format(p.getFirstName())
                sendMessageTemplate(p, msg)
                p.setEnabled(True, put=False)
                restart(p)
        elif user_input.startswith("/exit"):
            g = p.getGame()
            if g == None:
                msg = "{} You are not in a game!".format(icons.EXCLAMATION_ICON)
                sendMessageTemplate(p, msg)
            else:
                terminateGame(g, "The game has terminated because {} exited.".format(p.getFirstName()))
        elif WORK_IN_PROGRESS and p.chat_id not in key.TEST_PLAYERS:
            logging.debug('person {} not in {}'.format(p.chat_id, key.TEST_PLAYERS))
            sendMessageTemplate(p, icons.UNDER_CONSTRUCTION + " System under maintanence, try later.")
        else:
            logging.debug("Sending {} to state {} with input {}".format(p.getFirstName(), p.state, user_input))
            repeatState(p, input=user_input) #, contact=contact, photo=photo, document=document, voice=voice


app = webapp2.WSGIApplication([
    # ADMIN
    ('/admin_me', handlers_tg.MeHandler),
    ('/admin_set_webhook', handlers_tg.SetWebhookHandler),
    ('/admin_delete_webhook', handlers_tg.DeleteWebhook),
    ('/admin_get_webhook_info', handlers_tg.GetWebhookInfo),
    # TELEGRAM
    (key.WEBHOOK_PATH, handlers_tg.WebhookHandler),
    # FACEBOOK
    (key.FACEBOOK_WEBHOOK_PATH, handlers_fb.WebhookHandler),
    # PUBLIC_URL
    ('/checkExpiredGames', CheckExpiredGames),
    ('/gamestatus', game.getGameStatus),
    ('/gamestatusjson', game.getGameStatusJson),
], debug=True)

possibles = globals().copy()
possibles.update(locals())
