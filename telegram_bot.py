# create_bot - create BasisTradingBot with parameters
# bot_info - look at bot's parameters
# change_parameters - change parameters of existing bot
# start_bot - start already created BasisTradingBot
# stop_bot - stop running BasisTradingBot
# running_bot - list all running bots

import telebot
import time
from threading import Thread
from telebot import types
from buy_sell_bot_v0 import *
import json
import helpers
from derebit_ws import *
from buy_sell_bot_v0 import *
import my_data
from pool import *
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot import apihelper

# This initialization are global due to telebot lib.
# Practically every structure (telegram bot, pool of workers, users data, bots data) initialized here
#_____________________________________________________________________________________________________________________
tb = telebot.TeleBot("1918530464:AAGWaDRwJnkGKvbUZEXcCoSGBRFWFnbZhQs")
apihelper.SESSION_TIME_TO_LIVE = 5 * 60 # Force recreation after 5 minutes without any activity. So to avoid ConnectionResetErrors

ws = DeribitWS(my_data.client_id, my_data.client_secret, test=True)
pool = Pool()
trustful_user_ids = [679868171, 337991363]
bots = {
    "Test1": BasisTradingBot("Test1", 
    params={
    "name": "Test1",
    "coin": "BTC",
    "pair_base": 'BTC-PERPETUAL',
    "pair_other": 'BTC-24JUN22',
    "side_base": 'sell',
    "side_other": 'buy',
    'basis': -50.,                
    "amount_base": 10.,
    "amount_other": 10.,
    "diff_up": 5.,
    "diff_down": 2.4,
    }),
    "Test2": BasisTradingBot("Test2", 
    params={
    "name": "Test2",
    "coin": "BTC",
    "pair_base": 'BTC-PERPETUAL',
    "pair_other": 'BTC-24JUN22',
    "side_base": 'sell',
    "side_other": 'buy',
    'basis': 50.,                
    "amount_base": 10.,
    "amount_other": 10.,
    "diff_up": 5.,
    "diff_down": 2.4,
    })
}

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.bot = None
    
    def create_bot(self, name, params=None):
        self.bot = BasisTradingBot(name, params)

users = {
    679868171: User(679868171),
    337991363: User(337991363),
    }
#_____________________________________________________________________________________________________________________

# Initial commands processing
#_____________________________________________________________________________________________________________________

@tb.message_handler(commands=['start'])
def help_info(message):
    if message.from_user.id not in trustful_user_ids:
        tb.send_message(message.chat.id, f"Sorry, you can't use this bot. For more information you can pm @lomonoshka.")    
    elif message.from_user.id not in users:
        users[message.from_user.id] = User(message.from_user.id)
        tb.send_message(message.chat.id, f"Hey, you can fully use this bot! For more info please type /help.")
    else:
        tb.send_message(message.chat.id, f"You are already autherized, you can fully use this bot!")

@tb.message_handler(commands=['help'])
def help_info(message):
    tb.send_message(message.chat.id, 
"This bot was created for managing basis_trading_bot. It allows you to create bots with different parameters and run them. For now all logging happens in fixed chat.\n\
To see more information about commands type slash on your keyboard.")

@tb.message_handler(commands=['create_bot'])
def create_bot(message):
    bot_message = tb.send_message(message.chat.id, 'Enter the name of bot: ', reply_markup=types.ReplyKeyboardRemove())
    tb.register_next_step_handler(bot_message, handle_create_bot_message_sequence, message.text)

@tb.message_handler(commands=['start_bot'])
def start_bot(message):
    if len(pool.workers) >= pool.max_number_of_workers:
        tb.send_message(message.chat.id, f'The maximum number of bots launched cannot exceed {pool.max_number_of_workers}.')
    else:
        choose_bot(message, sequence_name="s_b", current_method="ch_b", state="idle")

@tb.message_handler(commands=['stop_bot'])
def stop_bot(message):
    choose_bot(message, sequence_name="st_b", current_method="ch_b", state="run")

@tb.message_handler(commands=['change_parameters'])
def change_parameters(message):
    choose_bot(message, sequence_name="ch_p", current_method="ch_b", state="idle")

@tb.message_handler(commands=['bot_info'])
def bot_info(message):
    choose_bot(message, sequence_name="b_i", current_method="ch_b")

@tb.message_handler(commands=['running_bots'])
def running_bots(message):
    if len(pool.workers) == 0:
        tb.send_message(message.chat.id, "There are not bots running.")
    else:    
        message_text = ""
        for bot_name in pool.workers:
            message_text += f"{bot_name}\n"
        tb.send_message(message.chat.id, message_text)


# state (run, idle, all)
def choose_bot(message, sequence_name, current_method, state="all"):
    conditions = {
        "all": lambda bot: True,
        "idle": lambda bot: not bot.is_running,
        "run": lambda bot: bot.is_running,
    }
    bot_names = [bot.name for bot in bots.values() if conditions[state](bot)]
    if len(bot_names) == 0:
        tb.send_message(message.chat.id, 'There are no bots available.')
    else:
        buttons = {bot: bot for bot in bot_names}
        markup = create_inline_markup(buttons, sequence_name, current_method)
        tb.send_message(message.chat.id, "Choose bot", reply_markup=markup, parse_mode="MarkdownV2")

#_____________________________________________________________________________________________________________________

# create_bot command processing
#_____________________________________________________________________________________________________________________

# Takes dict {button: callback_data}, current command and return InlineKeyboardMarkup where callback data is json
def create_inline_markup(buttons, sequence_name, current_method, row_width = 2):
    markup = InlineKeyboardMarkup()
    markup.row_width = row_width
    items = list(buttons.items())
    for i in range(0, len(buttons), row_width):
        bs = []
        for button, value in items[i: i + row_width]:
            callback_dict = {
                "val": value,
                "cur_m": current_method,
                "seq_n": sequence_name,
                }
            # print(json.dumps(callback_dict).encode('utf-8'))
            # print(len(json.dumps(callback_dict).encode('utf-8')))
            bs.append(InlineKeyboardButton(button, callback_data=json.dumps(callback_dict)))
        markup.add(*bs)
    return markup

def handle_create_bot_message_sequence(message, prev_message, data=None, call = None):
    if prev_message == "/create_bot":
        if message.text in bots:
            bot_message = tb.send_message(message.chat.id, 'Given name is already using.')
            tb.register_next_step_handler(bot_message, handle_create_bot_message_sequence, "/create_bot")
        else:
            user = users[message.from_user.id]
            user.create_bot(message.text)
            markup = create_inline_markup({
                "BTC": "BTC",
                "ETH": "ETH",
            }, sequence_name="cr_b", current_method="ch_c")
            tb.send_message(message.chat.id, get_parameters_table(user.bot.params, "Choose coin"), reply_markup=markup, parse_mode="MarkdownV2")
    elif prev_message == "change_parameter":
        bot = users[message.from_user.id].bot
        if data in {"basis", "amount_base", "amount_other", "diff_up", "diff_down"}:
            if message.text.isdigit():
                bot.params[data] = float(message.text)
            else:
                tb.answer_callback_query(call.id, f"This parameter has to be a number.")
        else:
            bot.params[data] = message.text
        tb.delete_message(message.chat.id, message.message_id)
        change_parameters(call, bot)

@tb.callback_query_handler(func=lambda call: call.data.find('"seq_n": "cr_b"') != -1)
def create_bot_callback_query(call):
    print(call.data)
    data = json.loads(call.data)
    bot = users[call.from_user.id].bot
    callbacks = {
        "ch_c": choosing_coin,
        "ch_i1": choosing_base_pair,
        "ch_i2": choosing_second_pair,
        "ch_p": choosing_parameters,
        "ch_s1": choose_base_side,
        "ch_s2": choose_second_side,
        "end": complete_creation,
        "quit": abort_creation,
    }
    callbacks[data["cur_m"]](call, bot)


def choosing_coin(call, bot):
    data = json.loads(call.data)
    message = call.message
    bot.params["coin"] = data["val"]
    try:    
        instruments = ws.available_instruments(bot.params["coin"])
        buttons = {button: button for button in instruments}
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="ch_i1")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, "Choose base pair"),
        reply_markup=markup, parse_mode="MarkdownV2")
    except Exception as e:
        print(e)

def choosing_base_pair(call, bot):
    data = json.loads(call.data)
    message = call.message
    bot.params["pair_base"] = data["val"]
    try:    
        instruments = ws.available_instruments(bot.params["coin"])
        buttons = {button: button for button in instruments if button != bot.params["pair_base"]}
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="ch_i2")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, "Choose second pair"),
        reply_markup=markup, parse_mode="MarkdownV2")
    except Exception as e:
        print(e)

def choosing_second_pair(call, bot):
    data = json.loads(call.data)
    message = call.message
    bot.params["pair_other"] = data["val"]
    change_parameters(call, bot)

def choosing_parameters(call, bot):
    data = json.loads(call.data)
    message = call.message
    if data["val"] == "comp_cr":
        if None in bot.params.values():
            tb.answer_callback_query(call.id, f"Not all parameters changed.")
        else:
            buttons = {
                "Yes": "Yes",
                "No": "No",
            }
            markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="end")
            tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, f'Are you sure you want to complete bot creation?'),
            reply_markup=markup, parse_mode="MarkdownV2")
    elif data["val"] == "side_base" or data["val"] == "side_other":
        buttons = {
            "sell": "sell",
            "buy": "buy",
        }
        current_method = "ch_s1" if data["val"] == "side_base" else "ch_s2" 
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method=current_method)
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, f'Please, choose new value of {data["val"]}'),
        reply_markup=markup, parse_mode="MarkdownV2")
    elif data["val"] == "q_cr":
        buttons = {
            "Yes": "Yes",
            "No": "No",
        }
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="quit")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, 'Are you sure you want to quit bot creation?'),
        reply_markup=markup, parse_mode="MarkdownV2")
    else:
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, f'Please, write new value of {data["val"]}'),
        reply_markup=None, parse_mode="MarkdownV2")
        tb.register_next_step_handler(call.message, handle_create_bot_message_sequence, "change_parameter", data["val"], call)

def choose_base_side(call, bot):
    data = json.loads(call.data)
    message = call.message
    bot.params["side_base"] = data["val"]
    change_parameters(call, bot)

def choose_second_side(call, bot):
    data = json.loads(call.data)
    message = call.message
    bot.params["side_other"] = data["val"]
    change_parameters(call, bot)

def complete_creation(call, bot):
    data = json.loads(call.data)
    message = call.message
    if data["val"] == "Yes":
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Bot succesfuly created.")
        bots[bot.name] = bot
    else:
        change_parameters(call, bot)

def abort_creation(call, bot):
    data = json.loads(call.data)
    message = call.message
    if data["val"] == "Yes":
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text='Bot creation aborted.')
    else:
        change_parameters(call, bot)

def change_parameters(call, bot):
    try:    
        buttons = {button: button for button in bot.params if button not in {"name", "coin", "pair_base", "pair_other"}}
        buttons["Complete bot creation"] = "comp_cr"
        buttons["Quit bot creation"] = "q_cr"
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="ch_p")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bot.params, "Edit other parameters"),
        reply_markup=markup, parse_mode="MarkdownV2")
    except Exception as e:
        print(e)

#_____________________________________________________________________________________________________________________

# Processing comand /start_bot
#_____________________________________________________________________________________________________________________
@tb.callback_query_handler(func=lambda call: call.data.find('"seq_n": "s_b"') != -1)
def create_bot_callback_query(call):
    data = json.loads(call.data)
    callbacks = {
        "ch_b": choosing_bot_start_bot,
    }
    callbacks[data["cur_m"]](call)

def choosing_bot_start_bot(call):
    data = json.loads(call.data)
    bot_name = data["val"]
    if bot_name not in bots:
        tb.answer_callback_query(call.id, f"Can't start this bot.")
    else:
        pool.start_worker(bots[bot_name])
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Bot succesfuly started.")
#_____________________________________________________________________________________________________________________

# Processing comand /start_bot
#_____________________________________________________________________________________________________________________
@tb.callback_query_handler(func=lambda call: call.data.find('"seq_n": "st_b"') != -1)
def create_bot_callback_query(call):
    data = json.loads(call.data)
    callbacks = {
        "ch_b": choosing_bot_stop_bot,
    }
    callbacks[data["cur_m"]](call)

def choosing_bot_stop_bot(call):
    data = json.loads(call.data)
    bot_name = data["val"]
    if bot_name not in bots:
        tb.answer_callback_query(call.id, f"Can't start this bot.")
    else:
        pool.terminate_worker(bots[bot_name])
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Bot succesfuly closed.")
#_____________________________________________________________________________________________________________________

# Processing comand /bot_info
#_____________________________________________________________________________________________________________________
@tb.callback_query_handler(func=lambda call: call.data.find('"seq_n": "b_i"') != -1)
def create_bot_callback_query(call):
    data = json.loads(call.data)
    callbacks = {
        "ch_b": choosing_bot_bot_info,
        "b_p": looking_bot_params,
    }
    callbacks[data["cur_m"]](call)

def choosing_bot_bot_info(call):
    data = json.loads(call.data)
    bot_name = data["val"]
    if bot_name not in bots:
        tb.answer_callback_query(call.id, f"Can't find this bot.")
    else:
        buttons = {
            "Back to bots": "rt"
        }
        print("keks")
        markup = create_inline_markup(buttons, "b_i", "b_p")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=get_parameters_table(bots[bot_name].params, ""),
        reply_markup=markup, parse_mode="MarkdownV2")

def looking_bot_params(call):
    buttons = {bot: bot for bot in bots}
    markup = create_inline_markup(buttons, sequence_name="b_i", current_method="ch_b")
    tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Choose bot",
    reply_markup=markup, parse_mode="MarkdownV2")

#_____________________________________________________________________________________________________________________

# Processing comand /change_parameters
#_____________________________________________________________________________________________________________________
@tb.callback_query_handler(func=lambda call: call.data.find('"seq_n": "ch_p"') != -1)
def create_bot_callback_query(call):
    data = json.loads(call.data)
    callbacks = {
        "ch_b": choosing_bot_change_params,
    }
    callbacks[data["cur_m"]](call)

def choosing_bot_change_params(call):
    data = json.loads(call.data)
    bot_name = data["val"]
    if bot_name not in bots:
        tb.answer_callback_query(call.id, f"Can't find this bot.")
    else:
        users[call.from_user.id].bot = bots[bot_name] 
        change_parameters(call, bots[bot_name])

#_____________________________________________________________________________________________________________________


def main():
    # tb.polling(none_stop=True, interval=1, timeout=100)
    while True:
        try:
            tb.polling(none_stop=True, interval=1, timeout=100)
        except KeyboardInterrupt:
            # Требуется два раза подряд нажать CTRL-C
            tb.stop_bot()
            print('Telegram Bot Closed')
            break
        except Exception as e:
            print(f'New Exception Raised:   {e}')
            time.sleep(15)

if __name__ == '__main__':
    main()