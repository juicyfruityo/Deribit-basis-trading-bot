import asyncio
import websockets
import json
import time
import logging
import os
from helpers import * 

class SimpleBasisBot:
    
    def __init__(self, parameters, test="False"):
        self.parameters = parameters
        if test:
            self.uri = "wss://www.deribit.com/ws/api/v2"
        else:
            self.uri = 'wss://test.deribit.com/ws/api/v2' 
        self.is_working = False

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
            while(websocket.open):
                self.calculating_basis(await websocket.recv())

    def calculating_basis(self, message):
        if "params" in message:
            data = json.loads(message)["params"]["data"]
            if data["instrument_name"] == self.parameters["base_inst"]:
                if self.parameters["base_side"] == "sell":
                    self.last_base_price = data["best_ask_price"]
                else:
                    self.last_base_price = data["best_bid_price"]
            else:
                if self.parameters["other_side"] == "sell":
                    self.last_other_price = data["best_ask_price"]
                else:
                    self.last_other_price = data["best_bid_price"]
            
            if self.last_base_price is not None and self.last_other_price is not None:
                self.basis = self.last_base_price - self.last_other_price
        
            if self.basis is not None:
                clear = lambda: os.system('clear')
                clear()
                print(f"Last_base_price: {self.last_base_price}\nLast_other_price: {self.last_other_price}\nBasis: {self.basis}")

def main():
    bot = SimpleBasisBot({
        "name": "Test",
        "base_inst": "ETH-PERPETUAL",
        "other_inst": "ETH-24SEP21",
        "base_side": "buy",
        "other_side": "sell",
        "base_amount": 10. ,
        "other_amount": 10. ,
        "basis": 15,
    })
    asyncio.get_event_loop().run_until_complete(bot.start())

if __name__ == "__main__":
    main()

