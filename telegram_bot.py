import telebot
import time
from threading import Thread
from telebot import types
from buy_sell_bot_v0 import *
import json
from derebit_ws import *
import my_data
bot = telebot.TeleBot("1836894761:AAFx_ZoDxA59a63FTlpBGTbeHLYvexeBla8")
ws = DeribitWS(my_data.client_id, my_data.client_secret, test=True)
num_of_running_bots = 0
MAX_BOTS_RUNNING = 1

class BotEntity:
    
    def __init__(self, name, params=None):
        if params is None:
            params = {
        'basis': 50,                
        "side_base": "sell",
        "side_second": "buy",
        "amount_base": 10,
        "amount_second": 10,
        "max_price_diff_up": 1.2,
        "max_price_diff_down": 5,
        "pair_base": "BTC-PERPETUAL",
        "pair_second": 'BTC-24JUN22',
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
                bot.send_message(-561707350, 'Bot closed through tg')
            num_of_running_bots -= 1
            trading_bot.close_bot()
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

bots = {"Test": BotEntity("Test")}

def dict_to_str(d):
    s = "\n"
    for key in d:
        s += f'{key}: {d[key]}\n'
    return s

@bot.message_handler(commands=['help'])
def send_welcome(message):
    bot.reply_to(message, 
    " \
    Данный телеграмм бот служит для управления basis_trading_bot, а так же логирования его работы.\
    Доступные команды: \n \
    /create_bot - команда для создания basis_trading_bot. В ходе ее выполнения нужно ввести название запускаемого бота, \
    биржу, используемые инструменты, параметры для входа в сделку. \n \
    /bot_info - команда для отслеживания состояния basis_trading_bot. В ходе ее выполнения нужно указать имя требуемого бота. \n\
    /change_parametrs - команда для смены параметров работающего бота. В ходе ее выполнения нужно указать имя требуемого бота. \n \
    /start_bot - Запускает созданного бота.\
    /stop_bot - команда для завершения работы basis_trading_bot (Все открытые ордера будут отменены). В ходе ее выполнения нужно указать имя требуемого бота. \
    ")


@bot.message_handler(commands=['clear'])
def clear(message):
    msg = bot.reply_to(message, 'Кнопки убраны', reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['create_bot'])
def start_bot(message):
    msg = bot.reply_to(message, 'Введите название бота: ')
    bot.register_next_step_handler(msg, create_bot_name)

@bot.message_handler(commands=['start_bot'])
def start_bot(message):
    if len(bots) == 0:
        bot.reply_to(message, 'На данный момент нет ни одного созданного бота.')
    elif num_of_running_bots >= MAX_BOTS_RUNNING:
        bot.reply_to(message, f'Максимальное количество запущенных ботов не может прервышать {MAX_BOTS_RUNNING}.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*bots.keys())
        msg = bot.reply_to(message, 'Выберите бота.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, start)

@bot.message_handler(commands=['stop_bot'])
def stop_bot(message):
    if len(bots) == 0:
        bot.reply_to(message, 'На данный момент нет ни одного созданного бота.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*bots.keys())
        msg = bot.reply_to(message, 'Выберите бота.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, stop)

@bot.message_handler(commands=['change_parametrs'])
def change_params(message):
    if len(bots) == 0:
        bot.reply_to(message, 'На данный момент нет ни одного созданного бота.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*bots.keys())
        msg = bot.reply_to(message, 'Выберите бота.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, change)

def change(message):
    if message.text not in bots:
        bot.reply_to(message, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
    else:
        basis_bot = bots[message.text]
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*basis_bot.params.keys(), "Завершить")
        msg = bot.reply_to(message, 
        f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Выберите параметр который хотите изменить", reply_markup=keyboard)
        bot.register_next_step_handler(msg, register_parametr, basis_bot)

def stop(message):
    if message.text not in bots:
        bot.reply_to(message, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
    else:
        basis_bot = bots[message.text]
        basis_bot.stop()
        bot.reply_to(message, 'Бот остановлен.', reply_markup=types.ReplyKeyboardRemove())

def start_trading_bot(basis_bot):
    trading_bot = BasisTradingBot(basis_bot.params, ws, bot)
    try:
        trading_bot.make_trade()
        bot.send_message(-561707350, 'Bot closed because trade done')
    except KeyboardInterrupt:
        trading_bot.close_bot()
        bot.send_message(-561707350, 'Bot closed by KeyboardInterrupt')
        sys.exit(0)

def start(message):
    if message.text not in bots:
        bot.reply_to(message, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
    else:
        basis_bot = bots[message.text]
        basis_bot.start()
        bot.reply_to(message, 'Бот запущен.', reply_markup=types.ReplyKeyboardRemove())

def create_bot_name(message):
    if message.text in bots:
        bot.reply_to(message, 'Данное имя уже использовано.')
    else:
        basis_bot = BotEntity(message.text)
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = ["BTC", "ETH"]
        keyboard.add(*buttons)
        msg = bot.reply_to(message, 'Выберите монету.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, choose_coin, basis_bot)

def choose_coin(message, basis_bot):
    basis_bot.params["coin"] = message.text
    instruments = ws.available_instruments(basis_bot.params["coin"])
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*instruments)
    msg = bot.reply_to(message, "Выберите базовый интсрумент", reply_markup=keyboard)
    bot.register_next_step_handler(msg, choose_instrument, basis_bot, instruments)

def choose_instrument(message, basis_bot, instruments):
    basis_bot.params["pair_base"] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*instruments)
    msg = bot.reply_to(message, "Выберите второй интсрумент", reply_markup=keyboard)
    bot.register_next_step_handler(msg, change_parametrs, basis_bot)

def choose_second_instrument(message, basis_bot):
    basis_bot.params["pair_second"] = message.text
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*basis_bot.params.keys(), "Завершить")
    msg = bot.reply_to(message, 
    f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Выберите параметр который хотите изменить", reply_markup=keyboard)
    bot.register_next_step_handler(msg, register_parametr, basis_bot)

def change_parametrs(message, basis_bot):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*basis_bot.params.keys(), "Завершить")
    msg = bot.reply_to(message, 
    f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Выберите параметр который хотите изменить", reply_markup=keyboard)
    bot.register_next_step_handler(msg, register_parametr, basis_bot)

def register_parametr(message, basis_bot):
    if message.text != "Завершить":
        bot.register_next_step_handler(message, register_msg, basis_bot, message.text)
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add("Да", "Нет")
        msg = bot.reply_to(message, 
        f"Текущие параметры бота:{dict_to_str(basis_bot.params)}Завершить настройку параметров?", reply_markup=keyboard)
        bot.register_next_step_handler(msg, create_bot, basis_bot)

def register_msg(message, basis_bot, key):
    if key in basis_bot.params: 
        basis_bot.params[key] = message.text
        change_parametrs(message, basis_bot)
    else:
        bot.repy_to(message, "Несуществующий параметр.")

def create_bot(message, basis_bot):
    if message.text == "Да":
        bots[basis_bot.name] = basis_bot
        bot.reply_to(message, "Параметры успешно сохранены.", reply_markup=types.ReplyKeyboardRemove())
    if message.text == "Нет":
        bot.repy_to(message, "Создание/изменение бота отменено.", reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=['bot_info'])
def bot_info(message):
    if len(bots) == 0:
        bot.reply_to(message, 'На данный момент нет ни одного созданного бота.')
    else:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*bots.keys())
        msg = bot.reply_to(message, 'Выберите бота.', reply_markup=keyboard)
        bot.register_next_step_handler(msg, print_bot_info)

def print_bot_info(message):
    if message.text in bots:
        msg = bot.reply_to(message, 
        f'Параметры бота.{dict_to_str(bots[message.text].params)}', reply_markup=types.ReplyKeyboardRemove())
    else:
        msg = bot.reply_to(message, 'Нет бота с данным именем.', reply_markup=types.ReplyKeyboardRemove())
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