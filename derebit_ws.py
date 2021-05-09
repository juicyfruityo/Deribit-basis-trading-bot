import asyncio
import websockets
import json

from helpers import *
import my_data

client_id = my_data.client_id
client_secret = my_data.client_secret


class DeribitWS:

    def __init__(self, client_id, client_secret, test=False):
        '''
        Информация об API:
        10001 - максимальное число данных в одном запросе

        '''

        if test:
            self.url = 'wss://test.deribit.com/ws/api/v2'
        elif not test:
            self.url = 'wss://www.deribit.com/ws/api/v2'
        else:
            raise Exception('live must be a bool, True=real, False=paper')


        self.client_id = client_id
        self.client_secret = client_secret

        self.auth_creds = {
              "jsonrpc" : "2.0",
              "id" : 0,
              "method" : "public/auth",
              "params" : {
                "grant_type" : "client_credentials",
                "client_id" : self.client_id,
                "client_secret" : self.client_secret
              }
            }
        self.test_creds()

        self.msg = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": None,
        }

    async def pub_api(self, msg):
        async with websockets.connect(self.url) as websocket:
            await websocket.send(msg)
            while websocket.open:
                response = await websocket.recv()
                return json.loads(response)

    async def priv_api(self, msg):
        async with websockets.connect(self.url) as websocket:
            await websocket.send(json.dumps(self.auth_creds))
            while websocket.open:
                response = await websocket.recv()
                await websocket.send(msg)
                response = await websocket.recv()
                break
            return json.loads(response)

    @staticmethod
    def async_loop(api, message):
        return asyncio.get_event_loop().run_until_complete(api(message))

    def test_creds(self):
        response = self.async_loop(self.pub_api, json.dumps(self.auth_creds))
        if 'error' in response.keys():
            raise Exception(f"Auth failed with error {response['error']}")
        else:
            print("Auth creds are good, it worked")

    def __error_check(self, response):
        if 'error' in response.keys():
            return response, 'error'
        else:
            return response, None

    def market_order(self, instrument, amount, side):
        params = {
                "instrument_name" : instrument,
                "amount" : amount,
                "type" : "market",
              }
        if side not in ['buy', 'sell']:
            raise Exception(f'Side in market order should be sell or buy')

        self.msg["method"] = f"private/{side}"
        self.msg["params"] = params

        response, err = self.__error_check(self.async_loop(self.priv_api, json.dumps(self.msg)))

        return response, err


    def limit_order(self, instrument, amount, side, price,
                   post_only, reduce_only):
        params = {
            "instrument_name": instrument,
            "amount": amount,
            "type": "limit",
            "price": price,
            # TODO: разобраться как конкретно это работает.
            "post_only": post_only
            # "reduce_only": reduce_only

        }
        if side not in ['buy', 'sell']:
            raise Exception(f'Side in market order should be sell or buy')

        self.msg["method"] = f"private/{side}"
        self.msg["params"] = params
        response, err = self.__error_check(self.async_loop(self.priv_api, json.dumps(self.msg)))
        return response, err

    def cancel_order(self, order_id):
        params =  {
                "order_id": order_id
            }
        self.msg["method"] = "private/cancel"
        self.msg["params"] = params

        response, err = self.__error_check(self.async_loop(self.priv_api, json.dumps(self.msg)))
        return response, err

    # market data methods
    def get_data(self, instrument, start, end, timeframe):
        params =  {
                "instrument_name": instrument,
                "start_timestamp": start,
                "end_timestamp": end,
                "resolution": timeframe
            }

        self.msg["method"] = "public/get_tradingview_chart_data"
        self.msg["params"] = params

        data = self.async_loop(self.pub_api, json.dumps(self.msg))
        return data

    def get_orderbook(self, instrument, depth=5):
        params = {
            "instrument_name": instrument,
            "depth": depth
        }
        self.msg["method"] = "public/get_order_book"
        self.msg["params"] = params

        order_book, err = self.__error_check(self.async_loop(self.pub_api, json.dumps(self.msg)))
        return order_book, err

    def get_bid_ask(self, instrument):
        order_book, err = self.get_orderbook(instrument, 1)
        if err is None:
            return order_book['result']['best_bid_price'], order_book['result']['best_ask_price'], err
        else:
            return -1, -1, err

    def get_quote(self, instrument):
        params = {
            "instrument_name": instrument
        }
        self.msg["method"] = "public/ticker"
        self.msg["params"] = params
        quote = self.async_loop(self.pub_api, json.dumps(self.msg))

        return quote['result']['last_price']

    def get_funding_rate_history(self, instrument, start_timestamp, end_timestamp):
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp
        }
        self.msg["method"] = "public/get_funding_rate_history"
        self.msg["params"] = params

        funding_rate_history = self.async_loop(self.pub_api, json.dumps(self.msg))
        return funding_rate_history['result']

    #account methods
    def account_summary(self, currency, extended=True):
        params = {
            "currency": currency,
            "extended": extended
        }

        self.msg["method"] = "private/get_account_summary"
        self.msg["params"] = params
        summary = self.async_loop(self.priv_api, json.dumps(self.msg))
        return summary

    def get_order_state(self, order_id):
        params = {
            "order_id": order_id
        }
        self.msg["method"] = "private/get_order_state"
        self.msg["params"] = params
        positions, err = self.__error_check(self.async_loop(self.priv_api, json.dumps(self.msg)))
        return positions, err

    def get_positions(self, instrument, kind="future"):
        params = {
            "instrument_name": instrument,
            "kind": kind
        }
        self.msg["method"] = "private/get_positions"
        self.msg["params"] = params
        positions = self.async_loop(self.priv_api, json.dumps(self.msg))
        return positions

    def available_instruments(self, currency, kind="future", expired=False):
        params = {
            "currency": currency,
            "kind": kind,
            "expired": expired
        }

        self.msg["method"] = "public/get_instruments"
        self.msg["params"] = params
        resp = self.async_loop(self.pub_api, json.dumps(self.msg))
        instruments = [d["instrument_name"] for d in resp['result']]
        return instruments


if __name__ == '__main__':

    ws = DeribitWS(client_id, client_secret, test=False)

    start = datetime_to_unix("2021-04-01 00:00") * 1000
    end = datetime_to_unix("2021-04-02 00:00") * 1000
    pair = 'ETH-PERPETUAL'

    print(ws.get_funding_rate_history(pair, start, end))