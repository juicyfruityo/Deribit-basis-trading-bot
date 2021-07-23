import telebot
import time
from threading import Thread
from telebot import types
from buy_sell_bot_v0 import *
import json
import helpers
from derebit_ws import *
import my_data
from bot_entity import *
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

tb = telebot.TeleBot("1918530464:AAGWaDRwJnkGKvbUZEXcCoSGBRFWFnbZhQs")
ws = DeribitWS(my_data.client_id, my_data.client_secret, test=True)
num_of_running_bots = 0
MAX_BOTS_RUNNING = 4
trustful_user_ids = [679868171, 337991363]
bots = {"Test": BotEntity("Test", params={
    "name": "Test",
    "coin": "BTC",
    "pair_base": 'BTC-PERPETUAL',
    "pair_second": 'BTC-24JUN22',
    "side_base": 'sell',
    "side_second": 'buy',
    'basis': 50,                
    "amount_base": 10,
    "amount_second": 10,
    "price_diff_up": 5,
    "price_diff_down": 2.4,
})}

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.bot = None
    
    def create_bot(self, name, params=None):
        self.bot = BotEntity(name, params)

users = {
    679868171: User(679868171),
    337991363: User(337991363),
    }

# Initial command processing
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
    if num_of_running_bots >= MAX_BOTS_RUNNING:
        tb.send_message(message.chat.id, f'The maximum number of bots launched cannot exceed {MAX_BOTS_RUNNING}.')
    else:
        choose_bot(message, "s_b", "ch_b")

@tb.message_handler(commands=['stop_bot'])
def stop_bot(message):
    choose_bot(message, None)

@tb.message_handler(commands=['change_parameters'])
def change_parameters(message):
    choose_bot(message, None)

@tb.message_handler(commands=['bot_info'])
def bot_info(message):
    choose_bot(message, None)

def choose_bot(message, sequence_name, current_method):
    if len(bots) == 0:
        tb.send_message(message.chat.id, 'There are no bots created.')
    else:
        buttons = {bot: bot for bot in bots}
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
            tb.send_message(message.chat.id, bot_params(user.bot.params, "Choose coin"), reply_markup=markup, parse_mode="MarkdownV2")
    elif prev_message == "change_parameter":
        bot = users[message.from_user.id].bot
        if data in {"basis", "amount_base", "amount_second", "price_diff_up", "price_diff_down"}:
            if message.text.isdigit():
                bot.params[data] = float(message.text)
            else:
                tb.answer_callback_query(call.id, f"This parametr has to be a number.")
        else:
            bot.params[data] = message.text
        tb.delete_message(message.chat.id, message.message_id)
        change_parameters(call, bot)

@tb.callback_query_handler(func=lambda call: call.data.find("cr_b") != -1)
def create_bot_callback_query(call):
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
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, "Choose base pair"),
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
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, "Choose second pair"),
        reply_markup=markup, parse_mode="MarkdownV2")
    except Exception as e:
        print(e)

def choosing_second_pair(call, bot):
    data = json.loads(call.data)
    message = call.message
    bot.params["pair_second"] = data["val"]
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
            tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, f'Are you sure you want to complete bot creation?'),
            reply_markup=markup, parse_mode="MarkdownV2")
    elif data["val"] == "side_base" or data["val"] == "side_second":
        buttons = {
            "sell": "sell",
            "buy": "buy",
        }
        current_method = "ch_s1" if data["val"] == "side_base" else "ch_s2" 
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method=current_method)
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, f'Please, choose new value of {data["val"]}'),
        reply_markup=markup, parse_mode="MarkdownV2")
    elif data["val"] == "q_cr":
        buttons = {
            "Yes": "Yes",
            "No": "No",
        }
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="quit")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, 'Are you sure you want to quit bot creation?'),
        reply_markup=markup, parse_mode="MarkdownV2")
    else:
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, f'Please, write new value of {data["val"]}'),
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
    bot.params["side_second"] = data["val"]
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
        buttons = {button: button for button in bot.params if button not in {"name", "coin", "pair_base", "pair_second"}}
        buttons["Complete bot creation"] = "comp_cr"
        buttons["Quit bot creation"] = "q_cr"
        markup = create_inline_markup(buttons, sequence_name="cr_b", current_method="ch_p")
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=bot_params(bot.params, "Edit other parameters"),
        reply_markup=markup, parse_mode="MarkdownV2")
    except Exception as e:
        print(e)

#_____________________________________________________________________________________________________________________

# Processing comand start_bot
#_____________________________________________________________________________________________________________________
@tb.callback_query_handler(func=lambda call: call.data.find("s_b") != -1)
def create_bot_callback_query(call):
    data = json.loads(call.data)
    callbacks = {
        "ch_b": choosing_bot,
    }
    callbacks[data["cur_m"]](call)

def choosing_bot(call):
    data = json.loads(call.data)
    bot_name = data["val"]
    if bot_name not in bots:
        tb.answer_callback_query(call.id, f"Can't start this bot.")
    else:
        bots[bot_name].start()
        tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Bot succesfuly started.")
#_____________________________________________________________________________________________________________________

def change(message):
    if message.text not in bots:
        tb.send_message(message.chat.id, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
    else:
        basis_bot = bots[message.text]
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*basis_bot.params.keys(), "Завершить")
        msg = tb.send_message(message.chat.id, 
        f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Выберите параметр который хотите изменить", reply_markup=keyboard)
        tb.register_next_step_handler(msg, register_parametr, basis_bot)

def stop(message):
    if message.text not in bots:
        tb.send_message(message.chat.id, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
    else:
        basis_bot = bots[message.text]
        basis_bot.stop()
        tb.send_message(message.chat.id, 'Бот остановлен.', reply_markup=types.ReplyKeyboardRemove())

# def start_trading_bot(basis_bot):
#     trading_bot = BasisTradingBot(basis_bot.params, ws, bot)
#     try:
#         trading_tb.make_trade()
#         tb.send_message(-561707350, 'Bot closed because trade done')
#     except KeyboardInterrupt:
#         trading_tb.close_bot()
#         tb.send_message(-561707350, 'Bot closed by KeyboardInterrupt')
#         sys.exit(0)

def start(message):
    if message.text not in bots:
        tb.send_message(message.chat.id, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
    else:
        basis_bot = bots[message.text]
        basis_bot.start()
        tb.send_message(message.chat.id, 'Бот запущен.', reply_markup=types.ReplyKeyboardRemove())

def create_bot_name(message):
    if message.text in bots:
        tb.send_message(message.chat.id, 'Данное имя уже использовано.')
    else:
        basis_bot = BotEntity(message.text)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ["BTC", "ETH"]
        keyboard.add(*buttons)
        msg = tb.send_message(message.chat.id, 'Выберите монету.', reply_markup=keyboard)
        tb.register_next_step_handler(msg, choose_coin, basis_bot)

def choose_coin(message, basis_bot):
    basis_bot.params["coin"] = message.text
    instruments = ws.available_instruments(basis_bot.params["coin"])
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*instruments)
    msg = tb.send_message(message.chat.id, "Выберите базовый интсрумент", reply_markup=keyboard)
    tb.register_next_step_handler(msg, choose_instrument, basis_bot, instruments)

def choose_instrument(message, basis_bot, instruments):
    basis_bot.params["pair_base"] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*instruments)
    msg = tb.send_message(message.chat.id, "Выберите второй интсрумент", reply_markup=keyboard)
    tb.register_next_step_handler(msg, change_parametrs, basis_bot)

def choose_second_instrument(message, basis_bot):
    basis_bot.params["pair_second"] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*basis_bot.params.keys(), "Завершить")
    msg = tb.send_message(message.chat.id, 
    f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Выберите параметр который хотите изменить", reply_markup=keyboard)
    tb.register_next_step_handler(msg, register_parametr, basis_bot)

def change_parametrs(message, basis_bot):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*basis_bot.params.keys(), "Завершить")
    msg = tb.send_message(message.chat.id, 
    f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Выберите параметр который хотите изменить", reply_markup=keyboard)
    tb.register_next_step_handler(msg, register_parametr, basis_bot)

def register_parametr(message, basis_bot):
    if message.text != "Завершить":
        tb.register_next_step_handler(message, register_msg, basis_bot, message.text)
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("Да", "Нет")
        msg = tb.send_message(message.chat.id, 
        f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Завершить настройку параметров?", reply_markup=keyboard)
        tb.register_next_step_handler(msg, create_bot, basis_bot)

def register_msg(message, basis_bot, key):
    if key in basis_bot.params: 
        basis_bot.params[key] = message.text
        change_parametrs(message, basis_bot)
    else:
        tb.repy_to(message, "Несуществующий параметр.")

def create_bot(message, basis_bot):
    if message.text == "Да":
        bots[basis_bot.name] = basis_bot
        tb.send_message(message.chat.id, "Параметры успешно сохранены.", reply_markup=types.ReplyKeyboardRemove())
    if message.text == "Нет":
        tb.repy_to(message, "Создание/изменение бота отменено.", reply_markup=types.ReplyKeyboardRemove())




def print_bot_info(message):
    if message.text in bots:
        msg = tb.send_message(message.chat.id, 
        f'Параметры бота.{dict_to_str(bots[message.text].params)}', reply_markup=types.ReplyKeyboardRemove())
    else:
        msg = tb.send_message(message.chat.id, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())


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