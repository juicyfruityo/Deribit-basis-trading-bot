import websocket, json
socket = 'wss://www.deribit.com/ws/api/v2'

def on_open(ws):
    print("Opened")
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


def on_message(ws, message):
    data = json.loads(message)
    # print(data)
    print("="*50)
    print(f'best_bid_price: {data["params"]["data"]["best_bid_price"]}\nbest_ask_price: {data["params"]["data"]["best_ask_price"]}')
    print("="*50)

ws = websocket.WebSocketApp(socket, on_open=on_open, on_message=on_message)

ws.run_forever()