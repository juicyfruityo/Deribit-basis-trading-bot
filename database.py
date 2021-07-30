import websocket, json
import psycopg2
from my_data import *
import derebit_ws
socket = 'wss://www.deribit.com/ws/api/v2'
added_rows = 1
con = psycopg2.connect(
                host="127.0.0.1",
                database="future-prices",
                user = "pigerloafer",
                password = "12345")

cur = con.cursor()

def on_open(ws):
    print("Opened")
    der_ws = derebit_ws.DeribitWS(r_client_id, r_clietn_secret, test=False)
    channels = list([f"quote.{channel}" for channel in der_ws.available_instruments("ETH") + der_ws.available_instruments("BTC")])
    data = {
    "method": "public/subscribe",
    "params": {
    "channels": channels
    },
    "jsonrpc": "2.0",
    "id": 15
}
    print(json.dumps(data))
    ws.send(json.dumps(data))


def on_message(ws, message):
    global added_rows
    js = json.loads(message)
    data = js["params"]["data"]
    cur.execute('insert into "BestBidAsks" (instrument, timestamp, best_bid, best_bid_size, best_ask, best_ask_size) values (%s, %s, %s, %s, %s, %s)',
    (data["instrument_name"], data["timestamp"], float(data["best_bid_price"]), float(data["best_bid_amount"]), float(data["best_ask_price"]), float(data["best_ask_amount"])))
    added_rows += 1
    if added_rows % 1000 == 0:
        print("Commiting to database")
        con.commit()
        added_rows = 1
    # print("="*50)
    # print(f'instrument: {data["instrument_name"]}')
    # print(f'timestamp: {data["timestamp"]}')
    # print(f'best_bid_price: {data["best_bid_price"]}')
    # print(f'best_ask_price: {data["best_ask_price"]}')
    # print("="*50)

ws = websocket.WebSocketApp(socket, on_open=on_open, on_message=on_message)
# der_ws = derebit_ws.DeribitWS(r_client_id, r_clietn_secret, test=False)
# print(der_ws.available_instruments("ETH"))
# for i in range(24):
while True:
    ws.run_forever()
# cur.execute('insert into "BestBidAsks" (instrument, timestamp, best_bid, best_bid_size, best_ask, best_ask_size) values (%s, %s, %s, %s, %s, %s)',
# ("ETH-PERPETUAL", 1001301031210, 1.01, 0.1, 2.01, 0.2))