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

def dict_to_str(d):
    s = "\n"
    for key in d:
        s += f'{key}: {d[key]}\n'
    return s