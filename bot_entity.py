import telebot
import time
from threading import Thread
from telebot import types
from buy_sell_bot_v0 import *
import json
import helpers
from derebit_ws import *
import my_data


class BotEntity:
    
    def __init__(self, name, params=None):
        if params is None:
            params = {
        "name": name,
        "coin": None,
        "pair_base": None,
        "pair_second": None,
        "side_base": None,
        "side_second": None,
        'basis': None,                
        "amount_base": None,
        "amount_second": None,
        "max_price_diff_up": None,
        "max_price_diff_down": None,
        }
        self.name = name
        self.params = params
        self.is_working = False
    
    def trading_bot_loop(self):
        global num_of_running_bots 
        trading_bot = BasisTradingBot(self.params, ws, bot)
        try:
            trading_bot.make_trade()
            if self.params["is_working"]:
                bot.send_message(-561707350, 'Bot closed because trade done')
                self.params["is_working"] = False
            else:
                trading_bot.close_bot()
                bot.send_message(-561707350, 'Bot closed through tg')
            num_of_running_bots -= 1
            
        except KeyboardInterrupt:
            trading_bot.close_bot()
            bot.send_message(-561707350, 'Bot closed by KeyboardInterrupt')
            num_of_running_bots -= 1

    def start(self):
        global num_of_running_bots 
        self.params["is_working"] = True
        self.worker = Thread(target=self.trading_bot_loop)
        self.worker.start()
        num_of_running_bots += 1
    
    def stop(self):
        self.params["is_working"] = False
        self.worker.join()

    def info(self):
        return dict_to_str(self.params)