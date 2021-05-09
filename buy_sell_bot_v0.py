import asyncio
import websockets
import json

import time
import logging
import sys

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

import my_data
from derebit_ws import DeribitWS

client_id = my_data.client_id_test
client_secret = my_data.client_secret_test


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
    
    def __init__(self, data, ws):
        self.data = data
        self.ws = ws
        self.current_orders = {}  # {pair: [order_info]}
        self.current_positions = {}  # {pair: [positions]}

        logging.basicConfig(level=logging.INFO, filename='application',
                            format='%(asctime)s  %(levelname)s:  %(message)s' )
        self.log = logging.getLogger(__name__)
        self.log.info("\n\n====================================================================")
        self.log.info("Starting application")

    def put_order(self):
        # TODO: сделать обработку ошибок,
        # добавлять открытые ордера в список.
        # ? сделать структуру для ордеров

        self.log.info('In put_order')

        bid_base, ask_base, err = self.ws.get_bid_ask(self.data['pair_base'])
        self.log.info(f'End get bid ask prices for base, err = {err}')

        # bid_second, ask_second, err = self.ws.get_bid_ask(self.data['pair_second'])
        # self.log.info(f'End get bid ask prices for second, err = {err}')
        

        amount = self.data['amount_second']
        pair = self.data['pair_second']

        side = self.data['side_second']
        basis = self.data['basis']
        # min_price_step = 0.05
        # Т.к. я делаю post_only заявку, то можно указать любую цену, она попадёт в стакан.
        if side == 'buy':
            order_price = bid_base + basis
            self.log.info(f'Set limit order: pair={pair}, side={side}, price={order_price}, amount={amount}; pair_base={self.data["pair_base"]}: price={bid_base}')
        elif side == 'sell':
            order_price = ask_base + basis
            self.log.info(f'Set limit order: pair={pair}, side={side}, price={order_price}, amount={amount}; pair_base={self.data["pair_base"]}: price={ask_base}')

        post_only = True
        reduce_only = False
        response, err = self.ws.limit_order(pair, amount, side, order_price, post_only, reduce_only)
        self.log.info(f'Make order, err={err}')

        order_id = response['result']['order']['order_id']
        order_price = response['result']['order']['price']
        order_info = {
            "order_id": order_id, "order_price": order_price, "filled_amount": 0.
        }
        self.current_orders[pair] = order_info

        return err

    def market_base(self):
        self.log.info('Start making market order')

        pair_base = self.data['pair_base']
        amount = self.data['amount_base']
        side = self.data['side_base']

        response, err = self.ws.market_order(pair_base, amount, side)
        self.log.info(f'End making market order, err={err} \n\t\t\t\t\t\t\t\t Trade DONE')
        
        pair_second = self.data['pair_second']
        order_price = self.current_orders[pair_second]['order_price']
        price_base = response['result']['order']['average_price']
        side_second = self.data['side_second']
        self.log.info(f'basis={round(order_price - price_base, 2)}; {side} {pair_base}: price={price_base}; {side_second} {pair_second}: price={order_price};')

        # Т.к. по сути ордер один, то можно закрывать бота.
        print('Trade done')
        print(f'basis={round(order_price - price_base, 2)}; {side} {pair_base}: price={price_base}; {side_second} {pair_second}: price={order_price};')
        
        return True, err

    def cancel_order(self, order_info):
        self.log.info('In cancel_order')
        order_id, amount_done = order_info['order_id'], order_info['filled_amount']
        response, err = self.ws.cancel_order(order_id)
        self.log.info(f'End cancelling order, err = {err}')

        # TODO: сделать проверку, что ордер исполнился.
        if response['result']['order_state'] == 'filled':
            is_trade, err = self.market_base()
            return True, err
        return False, err

    def check_order(self):
        '''
        Если ордер выполнился, то требуется сделать симметричную
        сделку на основной паре. Закончить программу.
        Если цена на основной фьючерс изменилась достаточно
        сильно, то требуется закрыть отрытый ордер и открыть новый.
        
        
        '''
        # TODO: надо добавить асинхронное выполнение запроса цены и запроса инфы об ордере.
        self.log.info('In check_order')

        # bid_base, ask_base, err = self.ws.get_bid_ask(self.data['pair_base'])
        # self.log.info(f'End get bid ask prices for base, err = {err}')
        # bid_second, ask_second, err = self.ws.get_bid_ask(self.data['pair_second'])
        # self.log.info(f'End get bid ask prices for second, err = {err}')

        pair_base = self.data['pair_base']
        pair_second = self.data['pair_second']
        amount = self.data['amount_base']
        side = self.data['side_base']

        # Проверяем ордер.
        # for order_info in self.current_orders[pair_second]:
        order_info = self.current_orders[pair_second]
        order_id, amount_done = order_info['order_id'], order_info['filled_amount']
        order_price = order_info['order_price']

        res_order_state, base_bid_ask, second_bid_ask = self.ws.execute_funcs(
            self.ws.get_order_state_async(order_id),
            self.ws.get_bid_ask_async(self.data['pair_base']),
            self.ws.get_bid_ask_async(self.data['pair_second'])
        )
        response, err_order_state = res_order_state
        bid_base, ask_base, err_base = base_bid_ask
        bid_second, ask_second, err_second = second_bid_ask
        err = err_base

        # self.log.info('Start check order state')
        # response, err = self.ws.get_order_state_async(order_id)
        self.log.info(f'End check order state, err = {err_order_state}')

        # bid_base, ask_base, err = self.ws.get_bid_ask_async(self.data['pair_base'])
        self.log.info(f'End get bid ask prices for base, err = {err_base}')
        self.log.info(f'End get bid ask prices for second, err = {err_second}')
        price_base = bid_base if side == 'sell' else ask_base
        price_second = bid_second if side == 'buy' else ask_second
        self.log.info(f'====  Current basis = {round(price_second - price_base, 2)}, base price={price_base}, order price={order_price}, diff={round(order_price - price_base, 2)}  =====')

        order_state = response['result']['order_state']
        filled_amount = response['result']['filled_amount']

        # Ордер выполнился. Надо выполнить по маркету основной фьючерс.
        if order_state == 'filled':
            is_trade, err = self.market_base()
            return True, err
            
        # TODO: сделать учёт, если ордер исполнился частично.
        # Надо частично выполнить по маркету основной фьючерс
        # if filled_amount > 0:

        # Ордер не выполнился. Надо проверить, требуется ли его переставить.
        else:
            self.log.info('Start check for resseting order')

            max_price_diff = 1.5  # Разница цены, при которой надо переставить ордер.
            # Если разница достаточно большая, то надо закрыть ордер и открыть заново.
            expr = (order_price - price_base <= self.data['basis'] - max_price_diff) \
                    or (order_price - price_base >= self.data['basis'] + max_price_diff)
            if expr:
                self.log.info('Start resetting order')
                is_trade, err = self.cancel_order(order_info)
                if is_trade:
                    return True, err

                err = self.put_order()
                self.log.info('End resetting order')

            self.log.info('End check for resseting order')

        self.log.info('End check_order \n')

        return False, err

    def close_bot(self):
        self.log.info('\n')
        self.log.info('In close bot')
        self.log.info('Start closing bot')

        pair_second = self.data['pair_second']
        order_info = self.current_orders[pair_second]
        err = self.cancel_order(order_info)

        self.log.info(f'End closing bot, err={err}')


    def make_trade(self):
        self.log.info("In make_trade")
        # Начальный ордер.
        err = self.put_order()

        trade_done = False
        while not trade_done:
            # start_time = time.time()
            trade_done, err = self.check_order()
            # end_time = time.time()
            # print(f'Work time = {(end_time - start_time)} seconds')
            # time.sleep(3)


def main():
    ws = DeribitWS(client_id, client_secret, test=True)

    # basis = 20  # При открытии позиции
    basis = 80  # При закрытии позиции, кратный 0.05

    pair_base = 'ETH-PERPETUAL'  # Закрываем по маркету
    pair_second = 'ETH-25JUN21'  # Выставляем лимитный ордер

    # buy/sell
    side_base = 'buy'
    side_second = 'sell'

    # side_base = 'sell'
    # side_second = 'buy'

    # Размер ордера в USDT
    amount_base = 1
    amount_second = 1

    data = {}
    data['basis'] = basis  
    data['pair_base'] = pair_base
    data['pair_second'] = pair_second
    data['side_base'] = side_base
    data['side_second'] = side_second
    data['amount_base'] = amount_base
    data['amount_second'] = amount_second

    # trade_done = False

    # while not trade_done:
    trading_bot = BasisTradingBot(data, ws)

    try:
        trading_bot.make_trade()
        print('Bot closed because trade done')
    except KeyboardInterrupt:
        trading_bot.close_bot()
        print('\nBot closed by KeyboardInterrupt')
        sys.exit(0)


if __name__ == '__main__':

    main()

    # ws = DeribitWS(client_id, client_secret, test=False)

    # for i in range(1000):
    #     eth_perp = get_quote('ETH-PERPETUAL')
    #     eth_7may = get_quote('ETH-7MAY21')
    #     print(f'PERP = {eth_perp},  7MAY = {eth_7may}')
    #     time.sleep(1)

    # order_book_perp = get_order_book('ETH-PERPETUAL', 5)
    # order_book_7may = get_order_book('ETH-7MAY21', 5)

    # print(order_book_perp)

    # for i in range(20):
    #     bid_perp, ask_perp = get_bid_ask('ETH-PERPETUAL')
    #     bid_7may, ask_7may = get_bid_ask('ETH-7MAY21')
    
    #     print(f'PERP: bid={bid_perp} ask={ask_perp};  7MAY: bid={bid_7may} ask={ask_7may}; DIFF: buy={bid_7may-ask_perp} sell={ask_7may-bid_perp}')

    #     time.sleep(1)