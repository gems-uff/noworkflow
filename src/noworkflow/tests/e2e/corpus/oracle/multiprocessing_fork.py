"""External processes: multiprocessing with the fork start method

A forked Process runs a function of the script, once writing a file that
the script reads back, and sends a value back through a Queue; a Pool
maps a function of the script. The fork start method is chosen
explicitly (the default is spawn on macOS and Windows, forkserver on
Linux from 3.14, which fail under ``now run``: #325, #334) and does not
exist on Windows. Every wait on a child is bounded by TIMEOUT seconds, so
that a child that dies or hangs fails the script instead of hanging it:
the Queue's get, the join of each Process (a child still running then is
killed, and the script stops on any exit code but 0), the Pool's results
(a worker that dies takes its task with it) and, once every task came
back, the join of the closed Pool, which takes no timeout of its own: a
helper thread runs it, and the script stops when the thread still waits
after TIMEOUT seconds. One wait has no bound: on the way out of its with
block the Pool terminates its workers (SIGTERM, which nothing here
handles) and joins them, which only waits when the helper thread timed
out. Split out: a direct os.fork()
(fork_child_exit_status.py, fork_with_threads_warning.py). Left out: a
target that raises, whose traceback multiprocessing prints on stderr,
under ``now run`` with the collector's frames (#271) and the context of
if_body_exception_context.py (the target runs inside the body of
``if __name__ == "__main__"``).
"""
import multiprocessing
import os
import threading

TIMEOUT = 60


def work(label, path, queue):
    total = sum(range(10))
    print("child", label, "total", total, flush=True)
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("written by {}\n".format(label))
    queue.put((label, total))


def square(number):
    return number * number


if __name__ == "__main__":
    context = multiprocessing.get_context("fork")
    queue = context.Queue()
    os.makedirs("out", exist_ok=True)
    print("parent: start", flush=True)
    for label, path in (("plain", None), ("writer", "out/fork.txt")):
        process = context.Process(target=work, args=(label, path, queue))
        process.start()
        try:
            print("received:", queue.get(timeout=TIMEOUT))
            process.join(TIMEOUT)
        finally:
            if process.exitcode is None:
                process.kill()
                process.join(TIMEOUT)
        print("exit code:", process.exitcode, flush=True)
        if process.exitcode != 0:
            raise RuntimeError("child {} failed".format(label))
    with open("out/fork.txt", encoding="utf-8") as handle:
        print("file:", repr(handle.read()))
    with context.Pool(2) as pool:
        squares = pool.map_async(square, range(6))
        print("pool:", squares.get(timeout=TIMEOUT))
        pool.close()
        joiner = threading.Thread(target=pool.join, daemon=True)
        joiner.start()
        joiner.join(TIMEOUT)
        if joiner.is_alive():
            raise RuntimeError("the pool's workers did not exit")
    print("parent: done")
