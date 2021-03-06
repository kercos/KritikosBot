# -*- coding: utf-8 -*-

from google.appengine.ext import ndb
import icons


CARDS_PER_PLAYER = 5
WINNING_SCORE = 11


GAME_EXPIRATION_SECONDS_IN_GAME = 150
GAME_EXPIRATION_SECONDS_IN_WAITING_FOR_PLAYERS = 300
MIN_WORDS_IN_SENTENCE = 5

GAME_ROOM_TRIANGLE = "TRIO - 3️⃣👤"
GAME_ROOM_SQUARE = "SQUARE - 4️⃣👤"
GAME_ROOM_PENTAGON = "QUINTET - 5️⃣👤"
PUBLIC_GAME_ROOM_NAMES = [GAME_ROOM_TRIANGLE, GAME_ROOM_SQUARE, GAME_ROOM_PENTAGON]
PUBLIC_GAME_ROOMS_INFO = {
    GAME_ROOM_TRIANGLE: {
        'PLAYERS': 3
    },
    GAME_ROOM_SQUARE: {
        'PLAYERS': 4
    },
    GAME_ROOM_PENTAGON: {
        'PLAYERS': 5
    }
}

DEFAULT_GAME_ROOM = GAME_ROOM_SQUARE

POINTS_BPO_DISGUISER = 3
POINT_CRITIC_DETECTIVE = 2
POINT_CRITIC_DISGUISER = 2
POINTS_ARRAY = [POINTS_BPO_DISGUISER, POINT_CRITIC_DETECTIVE, POINT_CRITIC_DISGUISER]

ICON_POINTS_BPO_DISGUISER = "{} (x{})".format(icons.BPO_DISGUISER_REWARD, POINTS_BPO_DISGUISER)
ICON_POINT_CRITIC_DETECTIVE = "{} (x{})".format(icons.DETECTIVE_REWARD, POINT_CRITIC_DETECTIVE)
ICON_POINT_CRITIC_DISGUISER = "{} (x{})".format(icons.CRITIC_DISGUISER_REWARD, POINT_CRITIC_DISGUISER)
