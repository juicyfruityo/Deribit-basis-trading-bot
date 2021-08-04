import asyncio
import websockets
from threading import Thread
import json
import time
import logging
import os
from queue import Queue
import my_data
from helpers import *

TEST_URI = 'wss://test.deribit.com/ws/api/v2'
URI = "wss://www.deribit.com/ws/api/v2"

q_price_base = Queue()  # Передаем цену базового актива
q_price_other = Queue()
q_order_state = Queue()  # Передаем информацию об отслеживаемом ордере
q_order_monitor = Queue()  # Передаем информаци, какой ордер требуется отслеживать


class BasisTradingBot:
    def __init__(self, name, params=None, test=False, tg_bot=None):
        self.name = name
        self.params = params
        self.is_running = False
        self.uri = TEST_URI if test else URI

        self.current_orders = {}  # {pair: [order_info]}
        self.current_positions = {}  # {pair: [positions]}

        self.time_iter = 0
        self.tg_bot = tg_bot
        self.log_to_tg = True

        # self.log = logging.getLogger('application_' + name)
        # handler = logging.FileHandler('application_' + name)
        # formatter = logging.Formatter('%(asctime)s  %(levelname)s:  %(message)s')
        # handler.setFormatter(formatter)
        # self.log.addHandler(handler)
        # self.log.setLevel(logging.INFO)
        self.log = get_logging_file(name)

        self.logging_bot("\n\n===============================", True)
        self.logging_bot(f"Creating BasisTradingBot named {name} with params {get_parameters_table(params, '')}", True)

    def logging_bot(self, msg, log_to_tg=False, markdown=False):
        if msg == "":
            return
        self.log.info(msg)
        if log_to_tg and self.tg_bot is not None:
            tg_logging(msg, markdown)

    async def start_check_price(self):
        '''
        Открываем вебсокет и мониторим риал-тайм данные по
        ценам на фьючерсы, передаём эти данные в Queue,
        откуда данные получаются и обрабатываются
        в другом Thead - start_check_order

        '''
        self._basis = None
        self._last_base_price = None
        self._last_other_price = None
        self._prev_time = time.time()

        # ping_interval требуется т.к. иногда связь сама ппо себе падает,
        # подробнее:
        # https://stackoverflow.com/questions/54101923/1006-connection-closed-abnormally-error-with-python-3-7-websockets
        async with websockets.connect(self.uri, ping_interval=None) as websocket:
            self.logging_bot(f"Socket fro price is opened")
            # Мониторим цены на активы
            msg_data = {
                "method": "public/subscribe",
                "params": {
                    "channels": [
                        f"quote.{self.params['base_inst']}",
                        f"quote.{self.params['other_inst']}"
                    ]
                },
                "jsonrpc": "2.0",
                "id": 1
            }
            await websocket.send(json.dumps(msg_data))

            # Аунтефикация для private запросов
            auth_creds = {
                "jsonrpc" : "2.0",
                "id" : 0,
                "method" : "public/auth",
                "params" : {
                    "grant_type" : "client_credentials",
                    "client_id" : self.params['client_id'],
                    "client_secret" : self.params['client_secret']
                }
            }
            await websocket.send(json.dumps(auth_creds))

            # Мониторим order state по требуемому активу
            msg_data = {
                "method": "private/subscribe",
                "params": {
                    "channels": [
                        f"user.orders.{self.params['other_inst']}.raw"
                    ]
                },
                "jsonrpc": "2.0",
                "id": 1
            }
            await websocket.send(json.dumps(msg_data))

            while websocket.open:
                message = await websocket.recv()

                if 'params' in message:
                    data = json.loads(message)["params"]

                    if data["channel"][:5] == "quote":
                        self.__preprocess_price(data["data"])
                    elif data["channel"][:11] == "user.orders":
                        self.__preprocess_order_state(data["data"])

            self.logging_bot(f"Socket for price is closed")

    def __preprocess_price(self, data):
        # if "params" in message:
        #     data = json.loads(message)["params"]["data"]
        if data["instrument_name"] == self.params["base_inst"]:
            if self.params["base_side"] == "sell":
                self._last_base_price = data["best_bid_price"]
            else:
                self._last_base_price = data["best_ask_price"]
        else:
            if self.params["other_side"] == "sell":
                self._last_other_price = data["best_ask_price"]
            else:
                self._last_other_price = data["best_bid_price"]
        
        if self._last_base_price is not None and self._last_other_price is not None:
            self._basis = self._last_other_price - self._last_base_price
            
            # Обмен информацией с другими тредами.
            q_price_base.put(self._last_base_price, block=True)
            q_price_other.put(self._last_other_price)

            # clear = lambda: os.system('clear')
            # clear()
            # print(f"Last_base_price: {self._last_base_price}\nLast_other_price: {self._last_other_price}\nBasis: {self._basis}")
            curr_time = time.time()
            if curr_time - self._prev_time >= 10:
                self._prev_time = curr_time
                self.logging_bot((f"=== Last_base_price: {self._last_base_price}   Last_other_price: {self._last_other_price}  Basis: {self._basis}"))

    def __preprocess_order_state(self, data):
        if data['order_id'] == self.current_orders[self.params['other_inst']]['order_id']:
            order_state = {
                "order_id": data['order_id'],
                "price": data['price'],
                "filled_amount": data['filled_amount'],
                "order_state": data["order_state"]
            }
            self.logging_bot((f'Order state: order_id={data["order_id"]}, order_price={data["price"]}, order_state={data["order_state"]}, filled_amount={data["filled_amount"]}'))
            q_order_state.put(order_state)
            
    def start_price(self):
        asyncio.run(self.start_check_price())
        # asyncio.get_event_loop().run_until_complete(self.start_check_price())
        asyncio.get_event_loop().run_forever()


    async def start_check_order(self):
        '''
        Выставляем ордер для other_inst и меняем расположение
        ордера, взависимости от получаемой с другого треда цены.
        Мониторим выполнение ордера и в случае его исполнения
        вызываем соответствующий маркет ордер для base_instr.

        '''
        self._prev_price_base = None
        self._prev_price_other = None

        # По поводу ping_interval=None смотри выше.
        async with websockets.connect(self.uri, ping_interval=None) as websocket:
            self.logging_bot(f"Socket for order is opened", False)
            # Аунтефикация для дальнейшего исполнения private api команд
            auth_creds = {
                "jsonrpc" : "2.0",
                "id" : 0,
                "method" : "public/auth",
                "params" : {
                    "grant_type" : "client_credentials",
                    "client_id" : self.params['client_id'],
                    "client_secret" : self.params['client_secret']
                }
            }
            await websocket.send(json.dumps(auth_creds))

            await self.__put_order(websocket)  # Выставляем начальный ордер.
            trade_done = False

            _iters = 0
            _exec_times = []
            while websocket.open:
                start = time.time()
                trade_done, err = await self.__check_order(websocket)
                if trade_done:
                    break
                
                _iters += 1
                _exec_times.append(time.time() - start)
                if _iters == 60:
                    # self.logging_bot(f'Working time of __check_order = {sum(_exec_times) / _iters} s (mean)')
                    _iters = 0
                    _exec_times = []

            self.logging_bot(f"Socket for order is closed", False)

    def start_order(self):
        asyncio.run(self.start_check_order())
        # asyncio.get_event_loop().run_until_complete(self.start_check_order())
        asyncio.get_event_loop().run_forever()

    async def __put_order(self, websocket):
        self.logging_bot('In __put_order')
        # Выставляем ордер для other_inst на нужный размер базиса.
        last_base_price = q_price_base.get(block=True)
        self._prev_price_base = last_base_price
        price = last_base_price + self.params['basis']

        # Если часть ордера выполнилась, то заявку нужно выствалять с меньшим размером.
        if self.current_orders.get(self.params['other_inst']) is not None:
            amount = self.current_orders[self.params['other_inst']]['amount'] \
                    - self.current_orders[self.params['other_inst']]['filled_amount']
        else:
            amount = self.params['amount_other']

        msg_order = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": f"private/{self.params['other_side']}",
            "params": {
                "instrument_name" : self.params['other_inst'],
                "amount" : amount,
                "price": price,
                "type" : "limit",
                "post_only": True
            }
        }
        await websocket.send(json.dumps(msg_order))
        while websocket.open:
          message = await websocket.recv()
          data = json.loads(message)
          if "order" in data['result']:
              break

        self.logging_bot(f'Put new order id={data["result"]["order"]["order_id"]},' \
                        + f' price={data["result"]["order"]["price"]},' \
                        + f' amount={data["result"]["order"]["amount"]}')
        # Записываем информацию об ордере.
        self.current_orders[self.params['other_inst']] = {
            'order_id': data['result']['order']['order_id'],
            'filled_amount': 0,
            'price': data['result']['order']['price'],
            'amount': data['result']['order']['amount']
        }

    async def __cancel_order(self, websocket):
        self.logging_bot('In __cancel_order')
        order_info = self.current_orders[self.params['other_inst']]
        msg_cancel = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "private/cancel",
            "params": {
                "order_id": order_info['order_id']
            }
        }
        await websocket.send(json.dumps(msg_cancel))
        while websocket.open:
            message = await websocket.recv()
            data = json.loads(message)
            if data.get('error') or "order_id" in data.get('result'):
                break

        self.logging_bot(f'Canceling order id={order_info["order_id"]}, price={order_info["price"]}, error={data.get("error")}')

        # Значит ордер полностью исполнился.
        # TODO: посмотреть что значат разные виды ошибок.
        if data.get('error') is not None:
            self.logging_bot(f'In cancel order Making full market order, amount = {order_info["amount"] - order_info["filled_amount"]}', True)

            amount = order_info['amount'] - order_info['filled_amount']
            market_price = await self.__market_order(websocket, self.params['base_side'],
                                                        self.params['base_inst'], amount)
            self.logging_bot(f'Trade done, order_price={order_info["price"]}, market_price={market_price}, amount={amount}, diff={order_info["price"] - market_price}', True)
            return True, None
        else:
            # Проверим ордер, т.к. он мог исполнится частично.
            filled_amount = data['result']['filled_amount']
            if filled_amount > order_info['filled_amount']:
                self.logging_bot(f'In cancel order Making partial market order, amount = {data["result"]["filled_amount"]}', True)

                amount = filled_amount - order_info['filled_amount']
                market_price = await self.__market_order(websocket, self.params['base_side'],
                                                        self.params['base_inst'], amount)
                self.current_orders[self.params['other_inst']]['filled_amount'] += amount
                self.logging_bot(f'Trade done partially, order_price={order_info["price"]}, market_price={market_price}, amount={amount}, diff={order_info["price"] - market_price}', True)

                if filled_amount == order_info['amount']:
                    return True, None

        return False, None
    
    async def __market_order(self, websocket, side, instrument, amount):
        msg_order = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": f"private/{side}",
            "params": {
                "instrument_name" : instrument,
                "amount" : amount,
                "type" : "market",
                "post_only": False
            }
        }
        await websocket.send(json.dumps(msg_order))
        while websocket.open:
          message = await websocket.recv()
          data = json.loads(message)
          if data.get('error') or "order" in data['result']:
              break

        if data.get('error'):
            self.logging_bot(f'ERROR in market_order={data.get("error")}', True)
            return None
        else:
            self.logging_bot(f'Correctly made market order, market_price={data["result"]["order"]["average_price"]}, amount={data["result"]["order"]["amount"]}', True)
            return data["result"]["order"]["average_price"]

    async def __check_order(self, websocket):
        # self.logging_bot('In __check_order')
        # Проверяем информацию о текущем ордере.
        order_info = self.current_orders[self.params['other_inst']]
        
        order_state = None
        if q_order_state.empty() is False:
            order_state = q_order_state.get(block=True)
            if order_state['order_id'] != order_info['order_id']:
                order_state = None

        # Делаем маркет ордер для базового актива на величину исполненной заявки.
        if order_state is not None and order_state.get('order_state') != 'open':
            self.logging_bot(f'In check order Making market order, amount = {order_state["filled_amount"] - order_info["filled_amount"]}', True)

            amount = order_state['filled_amount'] - order_info['filled_amount']
            market_price = await self.__market_order(websocket, self.params['base_side'],
                                                    self.params['base_inst'], amount)
            self.current_orders[self.params['other_inst']]['filled_amount'] += amount

            self.logging_bot(f'amount={order_info["amount"]} filled_amount={order_state["filled_amount"]}')
            if order_state['filled_amount'] == order_info['amount']:
                # TODO: закончить работу бота, т.к. сделка сделана.
                self.logging_bot(f'Trade done, order_price={order_info["price"]}, market_price={market_price}, amount={amount}, diff={order_info["price"] - market_price}', True)
                print('Trade done')
                return True, None
            else:
                self.logging_bot(f'Trade done partially, order_price={order_info["price"]}, market_price={market_price}, amount={amount}, diff={order_info["price"] - market_price}', True)

        # Забираем текущую цену базового актива, считаем,
        # значимо ли изменилась цена, относительно той, что была,
        # когда был поставлен последний ордер.
        last_base_price = None
        while not q_price_base.empty():
            # Это надо, чтобы получить самую последнюю доступную цену
            # и опустошить очередь.
            last_base_price = q_price_base.get(block=True)
        if last_base_price is not None:
            # diff_down - ставим меньше, когда надо, чтобы базис был больше
            # diff_up - ставим меньше, когда надо, чтобы базис был меньше
            expr = (last_base_price - self._prev_price_base <= -self.params["diff_down"]) \
                    or (last_base_price - self._prev_price_base >= self.params["diff_up"])

            self.time_iter += 1
            if self.time_iter == 30:
                self.time_iter = 0
                last_other_price = q_price_other.get(block=True)
                self.logging_bot(f'====  Current basis = {None}' \
                                + f', base price={last_base_price}, order price={order_info["price"]}, \n' + '\t'*8 \
                                + f' diff={round(order_info["price"] - last_base_price, 2)}, expr_diff={last_base_price - self._prev_price_base}  =====')
        else:
            expr = False
        # print(f'In check_order: last_base_price = {last_base_price}')
        
        # Если текущая цена базового актива изменилась значимым образом,
        # то требуется закрыть открытый ордер, и открыть заново.
        if expr:
            self.logging_bot(f'====  Current basis = {None}' \
                                + f', base price={last_base_price}, order price={order_info["price"]}, \n' + '\t'*8 \
                                + f' diff={round(order_info["price"] - last_base_price, 2)}, expr_diff={last_base_price - self._prev_price_base}  =====')
            self.logging_bot('Start resetting order')

            trade_done, err = await self.__cancel_order(websocket)
            if trade_done:
                # TODO: добавить обработку этого момента
                print('Trade done')
                return trade_done, err
            await self.__put_order(websocket)

            self.logging_bot('End resetting order')

        return False, None

    def start(self):
        t_price = Thread(target=self.start_price)
        t_order = Thread(target=self.start_order)

        t_price.start()
        t_order.start()

        # t_price.join()
        # t_order.join()



def main():
    bot = BasisTradingBot(
        "Test1", 
        params={
            "name": "Test1",
            "coin": "ETH",
            "base_inst": 'ETH-PERPETUAL',
            "other_inst": 'ETH-24SEP21',
            "base_side": 'buy',
            "other_side": 'sell',
            'basis': 14.1,                
            "amount_base": 1.,
            "amount_other": 1.,
            "diff_up": 0.3,
            "diff_down": 0.8,
            'client_id': my_data.api_keys[1]["client_id"],
            'client_secret': my_data.api_keys[1]["client_secret"]
        },
        test=False
    )

    # bot = BasisTradingBot(
    #     "Test2", 
    #     params={
    #         "name": "Test2",
    #         "coin": "ETH",
    #         "base_inst": 'ETH-PERPETUAL',
    #         "other_inst": 'ETH-24SEP21',
    #         "base_side": 'sell',
    #         "other_side": 'buy',
    #         'basis': 8.1,                
    #         "amount_base": 1.,
    #         "amount_other": 1.,
    #         "diff_up": 0.8,
    #         "diff_down": 0.3,
    #         'client_id': my_data.api_keys[0]["client_id"],
    #         'client_secret': my_data.api_keys[0]["client_secret"]
    #     },
    #     test=False
    # )

    # asyncio.get_event_loop().run_until_complete(bot.start())
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # loop.run_until_complete(bot.start())
    # asyncio.run(bot.start())
    bot.start()


if __name__ == "__main__":
    main()