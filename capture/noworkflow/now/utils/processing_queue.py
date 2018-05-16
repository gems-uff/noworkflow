import multiprocessing
import time


class Consumer(multiprocessing.Process):

    def __init__(self, task_queue, repo):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.repo = repo

    def run(self):
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                self.task_queue.task_done()
                break
            next_task(self.repo)
            self.task_queue.task_done()
        return
