# -*- coding: utf-8 -*-

import logging
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import parameters
import requests
import headlines
import rss_parser
import utility
from datetime import datetime
from random import randint
from random import shuffle
import webapp2
import json

#------------------------
# GAME_VARIABLES KEYS
#------------------------
PLAYER_NAMES = 'player_names' # --> [ string, string, ... ]
HAND_NUMBER = 'hand_number' # --> int
LEGITIMATE_CARDS = 'legitimate_cards' # [ string, string, ... ]
ILLEGITIMATE_CARDS = 'illegitimate_cards' # [ string, string, ... ]
SELECTED_LEGITIMATE_INDEXES = 'selected_legitimate_indexes' # --> [ int, int, ... ]
SELECTED_ILLEGITIMATE_INDEXES = 'selected_illegitimate_indexes' # --> [ int, int, ... ]
GAME_SCORES = 'game_scores' # --> { player_id1: int, player_id2: int, ...}

#------------------------
# HAND_VARIABLES KEYS
#------------------------
HAND_DEALT_CARDS = 'dealt_cards' # --> { player_id1: ['card'], player_id2: ['card'], ...}
HAND_CHOSEN_CARDS = 'chosen_cards' # --> { player_id1: 'card', player_id2: 'card', ...}
HAND_GUESSED_CARDS = 'guessed_cards' # --> { player_id1: 'card', player_id2: 'card', ...}
HAND_CARDS_SHUFFLE_LIST = 'cards_shuffle_list' # --> { player_id1: ['card', 'card',...], player_id2: ...}
HAND_SCORES = 'hands_scores' # --> { player_id1: [BPO_DISGUISER_POINT, CRITIC_DISGUISER_POINT, DETECTIVE_POINT], player_id2: ...}

#------------------------
# Game class
#------------------------

class Game(ndb.Model):
    players_ids = ndb.IntegerProperty(repeated=True)
    number_seats = ndb.IntegerProperty()
    public = ndb.BooleanProperty()
    started = ndb.BooleanProperty()
    game_variables = ndb.PickleProperty()
    hand_variables = ndb.PickleProperty()
    last_mod = ndb.DateTimeProperty(auto_now=True)

    def getGameRoomName(self):
        return self.key.id()

    def getCurrentNumberOfPlayers(self):
        return len(self.players_ids)

    def getNumberOfSeats(self):
        return self.number_seats

    def isPublic(self):
        return self.public

    def isGameExpired(self):
        diff_sec = (datetime.now() - self.last_mod).total_seconds()
        if self.started:
            return diff_sec > parameters.GAME_EXPIRATION_SECONDS_IN_GAME
        if len(self.players_ids)>0:
            return diff_sec > parameters.GAME_EXPIRATION_SECONDS_IN_WAITING_FOR_PLAYERS
        return False

    def resetGameVariables(self):
        self.game_variables = {
            PLAYER_NAMES: [],
            HAND_NUMBER: 0,
            LEGITIMATE_CARDS: rss_parser.getLegitimateHeadlines(), #headlines.getLegitimateHeadlines(),
            ILLEGITIMATE_CARDS: rss_parser.getIllegitimateHeadlines(), #headlines.getIllegitimateHeadlines(),
            SELECTED_LEGITIMATE_INDEXES: [],
            SELECTED_ILLEGITIMATE_INDEXES: [],
            GAME_SCORES: {}
        }

    def resetHandVariables(self):
        self.hand_variables = {
            HAND_DEALT_CARDS: {},
            HAND_CHOSEN_CARDS: {},
            HAND_GUESSED_CARDS: {},
            HAND_CARDS_SHUFFLE_LIST: {},
            HAND_SCORES: {}
        }
        self.initializeHandScores()

    def initializeGameScores(self):
        for p in self.players_ids:
            self.game_variables[GAME_SCORES][p] = 0 # INCLUDING TOTAL

    def initializeHandScores(self):
        for p in self.players_ids:
            self.hand_variables[HAND_SCORES][p]=[0,0,0]

    def getPlayerIds(self):
        return [x for x in self.players_ids]

    def getPlayerName(self, p_id):
        return self.game_variables[PLAYER_NAMES][self.players_ids.index(p_id)]

    def getHandNumber(self):
        return self.game_variables[HAND_NUMBER]

    def getBadPressOfficerIndex(self):
        return (self.getHandNumber() - 1) % self.number_seats

    def getBadPressOfficerName(self):
        pos = self.getBadPressOfficerIndex()
        return self.game_variables[PLAYER_NAMES][pos]

    def getBadPressOfficerId(self):
        pos = self.getBadPressOfficerIndex()
        return self.players_ids[pos]

    def getCriticsId(self):
        return [x for x in self.players_ids if x != self.getBadPressOfficerId()]

    def areMorePlayersAccepted(self):
        return len(self.players_ids) < self.number_seats

    def remainingSeats(self):
        return self.number_seats - len(self.players_ids)

    def resetGame(self):
        self.players_ids = []
        self.resetGameVariables()
        self.resetHandVariables()
        self.game_variables[HAND_NUMBER] = 1
        self.started = False
        self.put()

    def startGame(self):
        self.started = True
        self.initializeGameScores()
        self.initializeHandScores()
        self.put()

    def nextHand(self):
        self.resetHandVariables()
        self.game_variables[HAND_NUMBER] += 1
        self.put()

    def readyToStart(self):
        return len(self.players_ids) == self.number_seats

    @ndb.transactional(retries=100, xg=True)
    def addPlayer(self, player, put=True):
        if len(self.players_ids) < self.number_seats:
            self.players_ids.append(player.chat_id)
            self.game_variables[PLAYER_NAMES].append(player.getFirstName())
            player.setGameRoom(self.getGameRoomName())
            if put:
                self.put()
            return True
        return False

    @ndb.transactional(retries=100, xg=True)
    def givePlayersCards(self, player_id):
        cards = []
        i = 1 if player_id == self.getBadPressOfficerId() else 0
        source_cards = [
            self.game_variables[LEGITIMATE_CARDS],
            self.game_variables[ILLEGITIMATE_CARDS]
        ]
        source_indexes = [
            self.game_variables[SELECTED_LEGITIMATE_INDEXES],
            self.game_variables[SELECTED_ILLEGITIMATE_INDEXES]
        ]
        cards_list, indexes = source_cards[i], source_indexes[i]
        while len(cards) < parameters.CARDS_PER_PLAYER:
            r = randint(0, len(cards_list) - 1)
            if r in indexes:
                continue
            indexes.append(r)
            cards.append(cards_list[r])
            if len(indexes)==len(cards_list):
                return False
        self.hand_variables[HAND_DEALT_CARDS][player_id] = cards
        self.put()
        return cards

    @ndb.transactional(retries=100, xg=True)
    def storePlayerChosenCard(self, player_id, index):
        card = self.hand_variables[HAND_DEALT_CARDS][player_id][index]
        logging.debug("storePlayerChosenCard: adding card {} to player {}".format(card, player_id))
        self.hand_variables[HAND_CHOSEN_CARDS][player_id] = card
        logging.debug("{}: {}".format(HAND_CHOSEN_CARDS, self.hand_variables[HAND_CHOSEN_CARDS]))
        self.put()

    @ndb.transactional(retries=100, xg=True)
    def storeCriticGuessedCard(self, player_id, card):
        if card == self.hand_variables[HAND_CHOSEN_CARDS][player_id]:
            return False
        self.hand_variables[HAND_GUESSED_CARDS][player_id] = card
        self.put()
        return True

    def haveAllPlayersChosenACard(self):
        return len(self.hand_variables[HAND_CHOSEN_CARDS]) == self.number_seats

    def haveAllCriticsGuessedACard(self):
        return len(self.hand_variables[HAND_GUESSED_CARDS]) == self.number_seats - 1

    def computePlayersCardsShuffle(self):
        for p_id in self.getPlayerIds():
            cards_shuffle = [c for p, c in self.hand_variables[HAND_CHOSEN_CARDS].iteritems() if p != p_id]
            shuffle(cards_shuffle)
            self.hand_variables[HAND_CARDS_SHUFFLE_LIST][p_id] = cards_shuffle
        self.put()

    def getCriticCardsShuffle(self, p_id):
        return self.hand_variables[HAND_CARDS_SHUFFLE_LIST][p_id]

    def getAllCardsShuffle(self):
        cards_dict = self.hand_variables[HAND_CHOSEN_CARDS]
        cards_shuffle = cards_dict.values()
        shuffle(cards_shuffle)
        return cards_shuffle

    def getHandScores(self):
        return self.hand_variables[HAND_SCORES]

    def getGameScores(self):
        return self.game_variables[GAME_SCORES]

    def computeHandScores(self, put=False):
        bpo_id = self.getBadPressOfficerId()
        for p_id in self.players_ids:
            bpo_disguiser_reward, detective_reward, critic_disguiser_reward = 0, 0, 0
            p_card = self.hand_variables[HAND_CHOSEN_CARDS][p_id]
            guessed_cards_list = self.hand_variables[HAND_GUESSED_CARDS].values()
            people_chosing_p_card = guessed_cards_list.count(p_card)
            if p_id==bpo_id:
                bpo_disguiser_reward = self.number_seats - 1 - people_chosing_p_card
            else:
                bpo_card = self.hand_variables[HAND_CHOSEN_CARDS][bpo_id]
                my_guessed_card = self.hand_variables[HAND_GUESSED_CARDS][p_id]
                detective_reward = 1 if bpo_card==my_guessed_card else 0
                critic_disguiser_reward = people_chosing_p_card
            self.getHandScores()[p_id] = [bpo_disguiser_reward, detective_reward, critic_disguiser_reward]
        if put:
            self.put()
        return self.getHandScores()

    def updateGameScores(self, put=True):
        import icons
        bpo_id = self.getBadPressOfficerId()
        handScores = self.getHandScores()
        score_table = [
            ['', parameters.ICON_POINTS_BPO_DISGUISER, parameters.ICON_POINT_CRITIC_DETECTIVE,
             parameters.ICON_POINT_CRITIC_DISGUISER, 'TOTAL']
        ]
        gameScores = self.getGameScores()
        for p_id, p_id_hand_scores in handScores.iteritems():
            role_icon = icons.BAD_PRESS_OFFICER if p_id == self.getBadPressOfficerId() else icons.CRITIC
            icon_name = role_icon + ' ' + self.getPlayerName(p_id)

            p_id_oldGameScores = gameScores[p_id]
            p_id_totalHandScores = sum([x * y for x, y in zip(p_id_hand_scores, parameters.POINTS_ARRAY)])
            p_id_newGameScores = p_id_oldGameScores + p_id_totalHandScores
            total_str = "{}+{}={}".format(p_id_oldGameScores, p_id_totalHandScores, p_id_newGameScores)

            score_row = [icon_name, str(p_id_hand_scores[0]), str(p_id_hand_scores[1]), str(p_id_hand_scores[2]), total_str]
            score_table.append(score_row)

            gameScores[p_id] = p_id_newGameScores

        if put:
            self.put()

        logging.debug('Sending score_table: {}'.format(score_table))
        return score_table

    '''
    def howManyPeopleChoseMyCard(self, chat_id):
        return self.hand_variables[HAND_SCORES][chat_id]

    def whoChoseTheBadPressOfficerCard(self):
        bpo_id = self.getBadPressOfficerId()
        bpo_card = self.hand_variables[HAND_CHOSEN_CARDS][bpo_id]
        result = [p for p,c in self.hand_variables[HAND_GUESSED_CARDS].iteritems() if c==bpo_card]
        return result
    '''

    def isThereASingleWinner(self):
        return sum([score>=parameters.WINNING_SCORE for score in self.getGameScores().values()])==1

    def getWinnerNames(self):
        max_score = max(score for score in self.getGameScores().values())
        if max_score == 0:
            return []
        winners_id = [id for id, score in self.getGameScores().iteritems() if score==max_score]
        return [self.getPlayerName(x) for x in winners_id]


def gameExists(name):
    return Game.get_by_id(name)!=None

def createGame(name, number_seats, public=False, put=False):
    g = Game.get_by_id(name)
    if g == None:
        g = Game(id=name)
        g.number_seats = number_seats
        g.public = public
        g.resetGame()
        if put:
            g.put()
        return g
    return None

def getGame(name):
    return Game.get_by_id(name)

def deleteGame(game):
    game.key.delete()


#########

def populatePublicGames():
    for game, info in parameters.PUBLIC_GAME_ROOMS_INFO.iteritems():
        createGame(game, info['PLAYERS'], public=True, put=True)

def deleteAllPrivateGames():
    create_futures = ndb.delete_multi_async(
        Game.query(Game.public==False).fetch(keys_only=True)
    )
    ndb.Future.wait_all(create_futures)

def deleteAllGames():
    create_futures = ndb.delete_multi_async(
        Game.query().fetch(keys_only=True)
    )
    ndb.Future.wait_all(create_futures)

def getGameNames():
    return [x.getGameRoomName() for x in Game.query().fetch()]

def pushGameState(data=None):
    requests.post('http://donderskritikos.herokuapp.com/webhook', data={'test': 'this is a test'})

class getGameStatusJson(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        g = getGame(parameters.DEFAULT_GAME_ROOM)
        ready = g.haveAllPlayersChosenACard()
        data = {
            'ready': ready,
            'cards': g.getAllCardsShuffle()
            #'cards': ['test1', 'test2', 'test3', 'test4']
        }
        self.response.headers['Content-Type'] = 'application/json; charset=utf-8'
        self.response.out.write(json.dumps(data, indent=4, ensure_ascii=False))

class getGameStatus(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        g = getGame(parameters.DEFAULT_GAME_ROOM)
        cards = g.getAllCardsShuffle()
        with open('html/index.html', 'r') as htmlFile:
            html_string = htmlFile.read()
            html_string = html_string.replace("SENTENCE1", cards[0])
            html_string = html_string.replace("SENTENCE2", cards[1])
            html_string = html_string.replace("SENTENCE3", cards[2])
            html_string = html_string.replace("SENTENCE4", cards[3])
            self.response.write(html_string)
