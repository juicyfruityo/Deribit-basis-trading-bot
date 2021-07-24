from telegram_bot import *

def main():
    # tb.polling(none_stop=True, interval=1, timeout=100)
    try:
        tb.polling(none_stop=True, interval=1, timeout=100)
    except KeyboardInterrupt:
        # Требуется два раза подряд нажать CTRL-C
        tb.stop_bot()
        print('Telegram Bot Closed')
    except Exception as e:
        print(f'New Exception Raised:   {e}')

if __name__ == '__main__':
    main()