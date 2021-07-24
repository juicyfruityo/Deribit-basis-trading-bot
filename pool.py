import multiprocessing as mp
from threading import Thread
import time

class Pool:
    def __init__(self):
        self.max_number_of_workers = mp.cpu_count()
        self.workers = {}
        self.terminate_pool = False

        self.t = Thread(target=self.getting_message)
        self.t.start()
    
    def start_worker(self, bot):
        if len(self.workers) == self.max_number_of_workers or bot.name in self.workers:
            print("Can't start worker.")
            return
        bot.is_running = True
        message_queue = mp.Queue()
        self.workers[bot.name] = (mp.Process(target=bot.start_bot, args=(message_queue,)), message_queue)
        self.workers[bot.name][0].start()

    def terminate_worker(self, bot):
        if bot.name not in self.workers:
            return
        self.workers[bot.name][0].terminate()
        self.workers.pop(bot.name)
        bot.is_running = False
    
    def getting_message(self):
        while(not self.terminate_pool):
            joined_workers = []
            for name in self.workers:
                process, queue = self.workers[name]
                if queue.get() == "done":
                    print(f"Bot {name} done trading.")
                    process.join()
                    joined_workers.append(name)

            if len(joined_workers) != 0:
                self.workers.pop(*joined_workers)
            time.sleep(1)
        self.t.join()