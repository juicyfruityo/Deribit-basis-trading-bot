import asyncio
import websockets
import json

import time
import logging
import sys

import my_data
from derebit_ws import DeribitWS



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
    
    def __init__(self, data, ws, tg_bot):
        data['basis'] = float(data['basis'])
        data["amount_base"] = float(data["amount_base"])
        data["amount_second"] = float(data["amount_second"])
        data["price_diff_up"] = float(data["price_diff_up"])
        data["price_diff_down"] = float(data["price_diff_down"])
        self.data = data

        self.ws = ws
        self.current_orders = {}  # {pair: [order_info]}
        self.current_positions = {}  # {pair: [positions]}

        self.time_iter = 0
        self.tg_bot = tg_bot
        self.log_to_tg = True

        logging.basicConfig(level=logging.INFO, filename='application_' + data['name'],
                            format='%(asctime)s  %(levelname)s:  %(message)s' )
        self.log = logging.getLogger(__name__)
        self.logging_bot("\n\n====================================================================", True)
        self.logging_bot("Init BasisTradingBot", True)


    def logging_bot(self, msg, log_to_tg=False):
        if msg == "":
            return
        self.log.info(msg)
        if log_to_tg:
            self.tg_bot.send_message(-561707350, msg)

    def put_order(self):
        # TODO: сделать обработку ошибок,
        # добавлять открытые ордера в список.
        # ? сделать структуру для ордеров

        self.logging_bot('In put_order')

        bid_base, ask_base, err = self.ws.get_bid_ask(self.data['pair_base'])
        # self.logging_bot(f'End get bid ask prices for base, err = {err}')
        # bid_second, ask_second, err = self.ws.get_bid_ask(self.data['pair_second'])
        self.logging_bot(f'End get bid ask prices for second, err = {err}')
        

        amount = self.data['amount_second']
        pair = self.data['pair_second']

        side = self.data['side_second']
        basis = self.data['basis']
        # min_price_step = 0.05
        # Т.к. я делаю post_only заявку, то можно указать любую цену, она попадёт в стакан.
        if side == 'buy':
            order_price = bid_base + basis
            self.logging_bot(f'Set limit order: pair={pair}, side={side}, price={order_price}, amount={amount}; pair_base={self.data["pair_base"]}: price={bid_base}')
        elif side == 'sell':
            order_price = ask_base + basis
            self.logging_bot(f'Set limit order: pair={pair}, side={side}, price={order_price}, amount={amount}; pair_base={self.data["pair_base"]}: price={ask_base}')

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

        pair_base = self.data['pair_base']
        # amount = self.data['amount_base']
        side = self.data['side_base']

        response, err = self.ws.market_order(pair_base, amount, side)
        self.logging_bot(f'End making market order, err={err} \n\t\t\t\t\t\t\t\t Trade DONE amount {amount} out of {self.data["amount_base"]}')
        
        pair_second = self.data['pair_second']
        order_price = self.current_orders[pair_second]['order_price']
        price_base = response['result']['order']['average_price']
        side_second = self.data['side_second']

        self.logging_bot(f'Trade done amount {amount} out of {self.data["amount_base"]}', True)
        self.logging_bot(f'basis={round(order_price - price_base, 2)}; {side} {pair_base}: price={price_base}; {side_second} {pair_second}: price={order_price};', True)

        # Т.к. по сути ордер один, то можно закрывать бота.
        print(f'Trade done amount {amount} out of {self.data["amount_base"]}')
        print(f'basis={round(order_price - price_base, 2)}; {side} {pair_base}: price={price_base}; {side_second} {pair_second}: price={order_price};')
        
        # Если исполнился частично, надо продолжить работу бота.
        if amount < self.data['amount_base']:
            self.data['amount_base'] -= amount
            self.data['amount_second'] -= amount
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

            is_trade, err = self.market_base(self.data['amount_base'])
            return is_trade, err

        # Значит ордер частично исполнился.
        pair_second = self.data['pair_second']
        filled_amount = response['result']['filled_amount']
        if filled_amount > 0:

            self.logging_bot(f'In cancel_order order filled_amount={filled_amount}')
            self.logging_bot(response['result'])

            if self.current_orders[pair_second]['filled_amount'] < filled_amount:
                amount = filled_amount - self.current_orders[pair_second]['filled_amount']
                self.current_orders[pair_second]['filled_amount'] = filled_amount
                is_trade, err = self.market_base(amount)
                return is_trade, err

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

        pair_base = self.data['pair_base']
        pair_second = self.data['pair_second']
        amount = self.data['amount_base']
        side = self.data['side_base']

        order_info = self.current_orders[pair_second]
        order_id, amount_done = order_info['order_id'], order_info['filled_amount']
        order_price = order_info['order_price']

        # Проверяем ордер.
        res_order_state, base_bid_ask, second_bid_ask = self.ws.execute_funcs(
            self.ws.get_order_state_async(order_id),
            self.ws.get_bid_ask_async(self.data['pair_base']),
            self.ws.get_bid_ask_async(self.data['pair_second'])
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
            self.logging_bot(f'In check_order order filled_amount={filled_amount} out of {self.data["amount_second"]}')
            self.logging_bot(response['result'])
            if self.current_orders[pair_second]['filled_amount'] < filled_amount:
                amount = filled_amount - self.current_orders[pair_second]['filled_amount']
                self.current_orders[pair_second]['filled_amount'] = filled_amount
                is_trade, err = self.market_base(amount)
                return is_trade, err

        # Ордер не выполнился. Надо проверить, требуется ли его переставить.
        else:
            self.logging_bot('Start check for resseting order')

            # Разница цены, при которой надо переставить ордер.
            price_diff_up = self.data['price_diff_up']  # Переставлять оредр, если текущий базис больше заданного. (Надо ставить больше при вхождении в позицию)
            price_diff_down = self.data['price_diff_down']  # Переставлять ордер, если текущий базис снизился на данное значение. (Надо ставить больше при выходже из позиции)

            # price_diff_up - ставим побольше, когда нам надо чтобы базис был как можно больше
            # price_diff_down - ставим поменьше, когда нам надо чтобы базис был как можно больше

            # Если разница достаточно большая, то надо закрыть ордер и открыть заново.
            # 1) Отставляем ордер ниже, если базис начал уменьшаться не в нашу сторону.
            # 2) Отсавляем ордер ближе ордербуке, если разница стала слишком большой.
            expr = (order_price - price_base <= self.data['basis'] - price_diff_down) \
                    or (order_price - price_base >= self.data['basis'] + price_diff_up)

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

    def close_bot(self):
        self.logging_bot('In close bot')
        self.logging_bot('Start closing bot')

        pair_second = self.data['pair_second']
        order_info = self.current_orders[pair_second]
        err = self.cancel_order(order_info)

        self.logging_bot(f'End closing bot, err={err}')


    def make_trade(self):
        self.logging_bot("In make_trade")
        # Начальный ордер.
        err = self.put_order()

        trade_done = False
        while not trade_done and self.data["is_working"]:
            # start_time = time.time()
            trade_done, err = self.check_order()
            # end_time = time.time()
            # print(f'Work time = {(end_time - start_time)} seconds')
            # time.sleep(3)

def main():
    client_id = my_data.client_id
    client_secret = my_data.client_secret
    ws = DeribitWS(client_id, client_secret, test=True)

    # basis = 90  # При открытии позиции
    basis = 50  # При закрытии позиции, кратный 0.05

    pair_base = 'BTC-PERPETUAL'  # Закрываем по маркету, цена должна быть ниже
    pair_second = 'BTC-24JUN22'  # Выставляем лимитный ордер

    # buy/sell
    # side_base = 'buy'
    # side_second = 'sell'

    side_base = 'sell'
    side_second = 'buy'

    price_diff_up = 1.2  # Переставлять оредр, если текущий базис больше заданного. (Надо ставить больше при вхождении в позицию)
    price_diff_down = 5

    # Размер ордера в USDT
    amount = 10
    amount_base = amount
    amount_second = amount

    data = {}
    data['basis'] = basis  
    data['pair_base'] = pair_base
    data['pair_second'] = pair_second
    data['side_base'] = side_base
    data['side_second'] = side_second
    data['amount_base'] = amount_base
    data['amount_second'] = amount_second
    data['price_diff_up'] = price_diff_up
    data['price_diff_down'] = price_diff_down
    data["is_working"] = True

    trading_bot = BasisTradingBot(data, ws, None)
    try:
        trading_bot.make_trade()
        print('Bot was stoped OK')
    except KeyboardInterrupt:
        trading_bot.close_bot()
        print('\nBot closed by KeyboardInterrupt')
        sys.exit(0)


if __name__ == '__main__':

    main()