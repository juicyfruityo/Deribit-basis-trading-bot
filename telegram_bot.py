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

bots = {"Test": BotEntity("Test")}

# Command processing
#_____________________________________________________________________________________________________________________

@tb.message_handler(commands=['help'])
def help_info(message):
    print(dir(message))
    tb.send_message(message.chat.id, 
"This bot was created for managing basis_trading_tb. It allows you to create bots with different parameters and run them. For now all logging happens in fixed chat.\n\
To see more information about commands type slash on your keyboard.")

@tb.message_handler(commands=['create_bot'])
def create_bot(message):
    bot_message = tb.send_message(message.chat.id, 'Enter the name of bot: ', reply_markup=types.ReplyKeyboardRemove())
    tb.register_next_step_handler(bot_message, handle_create_bot_message_sequence, message)

@tb.message_handler(commands=['start_bot'])
def start_bot(message):
    if num_of_running_bots >= MAX_BOTS_RUNNING:
        tb.send_message(message.chat.id, f'The maximum number of bots launched cannot exceed {MAX_BOTS_RUNNING}.')
    else:
        choose_bot(message, handle_start_bot_message_sequence)

@tb.message_handler(commands=['stop_bot'])
def stop_bot(message):
    choose_bot(message, None)

@tb.message_handler(commands=['change_parameters'])
def change_parameters(message):
    choose_bot(message, None)

@tb.message_handler(commands=['bot_info'])
def bot_info(message):
    choose_bot(message, None)

def choose_bot(message, handler):
    if len(bots) == 0:
        tb.send_message(message.chat.id, 'There are no bots created.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*bots.keys())
        bot_message = tb.send_message(message.chat.id, 'Choose bot', reply_markup=keyboard)
        tb.register_next_step_handler(bot_message, handler)
#_____________________________________________________________________________________________________________________

# Handlers for commands
#_____________________________________________________________________________________________________________________

# Takes dict {button: callback_data} and return InlineKeyboardMarkup
def create_inline_markup(buttons):
    markup = InlineKeyboardMarkup()
    for button, callback in buttons.items():
        markup.add(InlineKeyboardButton(button, callback_data=callback))
    return markup

def handle_create_bot_message_sequence(message, prev_message):
    if prev_message.text == "/create_bot":
        if message.text in bots:
            tb.send_message(message.chat.id, 'Given name is already using.')
        else:
            basis_bot = BotEntity(message.text)
            markup = create_inline_markup({
                "BTC": "coin_choosed_BTC",
                "ETH": "coin_choosed_ETH",
            })
            msg = tb.send_message(message.chat.id, 'Выберите монету.', reply_markup=markup)
            # tb.register_next_step_handler(msg, choose_coin, basis_bot)

@tb.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data.startswith("coin_choosed"):
        try:    
            instruments = ws.available_instruments(call.data[-3:])
            buttons = {button: f"first_insrument_choosed:{button}" for button in instruments}
            markup = create_inline_markup(buttons)
            tb.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text = "Greate choose instrument",
            reply_markup=markup)
        except Exception as e:
            print(e)

def handle_start_bot_message_sequence(message, prev_message):
    pass

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