import asyncio
from requests.api import get
import websockets
import json

import time
import logging
import sys
import signal

from helpers import *
import my_data
from derebit_ws import DeribitWS

class GracefulKiller:
  kill_now = False
  def __init__(self):
    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)

  def exit_gracefully(self, *args):
    self.kill_now = True


class BasisTradingBot:
    '''
    Идея бота в том чтобы торговать относительно basisа,
    т.е. например купить и продать два фьючерса с одним
    и тем же базовым активом, но разной датой экспирации.
    Например купить ETH-PERPETUAL (long),
    одновременно с этим продав ETH-7MAY21 (short), так чтобы
    между ними была разница 20долларов, а потом сделать обратную сделку,
    когда разница между ними станет 5 долларов. Таким образом
    маржа будет 15 долларов.

    Пока предназначен одновременно только для двух пар.

    '''
    # TODO: 1) обработка ошибок
    # 2) обработка случая если ордер при карытии уже исполнился, 
    # 3) обработка случая, когда ордер исполнился частично,
    # 4) сделать ассинхроннное выполнение запросов, посмотреть
    # возмодные точки оптимизации
    # 5) добавить логирование в телеграм бота
    # 6) добавить отчёт о совершённых сделках
    # 7) надо придумать как борорться с проскальзыванием между проверками.
    # 8) надо аккуратно заканчивать работу программы, т.к. сейчас она обрывается посреди действия.
    
    def __init__(self, name, params=None):
        if params is None:
            params = {
        "name": name,
        "coin": None,
        "pair_base": None,
        "pair_other": None,
        "side_base": None,
        "side_other": None,
        'basis': None,                
        "amount_base": None,
        "amount_other": None,
        "diff_up": None,
        "diff_down": None,
        }
        self.name = name
        self.params = params
        self.is_running = False

        self.ws = DeribitWS(my_data.client_id, my_data.client_secret, test=True)
        self.current_orders = {}  # {pair: [order_info]}
        self.current_positions = {}  # {pair: [positions]}

        self.time_iter = 0
        # self.tg_bot = tg_bot
        self.log_to_tg = True

        logging.basicConfig(level=logging.INFO, filename='application_' + params['name'],
                            format='%(asctime)s  %(levelname)s:  %(message)s' )
        self.log = logging.getLogger(__name__)


    def logging_bot(self, msg, log_to_tg=False, markdown=False):
        if msg == "":
            return
        self.log.info(msg)
        if log_to_tg:
            tg_logging(msg, markdown)

    def put_order(self):
        # TODO: сделать обработку ошибок,
        # добавлять открытые ордера в список.
        # ? сделать структуру для ордеров

        self.logging_bot('In put_order')

        bid_base, ask_base, err = self.ws.get_bid_ask(self.params['pair_base'])
        # self.logging_bot(f'End get bid ask prices for base, err = {err}')
        # bid_second, ask_second, err = self.ws.get_bid_ask(self.params['pair_other'])
        self.logging_bot(f'End get bid ask prices for second, err = {err}')
        

        amount = self.params['amount_other']
        pair = self.params['pair_other']

        side = self.params['side_other']
        basis = self.params['basis']
        # min_price_step = 0.05
        # Т.к. я делаю post_only заявку, то можно указать любую цену, она попадёт в стакан.
        if side == 'buy':
            order_price = bid_base + basis
            self.logging_bot(f'Set limit order: pair={pair}, side={side}, price={order_price}, amount={amount}; pair_base={self.params["pair_base"]}: price={bid_base}')
        elif side == 'sell':
            order_price = ask_base + basis
            self.logging_bot(f'Set limit order: pair={pair}, side={side}, price={order_price}, amount={amount}; pair_base={self.params["pair_base"]}: price={ask_base}')

        post_only = True
        reduce_only = False
        response, err = self.ws.limit_order(pair, amount, side, order_price, post_only, reduce_only)
        # print(response)
        self.logging_bot(f'Make order, err={err}')
        print(response)
        order_id = response['result']['order']['order_id']
        order_price = response['result']['order']['price']
        order_info = {
            "order_id": order_id, "order_price": order_price, "filled_amount": 0.
        }
        self.current_orders[pair] = order_info

        return err

    def market_base(self, amount):
        self.logging_bot('Start making market order')

        pair_base = self.params['pair_base']
        # amount = self.params['amount_base']
        side = self.params['side_base']

        response, err = self.ws.market_order(pair_base, amount, side)
        self.logging_bot(f'End making market order, err={err} \n\t\t\t\t\t\t\t\t Trade DONE amount {amount} out of {self.params["amount_base"]}')
        
        pair_other = self.params['pair_other']
        order_price = self.current_orders[pair_other]['order_price']
        price_base = response['result']['order']['average_price']
        side_other = self.params['side_other']

        self.logging_bot(f'Trade done amount {amount} out of {self.params["amount_base"]}', True)
        self.logging_bot(f'basis={round(order_price - price_base, 2)}; {side} {pair_base}: price={price_base}; {side_other} {pair_other}: price={order_price};', True)

        # Т.к. по сути ордер один, то можно закрывать бота.
        print(f'Trade done amount {amount} out of {self.params["amount_base"]}')
        print(f'basis={round(order_price - price_base, 2)}; {side} {pair_base}: price={price_base}; {side_other} {pair_other}: price={order_price};')
        
        # Если исполнился частично, надо продолжить работу бота.
        if amount < self.params['amount_base']:
            self.params['amount_base'] -= amount
            self.params['amount_other'] -= amount
            return False, err
        return True, err  # Работа бота завершена.

    def cancel_order(self, order_info):
        self.logging_bot('In cancel_order')
        order_id, amount_done = order_info['order_id'], order_info['filled_amount']
        response, err = self.ws.cancel_order(order_id)

        self.logging_bot(f'End cancelling order, err = {err}')

        # Знчит ордер сполнился полностью.
        if err == 'error':
            self.logging_bot('In cancel_order order fully filled')

            is_trade, err = self.market_base(self.params['amount_base'])
            return is_trade, err
        try:
            # Значит ордер частично исполнился.
            pair_other = self.params['pair_other']
            filled_amount = response['result']['filled_amount']
            if filled_amount > 0:

                self.logging_bot(f'In cancel_order order filled_amount={filled_amount}')
                self.logging_bot(response['result'])

                if self.current_orders[pair_other]['filled_amount'] < filled_amount:
                    amount = filled_amount - self.current_orders[pair_other]['filled_amount']
                    self.current_orders[pair_other]['filled_amount'] = filled_amount
                    is_trade, err = self.market_base(amount)
                    return is_trade, err
        except:
            print(response)
        return False, err

    def check_order(self):
        '''
        Если ордер выполнился, то требуется сделать симметричную
        сделку на основной паре. Закончить программу.
        Если цена на основной фьючерс изменилась достаточно
        сильно, то требуется закрыть отрытый ордер и открыть новый.
        
        
        '''
        # TODO: надо добавить асинхронное выполнение запроса цены и запроса инфы об ордере.
        self.logging_bot('In check_order')

        pair_base = self.params['pair_base']
        pair_other = self.params['pair_other']
        amount = self.params['amount_base']
        side = self.params['side_base']

        order_info = self.current_orders[pair_other]
        order_id, amount_done = order_info['order_id'], order_info['filled_amount']
        order_price = order_info['order_price']

        # Проверяем ордер.
        res_order_state, base_bid_ask, second_bid_ask = self.ws.execute_funcs(
            self.ws.get_order_state_async(order_id),
            self.ws.get_bid_ask_async(self.params['pair_base']),
            self.ws.get_bid_ask_async(self.params['pair_other'])
        )
        response, err_order_state = res_order_state
        bid_base, ask_base, err_base = base_bid_ask
        bid_second, ask_second, err_second = second_bid_ask
        err = err_base

        self.logging_bot('Start check order state')
        # response, err = self.ws.get_order_state_async(order_id)
        self.logging_bot(f'End check order state of order={order_id}, err = {err_order_state}')
        self.logging_bot(f'End get bid ask prices for base, err = {err_base}')
        self.logging_bot(f'End get bid ask prices for second, err = {err_second}')

        price_base = bid_base if side == 'sell' else ask_base
        # price_second = bid_second if side == 'buy' else ask_second
        price_second = bid_second if side == 'sell' else ask_second
        self.logging_bot(f'====  Current basis = {round(price_second - price_base, 2)}' \
            + f', base price={price_base}, order price={order_price}, diff={round(order_price - price_base, 2)}  =====')
        
        # Логгирование в Телеграм каждые 1000 итераций ~ 400сек
        self.time_iter += 1
        if self.time_iter == 1000:
            self.time_iter = 0
            self.logging_bot(f'====  Current basis = {round(price_second - price_base, 2)}' \
            + f', base price={price_base}, order price={order_price}, diff={round(order_price - price_base, 2)}  =====', True)

        order_state = response['result']['order_state']
        filled_amount = response['result']['filled_amount']

        # Ордер выполнился. Надо выполнить по маркету основной фьючерс.
        if filled_amount > 0:
            self.logging_bot(f'In check_order order filled_amount={filled_amount} out of {self.params["amount_other"]}')
            self.logging_bot(response['result'])
            if self.current_orders[pair_other]['filled_amount'] < filled_amount:
                amount = filled_amount - self.current_orders[pair_other]['filled_amount']
                self.current_orders[pair_other]['filled_amount'] = filled_amount
                is_trade, err = self.market_base(amount)
                return is_trade, err

        # Ордер не выполнился. Надо проверить, требуется ли его переставить.
        else:
            self.logging_bot('Start check for resseting order')

            # Разница цены, при которой надо переставить ордер.
            diff_up = self.params['diff_up']  # Переставлять оредр, если текущий базис больше заданного. (Надо ставить больше при вхождении в позицию)
            diff_down = self.params['diff_down']  # Переставлять ордер, если текущий базис снизился на данное значение. (Надо ставить больше при выходже из позиции)

            # diff_up - ставим побольше, когда нам надо чтобы базис был как можно больше
            # diff_down - ставим поменьше, когда нам надо чтобы базис был как можно больше

            # Если разница достаточно большая, то надо закрыть ордер и открыть заново.
            # 1) Отставляем ордер ниже, если базис начал уменьшаться не в нашу сторону.
            # 2) Отсавляем ордер ближе ордербуке, если разница стала слишком большой.
            expr = (order_price - price_base <= self.params['basis'] - diff_down) \
                    or (order_price - price_base >= self.params['basis'] + diff_up)

            if expr:
                self.logging_bot('Start resetting order')
                is_trade, err = self.cancel_order(order_info)
                if is_trade:
                    return True, err

                err = self.put_order()
                self.logging_bot('End resetting order')

            self.logging_bot('End check for resseting order')

        self.logging_bot('End check_order \n')

        return False, err

    def start_bot(self, message_queue):
        self.message_queue = message_queue
        self.killer = GracefulKiller()
        line = '\\='*28
        self.logging_bot(f"{line}\nStarting bot {self.name}\n{line}", True, markdown=True)
        self.logging_bot(get_parameters_table(self.params, ''), True, markdown=True)
        try:
            self.make_trade()
            print('Bot was stoped OK')
        except KeyboardInterrupt:
            self.close_bot()
            print('\nBot closed by KeyboardInterrupt')
            sys.exit(0)

    def close_bot(self):
        print("in close bot")
        self.logging_bot('In close bot')
        self.logging_bot('Start closing bot')

        pair_other = self.params['pair_other']
        order_info = self.current_orders[pair_other]
        err = self.cancel_order(order_info)
        self.is_running = False
        tg_logging(f'End closing bot, err\\={err}', False)


    def make_trade(self):
        self.logging_bot("In make_trade")
        # Начальный ордер.
        err = self.put_order()

        trade_done = False
        while not trade_done and self.is_running and not self.killer.kill_now:
            start_time = time.time()
            trade_done, err = self.check_order()
            end_time = time.time()
            print(f'Work time = {(end_time - start_time)} seconds')
        if trade_done:
            self.message_queue.put("done")
        self.close_bot()

def main():
    client_id = my_data.client_id
    client_secret = my_data.client_secret
    ws = DeribitWS(client_id, client_secret, test=True)

    # basis = 90  # При открытии позиции
    basis = 50  # При закрытии позиции, кратный 0.05

    pair_base = 'BTC-PERPETUAL'  # Закрываем по маркету, цена должна быть ниже
    pair_other = 'BTC-24JUN22'  # Выставляем лимитный ордер

    # buy/sell
    # side_base = 'buy'
    # side_other = 'sell'

    side_base = 'sell'
    side_other = 'buy'

    diff_up = 1.2  # Переставлять оредр, если текущий базис больше заданного. (Надо ставить больше при вхождении в позицию)
    diff_down = 5

    # Размер ордера в USDT
    amount = 10
    amount_base = amount
    amount_other = amount

    params = {}
    params['basis'] = basis  
    params['pair_base'] = pair_base
    params['pair_other'] = pair_other
    params['side_base'] = side_base
    params['side_other'] = side_other
    params['amount_base'] = amount_base
    params['amount_other'] = amount_other
    params['diff_up'] = diff_up
    params['diff_down'] = diff_down
    params["is_working"] = True

    trading_bot = BasisTradingBot(params, ws, None)


if __name__ == '__main__':

    main()