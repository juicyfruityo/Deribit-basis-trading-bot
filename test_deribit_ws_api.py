import websocket, json
from threading import Thread
import time


def on_open1(ws):
    print("Opened1")
    data = {
    "method": "public/subscribe",
    "params": {
    "channels": [
        "quote.ETH-PERPETUAL",
    ]
    },
    "data": "ETH-PERPETUAL",
    "jsonrpc": "2.0",
    "id": 15
}

    ws.send(json.dumps(data))

def on_open2(ws):
    print("Opened2")
    data = {
        "method": "public/subscribe",
        "params": {
        "channels": [
            "quote.ETH-PERPETUAL",
        ]
        },
        "data": "ETH-PERPETUAL",
        "jsonrpc": "2.0",
        "id": 15
    }

    ws.send(json.dumps(data))


def on_message1(ws, message):
    data = json.loads(message)
    # print(data)
    print("="*50 + "1")
    print(f'best_bid_price: {data["params"]["data"]["best_bid_price"]}\nbest_ask_price: {data["params"]["data"]["best_ask_price"]}')
    # print("="*50 + "1")

def on_message2(ws, message):
    data = json.loads(message)
    # print(data)
    print("="*50 + "2")
    print(f'best_bid_price: {data["params"]["data"]["best_bid_price"]}\n best_ask_price: {data["params"]["data"]["best_ask_price"]}')
    # print("="*50 + "2")

def on_close(ws):
    print('closed connection')


socket = 'wss://www.deribit.com/ws/api/v2'
ws1 = websocket.WebSocketApp(socket, on_open=on_open1, on_message=on_message1, on_close=on_close)
t1 = Thread(target=ws1.run_forever)
ws2 = websocket.WebSocketApp(socket, on_open=on_open2, on_message=on_message2, on_close=on_close)
t2 = Thread(target=ws2.run_forever)
t1.start()
t2.start()

while True:
    time.sleep(1)