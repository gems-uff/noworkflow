# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content database engine parallel generics"""

def create_distributed(cls, name=None):
    from multiprocessing import Process, JoinableQueue, cpu_count, Manager, Lock
    from . import safeopen
    class Worker(Process):

        def __init__(self, task_queue, engine):
            with safeopen.use_safe_open():
                Process.__init__(self)
                self.task_queue = task_queue
                self.engine = engine
            

        def run(self):
            while True:
                queue_content = self.task_queue.get()
                if queue_content is None:
                    # Poison pill means shutdown
                    self.task_queue.task_done()
                    break

                self.engine.do_put(*queue_content)
                self.task_queue.task_done()


    class Distributed(cls):

        def __init__(self, config):
            super(Distributed, self).__init__(config)
            self.tasks = None
            self.consumers = []
            self.num_consumers = None
            self.processes_started = False
            self.manager = Manager()
            self.object_hashes = self.manager.dict()
            self.lock = self.manager.RLock()

        def start_processes(self):
            """Start processes"""
            self.tasks = JoinableQueue()
            self.object_hashes = self.manager.dict()
            self.num_consumers = cpu_count()
            self.processes_started = True
            self.consumers = []
            with safeopen.use_safe_open():
                for _ in range(self.num_consumers):
                    consumer = Worker(self.tasks, self)
                    self.consumers.append(consumer)
                    consumer.start()

        def put(self, content, filename="generic"):  # pylint: disable=method-hidden
            """Put content in the content database"""
            if not self.processes_started:
                self.start_processes()

            self.tasks.put(self.put_attr(content, filename))
            content_hash = self._get_hash_from_content(content)
            return content_hash

        def close(self):
            """Join and close processes"""
            if self.processes_started:
                # Add a poison pill for each consumer
                for _ in range(self.num_consumers):
                    self.tasks.put(None)

                # Wait for all of the tasks to finish
                self.tasks.join()
                self.processes_started = False
        
    Distributed.__name__ = name or ("Distributed" + cls.__name__)
    return Distributed


def create_pool(cls, name=None):
    from multiprocessing import cpu_count, Manager, Pool, Lock
    from . import safeopen

    class ProcessingPool(cls):

        def __init__(self, config):
            super(ProcessingPool, self).__init__(config)
            self.pool = None
            self.manager = Manager()
            self.object_hashes = self.manager.dict()
            self.processes_started = False
            self.lock = self.manager.RLock()

        def start_processes(self):
            """Start processes"""
            with safeopen.use_safe_open():
                self.object_hashes = self.manager.dict()
                self.pool = Pool(cpu_count())
                self.processes_started = True

        def put(self, content, filename="generic"):  # pylint: disable=method-hidden
            """Put content in the content database"""
            if not self.processes_started:
                self.start_processes()

            self.pool.apply_async(self.do_put, self.put_attr(content, filename))
            content_hash = self._get_hash_from_content(content)
            return content_hash

        def close(self):
            """Join and close processes"""
            if self.processes_started:
                self.pool.close()
                self.pool.join()
                self.processes_started = False
        
    ProcessingPool.__name__ = name or ("Pool" + cls.__name__)
    return ProcessingPool


def create_threading(cls, name=None):
    import threading
    import sys
    class Threading(cls):

        def __init__(self, config):
            super(Threading, self).__init__(config)
            self.persistence_threads = []
            self.lock = threading.Lock()

        def put(self, content, filename="generic"):  # pylint: disable=method-hidden
            """Put content in the content database"""
            t = threading.Thread(target=self.do_put, args=self.put_attr(content, filename))
            self.persistence_threads.append(t)
            t.start()
            content_hash = self._get_hash_from_content(content)
            return content_hash

        def close(self):
            """Join and close threads"""
            for t in self.persistence_threads:
                t.join()
            
            self.persistence_threads = []

    Threading.__name__ = name or ("Threading" + cls.__name__)
    return Threading
        

class NullLock(object):

    def acquire(self, block=False):
        return True

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        return None
