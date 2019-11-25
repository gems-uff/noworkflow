import subprocess
import os

def execute(cmd, default=None, **kwargs):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    out = p.communicate()[0]
    returncode = p.wait()
    if returncode != 0:
        if default is None:
            print(out)
            raise subprocess.CalledProcessError(returncode, cmd)
        else:
            return default
    return out

def is_git_installed():
    try:
        p = subprocess.Popen("git")
        p.wait()
        return True
    except OSError:
        return False


def init(path):
    cmd = ["git", "init", "--bare", path]
    return execute(cmd)


def hash_object(content, git_path):
    cmd = ["git", "hash-object", "-w", "--stdin"]
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        stdin=subprocess.PIPE, cwd=git_path)
    out = p.communicate(content)[0]
    returncode = p.wait()
    if returncode != 0:
        print(out)
        raise subprocess.CalledProcessError(returncode, cmd)
    return out.decode().replace("\n", "")

def get(content_hash, git_path):
    cmd = ["git", "cat-file", "-p", content_hash]
    return execute(cmd, cwd=git_path)    


def update_index(mode, content_hash, filename, git_path):
    cmd = ["git", "update-index", "--add", "--cacheinfo", mode, content_hash, filename]
    return execute(cmd, cwd=git_path)


def write_tree(git_path):
    cmd = ["git", "write-tree"]
    return execute(cmd, cwd=git_path).decode().replace("\n", "")


def read_tree(filename, content_hash, git_path):
    cmd = ["git", "read-tree", "--prefix={}".format(filename), content_hash]
    return execute(cmd, cwd=git_path).decode().replace("\n", "")


def cat_file(content_hash, git_path):
    cmd = ["git", "cat-file", "-p", content_hash]
    return execute(cmd, cwd=git_path).decode()


def rm_all(git_path):
    cmd = ["git", "rm", "-r", "--cached", "."]
    return execute(cmd, cwd=git_path, default=b"").decode()



def commit_tree(tree_hash, commit_message, git_path, author=None, parent=None):
    if not commit_message:
        commit_message = "<empty>"
    cmd = ["git", "commit-tree", tree_hash, "-m", commit_message]
    if parent:
        cmd.append("-p")
        cmd.append(parent)
    env = os.environ
    if author:
        env = env.copy()
        env["GIT_AUTHOR_NAME"], env["GIT_AUTHOR_EMAIL"] = author
    return execute(cmd, cwd=git_path, env=env).decode().replace("\n", "")


def garbage_collection(git_path, aggressive=False):
    cmd = ["git gc", "--quiet"]
    if aggressive:
        cmd.append("--aggressive")
    execute(cmd, cwd=git_path, shell=True)


def count_loose_objects(git_path):
    cmd = ["git", "count-objects", "-v"]
    return execute(cmd, cwd=git_path).decode().strip().split("\n")[0].split(": ")[1]


def all_objects(git_path):
    cmd = ["git", "rev-list", "--objects", "--all"]
    out = execute(cmd, cwd=git_path)
    if out:
        return [x.strip() for x in out.split() if x.strip()]
    return []


def show_ref(ref, git_path):
    cmd = ["git", "show-ref", ref]
    result = execute(cmd, cwd=git_path, default=b"").decode().strip()
    if result:
        return result.split()[0]
    return None

def update_ref(ref, tree, git_path):
    cmd = ["git", "update-ref", ref, tree]
    return execute(cmd, cwd=git_path)
