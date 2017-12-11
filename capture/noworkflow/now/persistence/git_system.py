import subprocess
import os


def is_git_installed():
    try:
        p = subprocess.Popen("git")
        p.kill()
        return True
    except OSError:
        return False


def init(path):
    p = subprocess.Popen(["git", "init", path],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        raise OSError(err.decode())
    elif out:
        return out


def put(content, git_path):
    p = subprocess.Popen(["git", "hash-object", "-w", "--stdin"], cwd=git_path,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, err = p.communicate(content)
    return out.decode().replace("\n", "")


def get(content_hash, git_path):
    p = subprocess.Popen(["git", "cat-file", "-p", content_hash], cwd=git_path, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if err:
        raise OSError(err.decode())
    elif out:
        return out


def update_index(content_hash, git_path):
    p = subprocess.Popen(["git", "update-index", "--add", "--cacheinfo", "100644", content_hash, content_hash],
                         cwd=git_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    p.kill()
    if err:
        raise OSError(err.decode())
    elif out:
        return out


def write_tree(git_path):
    p = subprocess.Popen(["git", "write-tree"], cwd=git_path,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    p.kill
    if err:
        raise OSError(err.decode())
    elif out:
        return out.decode().replace("\n", "")


def commit_tree_parent(tree_hash, parent_commit_hash, commit_message, git_path):
    p = subprocess.Popen(["git", "commit-tree", tree_hash, "-p", parent_commit_hash,
                          "-m", commit_message], cwd=git_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    p.kill()
    if err:
        raise OSError(err.decode())
    elif out:
        return out.decode().replace("\n", "")


def commit_tree(git_path, tree_hash, commit_message):
    p = subprocess.Popen(["git", "commit-tree", tree_hash, "-m", commit_message],
                         cwd=git_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    p.wait()
    if err:
        raise OSError(err.decode())
    elif out:
        return out.decode().replace("\n", "")


def garbage_collection(git_path):
    p = subprocess.Popen(['git gc', '--quiet'], cwd=git_path, shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    p.wait()
    if err:
        raise OSError(err.decode())


def count_loose_objects(git_path):
    p = subprocess.Popen(["git", "count-objects", "-v"], cwd=git_path,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    p.kill()
    if err:
        raise OSError(err.decode())
    if out:
        return out.decode().strip().split("\n")[0].split(": ")[1]
