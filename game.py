# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import parameters
import requests
import headlines
import utility
from random import randint
import webapp2
import json

#------------------------
# HAND_VARIABLES NAMES
#------------------------
HAND_CARDS = 'cards'

#------------------------
# Game class
#------------------------

GAME_NAME = "SINGLE_MODE"

class Game(ndb.Model):
    players_ids = ndb.IntegerProperty(repeated=True)
    players_names = ndb.StringProperty(repeated=True)
    started = ndb.BooleanProperty()
    hand = ndb.IntegerProperty(default=0)
    selected_legitimate_indexes = ndb.IntegerProperty(repeated=True)
    selected_illegitimate_indexes = ndb.IntegerProperty(repeated=True)
    hand_variables = ndb.PickleProperty()
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
    g.hand = 0
    g.hand_variables = {HAND_CARDS: {}}
    g.put()

def nextHand():
    g = getGame()
    g.hand += 1
    g.hand_variables = {}
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
    return g.players_names[pos].encode('utf-8')

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

def setPlayerCard(player_id, headline):
    g = getGame()
    g.hand_variables[HAND_CARDS][player_id] = headline
    g.put()

def haveAllPlayersPlayedTheirCards():
    g = getGame()
    return len(g.hand_variables[HAND_CARDS])==parameters.PLAYERS

#########

def pushGameState(data=None):
    requests.post('http://donderskritikos.herokuapp.com/webhook', data={'test': 'this is a test'})

class getGameStatusJson(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        data = {'test': 'this is a test'}
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(data, indent=4, ensure_ascii=False))

class getGameStatus(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        with open('html/index.html', 'r') as htmlFile:
            html_string = htmlFile.read()
            self.response.write(html_string)
