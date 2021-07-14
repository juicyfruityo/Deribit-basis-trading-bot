import telebot
import time
from threading import Thread
from telebot import types
import buy_sell_bot_v0
import json
from derebit_ws import *
import my_data
bot = telebot.TeleBot("1836894761:AAFx_ZoDxA59a63FTlpBGTbeHLYvexeBla8")
ws = DeribitWS(my_data.client_id, my_data.client_secret, test=True)
bots = {}

class BotEntity:
    
    def __init__(self, name, params=None):
        if params is None:
            params = {
        "side_base": "sell",
        "side_second": "buy",
        "amount_base": 50,
        "amount_second": 50,
        "max_price_diff_up": 1.2,
        "max_price_diff_down": 5
        }
        self.name = name
        self.params = params
        self.is_working = False
    
    def start():
        pass
    
    def stop():
        pass

    def info(self):
        return dict_to_str(self.params)

def dict_to_str(d):
    s = "\n"
    for key in d:
        s += f'{key}: {d[key]}\n'
    return s

@bot.message_handler(commands=['help'])
def send_welcome(message):
    bot.reply_to(message, 
    " \
    Данный телеграмм бот служит для управления basis_trading_bot, а так же логирования его работы. \
    Доступные команды: \n \
    /create_bot - команда для создания basis_trading_bot. В ходе ее выполнения нужно ввести название запускаемого бота, \
    биржу, используемые инструменты, параметры для входа в сделку. \n \
    /bot_info - команда для отслеживания состояния basis_trading_bot. В ходе ее выполнения нужно указать имя требуемого бота. \n\
    /change_parametrs - команда для смены параметров работающего бота. В ходе ее выполнения нужно указать имя требуемого бота. \n \
    /stop_bot - команда для завершения работы basis_trading_bot (Все открытые ордера будут отменены). В ходе ее выполнения нужно указать имя требуемого бота. \
    ")

@bot.message_handler(commands=['create_bot'])
def start_bot(message):
    msg = bot.reply_to(message, 'Введите название бота: ')
    bot.register_next_step_handler(msg, create_bot_name)

def create_bot_name(message):
    if message.text in bots:
        bot.reply_to(message, 'Данное имя уже использовано.')
    elif len(bots) >= 1:
        bot.reply_to(message, 'На данный момент поддерживается создание только одного бота.')
    else:
        basis_bot = BotEntity(message.text)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ["BTC", "ETH"]
        keyboard.add(*buttons)
        msg = bot.reply_to(message, 'Выберете монету.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, choose_coin, basis_bot)

def choose_coin(message, basis_bot):
    basis_bot.params["coin"] = message.text
    instruments = ws.available_instruments(basis_bot.params["coin"])
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*instruments)
    msg = bot.reply_to(message, "Выберете базовый интсрумент", reply_markup=keyboard)
    bot.register_next_step_handler(msg, choose_instrument, basis_bot, instruments)

def choose_instrument(message, basis_bot, instruments):
    basis_bot.params["pair_base"] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*instruments)
    msg = bot.reply_to(message, "Выберете второй интсрумент", reply_markup=keyboard)
    bot.register_next_step_handler(msg, change_parametrs, basis_bot)

def change_parametrs(message, basis_bot):
    basis_bot.params["pair_second"] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*basis_bot.params.keys(), "Завершить")
    msg = bot.reply_to(message, 
    f"Текущие параметры бота:{dict_to_str(basis_bot.params)} \
    Выберете параметр который хотите изменить", reply_markup=keyboard)
    bot.register_next_step_handler(msg,
    lambda m: bot.register_next_step_handler(m, register_msg, basis_bot, m.text))

def register_msg(message, basis_bot, key):
    if key == "Завершить":
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("Да", "Нет")
        msg = bot.reply_to(message, 
        f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Создать бота?", reply_markup=keyboard)
        bot.register_next_step_handler(msg, create_bot, basis_bot)
    else:
        if key in basis_bot.params: 
            basis_bot.params[key] = message.text
            change_parametrs(message, basis_bot)
        else:
            bot.repy_to(message, "Несуществующий параметр.")

def create_bot(message, basis_bot):
    if message.text == "Да":
        bots[basis_bot.name] = basis_bot
    if message.text == "Нет":
        bot.repy_to(message, "Бот не был создан.")


@bot.message_handler(commands=['bot_info'])
def bot_info(message):
    if len(bots) == 0:
        bot.reply_to(message, 'На данный момент нет ни одного созданного бота.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*bots.keys())
        msg = bot.reply_to(message, 'Выберете бота.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, print_bot_info)

def print_bot_info(message):
    if message.text in bots:
        msg = bot.reply_to(message, 
        f'Параметры бота.{dict_to_str(bots[message.text].params)}', reply_markup=types.ReplyKeyboardRemove())
    else:
        msg = bot.reply_to(message, 'Нет бота с данным именем', reply_markup=types.ReplyKeyboardRemove())
def main():
    t = Thread(target=bot.polling)
    try:
        t.start()
        while(t.is_alive):
            pass
    except KeyboardInterrupt:
        bot.stop_polling()
        t.join()

if __name__ == '__main__':
    main()