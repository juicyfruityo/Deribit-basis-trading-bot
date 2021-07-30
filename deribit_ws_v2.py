import asyncio
import websockets
import json
import time
import logging
import os
import my_data
from derebit_ws import DeribitWS
from helpers import * 

class SimpleBasisBot:
    
    def __init__(self, parameters, test=False):
        self.parameters = parameters
        if test is False:
            self.uri = "wss://www.deribit.com/ws/api/v2"
        else:
            self.uri = 'wss://test.deribit.com/ws/api/v2' 
        self.is_working = False

        # self.ws = DeribitWS(my_data.client_id, my_data.client_secret, test=False)

        logging.basicConfig(level=logging.INFO, filename=f"SimpleBasisBot_{self.parameters['name']}",
                    format='%(asctime)s  %(levelname)s:  %(message)s' )
        self.log = logging.getLogger(__name__)
        self.log.info(f"Creating SimpleBasisBot with params {get_parameters_table(parameters, '')}")

    async def start(self):
        self.log.info(f"Starting bot with name {self.parameters['name']}")
        self.basis = None
        self.last_base_price = None
        self.last_other_price = None
        async with websockets.connect(self.uri) as websocket:
            self.log.info(f"Socker is opened")
            data = {
                "method": "public/subscribe",
                "params": {
                "channels": [
                f"quote.{self.parameters['base_inst']}",
                f"quote.{self.parameters['other_inst']}"
                ]
                },
                "jsonrpc": "2.0",
                "id": 1
            }

            await websocket.send(json.dumps(data))

            make_trade = False
            while(websocket.open and make_trade is False):
                make_trade = self.calculating_basis(await websocket.recv())
                if make_trade:
                    start = time.time()
                    auth_creds = {
                        "jsonrpc" : "2.0",
                        "id" : 0,
                        "method" : "public/auth",
                        "params" : {
                            "grant_type" : "client_credentials",
                            "client_id" : my_data.client_id,
                            "client_secret" : my_data.client_secret
                        }
                    }
                    await websocket.send(json.dumps(auth_creds))

                    pair_base = self.parameters["base_inst"]
                    amount_base = self.parameters['base_amount']
                    side_base = self.parameters['base_side']
                    pair_other = self.parameters["other_inst"]
                    amount_other = self.parameters['other_amount']
                    side_other = self.parameters['other_side']
                    msg_base = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": f"private/{side_base}",
                        "params": {
                            "instrument_name" : pair_base,
                            "amount" : amount_base,
                            "type" : "market",
                            "grant_type" : "client_credentials",
                            "client_id" : my_data.client_id,
                            "client_secret" : my_data.client_secret
                        }
                    }
                    msg_other = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": f"private/{side_other}",
                        "params": {
                            "instrument_name" : pair_other,
                            "amount" : amount_other,
                            "type" : "market",
                            "grant_type" : "client_credentials",
                            "client_id" : my_data.client_id,
                            "client_secret" : my_data.client_secret
                        }
                    }

                    await websocket.send(json.dumps(msg_base))
                    response_base = await websocket.recv()

                    await websocket.send(json.dumps(msg_other))
                    response_other = await websocket.recv()

                    print(response_base)

                    print(f'Working time = {time.time() - start} sec')
                    print('Trade DONE')

    def calculating_basis(self, message):
        if "params" in message:
            data = json.loads(message)["params"]["data"]
            if data["instrument_name"] == self.parameters["base_inst"]:
                if self.parameters["base_side"] == "sell":
                    self.last_base_price = data["best_bid_price"]
                else:
                    self.last_base_price = data["best_ask_price"]
            else:
                if self.parameters["other_side"] == "sell":
                    self.last_other_price = data["best_bid_price"]
                else:
                    self.last_other_price = data["best_ask_price"]
            
            if self.last_base_price is not None and self.last_other_price is not None:
                self.basis = self.last_other_price - self.last_base_price
        
            if self.basis is not None:
                clear = lambda: os.system('clear')
                clear()
                print(f"Last_base_price: {self.last_base_price}\nLast_other_price: {self.last_other_price}\nBasis: {self.basis}")

                if self.parameters['base_sid'] == 'buy' and self.basis > self.parameters['basis']:
                    return True
                elif self.parameters['base_sid'] == 'sell' and self.basis < self.parameters['basis']:
                    return True
        return False

def main():
    bot = SimpleBasisBot({
        "name": "Test",
        "base_inst": "ETH-PERPETUAL",
        "other_inst": "ETH-24SEP21",
        "base_side": "sell",
        "other_side": "buy",
        "base_amount": 1.,
        "other_amount": 1.,
        "basis": 15.5,
    })
    # asyncio.get_event_loop().run_until_complete(bot.start())
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # loop.run_until_complete(bot.start())
    asyncio.run(bot.start())

if __name__ == "__main__":
    main()

