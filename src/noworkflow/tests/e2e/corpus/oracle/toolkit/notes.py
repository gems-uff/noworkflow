"""Notes saved to a file, imported by open_files_kept_alive.py"""


def save(path, text):
    open(path, "w", encoding="utf-8").write(text)
