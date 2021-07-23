import pandas as pd

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

def bot_params(params, next_line):
    s = "```\n"
    s += "Bot's current parameters:\n"
    s += "x" + 36 * "-" + "x" + "\n"
    for key in params:
        if params[key] is not None:
            s += "|{:<20} {:>15}|".format(key, params[key])
            s += "\n"
    s += "x" + 36 * "-" + "x" + "\n"
    s += next_line
    # print(s)
    return s + "```"  