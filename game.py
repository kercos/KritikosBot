# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import parameters
import requests
import headlines
import utility
from random import randint
from random import shuffle
import webapp2
import json

#------------------------
# HAND_VARIABLES NAMES
#------------------------
HAND_CHOSEN_CARDS = 'chosen_cards'
HAND_GUESSED_CARDS = 'guessed_cards'
HAND_CARDS_SHUFFLE_LIST = 'cards_shuffle_list'
HAND_POINTS = 'hadn_points'

#------------------------
# Game class
#------------------------

GAME_NAME = "SINGLE_MODE"

class Game(ndb.Model):
    players_ids = ndb.PickleProperty()
    players_names = ndb.PickleProperty()
    started = ndb.BooleanProperty()
    hand = ndb.IntegerProperty(default=0)
    selected_legitimate_indexes = ndb.PickleProperty()
    selected_illegitimate_indexes = ndb.PickleProperty()
    hand_variables = ndb.PickleProperty()
    game_point = ndb.PickleProperty()
    # 'cards': { player_id1: 'headline', player_id2: 'headline', ...}

def createGame():
    g = Game(id = GAME_NAME)
    g.put()

def getGame():
    return Game.get_by_id(GAME_NAME)

def getPlayersId():
    g = getGame()
    return g.players_ids

def getDealerIndex(g):
    return (g.hand % parameters.PLAYERS) - 1

def getDealerId(g = None):
    if g==None:
        g = getGame()
    pos = getDealerIndex(g)
    return g.players_ids[pos]

def getHandNumber():
    g = getGame()
    return g.hand

def getCheckersId():
    g = getGame()
    return [x for x in g.players_ids if x != getDealerId(g)]

def areMorePlayersAccepted():
    g = getGame()
    return len(g.players_ids)<parameters.PLAYERS

def remainingSeats():
    g = getGame()
    return parameters.PLAYERS - len(g.players_ids)

def startGame():
    g = getGame()
    g.started = True
    g.hand = 1
    g.put()

def resetGame():
    g = getGame()
    g.players_ids = []
    g.players_names = []
    g.selected_legitimate_indexes = []
    g.selected_illegitimate_indexes = []
    g.game_point = {}
    g.hand = 0
    g.hand_variables = {HAND_CHOSEN_CARDS: {}, HAND_GUESSED_CARDS: {}, HAND_CARDS_SHUFFLE_LIST: [], HAND_POINTS: {}}
    g.put()

def nextHand():
    g = getGame()
    g.hand += 1
    g.hand_variables = {HAND_CHOSEN_CARDS: {}, HAND_GUESSED_CARDS: {}, HAND_CARDS_SHUFFLE_LIST: [], HAND_POINTS: {}}
    g.put()

def addPlayer(p):
    g = getGame()
    if len(g.players_ids)<parameters.PLAYERS:
        g.players_ids.append(p.chat_id)
        g.players_names.append(p.getFirstName())
        g.put()
        return True
    return False

def readyToStart():
    g = getGame()
    return len(g.players_ids)==parameters.PLAYERS

def getDealerName():
    g = getGame()
    pos = getDealerIndex(g)
    return g.players_names[pos]

def getHeadlineListIndexes(g, dealer):
    bin = 1 if dealer else 0
    headline_list = headlines.HEADLINES[bin]
    indexes = g.selected_legitimate_indexes if bin==0 else g.selected_illegitimate_indexes
    return headline_list, indexes

def givePlayersCards(dealer):
    g = getGame()
    cards = []
    headline_list, indexes = getHeadlineListIndexes(g, dealer)
    while len(cards) < parameters.CARDS_PER_PLAYER:
        i = randint(0, len(headline_list)-1)
        if i in indexes:
            continue
        indexes.append(i)
        cards.append(headline_list[i])
    g.put()
    return cards

def storePlayerChosenCard(player_id, headline):
    g = getGame()
    g.hand_variables[HAND_CHOSEN_CARDS][player_id] = headline
    g.put()

def storeCheckerGuessedCard(player_id, headline):
    g = getGame()
    g.hand_variables[HAND_GUESSED_CARDS][player_id] = headline
    g.put()

def haveAllPlayersPlayedTheirCards():
    g = getGame()
    return len(g.hand_variables[HAND_CHOSEN_CARDS]) == parameters.PLAYERS

def haveAllCheckersGuessedTheirCards():
    g = getGame()
    return len(g.hand_variables[HAND_GUESSED_CARDS]) == parameters.PLAYERS-1

def computePlayersCardsShuffle():
    g = getGame()
    cards_dict = g.hand_variables[HAND_CHOSEN_CARDS]
    cards_shuffle = cards_dict.values()
    shuffle(cards_shuffle)
    g.hand_variables[HAND_CARDS_SHUFFLE_LIST] = cards_shuffle
    g.put()

def getPlayersCardsShuffle():
    g = getGame()
    return g.hand_variables[HAND_CARDS_SHUFFLE_LIST]

def howManyPeopleChoseMyCard(chat_id):
    g = getGame()
    my_heading = g.hand_variables[HAND_CHOSEN_CARDS][chat_id]
    guessed_headings = g.hand_variables[HAND_GUESSED_CARDS].values()
    return guessed_headings.count(my_heading)

def computeHandScore():
    g = getGame()


#########

def pushGameState(data=None):
    requests.post('http://donderskritikos.herokuapp.com/webhook', data={'test': 'this is a test'})

class getGameStatusJson(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        ready = haveAllPlayersPlayedTheirCards()
        data = {
            'ready': ready,
            #'cards': getPlayersCardsShuffle()
            'cards': ['test1', 'test2', 'test3', 'test4']
        }
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(data, indent=4, ensure_ascii=False))

class getGameStatus(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        with open('html/index.html', 'r') as htmlFile:
            html_string = htmlFile.read()
            self.response.write(html_string)
