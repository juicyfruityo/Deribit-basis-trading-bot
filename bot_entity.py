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
        'basis': 50,                
        "side_base": "buy",
        "side_second": "sell",
        "amount_base": 1,
        "amount_second": 1,
        "max_price_diff_up": 1.2,
        "max_price_diff_down": 5,
        "pair_base": "ETH-PERPETUAL",
        "pair_second": 'ETH-30JUL21',
        "name": name,
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