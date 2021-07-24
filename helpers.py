import pandas as pd
import requests

def datetime_to_unix(datetime):
    '''
    datetime - в формате "2021-03-21 13:10:08" %Y-%m-%d %H:%M:%S

    '''
    datetime = pd.to_datetime(datetime)
    unixtime = (datetime - pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')

    return unixtime

def unix_to_datetime(unixtime):
    '''
    unixtime - в секундах

    '''
    datetime = pd.to_datetime(unixtime, unit='s', origin='unix')
    
    return datetime

def get_parameters_table(params, next_line):
    s = "```\n"
    s += "Bot's current parameters:\n"
    s += "x" + 26 * "-" + "x" + "\n"
    for key in params:
        val = params[key] if params[key] is not None else "?"
        s += "|{:<12} {:<13}|".format(key, val)
        s += "\n"
    s += "x" + 26 * "-" + "x" + "\n"
    s += next_line
    # print(s)
    return s + "```"  

def tg_logging(bot_message, markdown=False):

    bot_token = "1861690516:AAGtrzfJdLPruv93ZKHHUIXThVHqHRAiYoU"
    bot_chatID = "-1001526300280"
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={bot_chatID}&text={bot_message}'
    if markdown:
        url += '&parse_mode=MarkdownV2'
    response = requests.get(url)
    return response.json()