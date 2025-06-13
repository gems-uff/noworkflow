import os
import subprocess
from pathlib import Path
from time import sleep

PACKAGES = Path('packages')

class Module:

    def __init__(self, name, path=None, files=None, dependencies=None):
        self.name = name
        if path is None:
            path = PACKAGES / name
        self.path = path
        self.files = files or ["src/", "style/"]
        self.dependencies = dependencies or []
        self.old_sum = 0

    def check_dir(self):
        pass

    def run(self):
        pass

    def check(self, run=True, visited={}):
        """Check if the module or its dependencies has changed"""
        if self in visited:
            return visited[self]
        visited[self] = True
        invalid = False
        for dependency in self.dependencies:
            if not dependency.check(run, visited):
                invalid = True

        invalid |= self.check_dir()

        if run and invalid:
            visited[self] = False
            self.run()

        return not invalid

    def __hash__(self):
        return hash(self.path)

    def __repr__(self):
        return "Module({})".format(self.name)


class FileModule(Module):

    def __init__(self, name, package_name, path=None, files=None, dependencies=None):
        super().__init__(name, path=path, files=files, dependencies=dependencies)
        self.package_name = package_name
    
    def check_dir(self):
        """Check if a file has changed in the package"""
        time_list = []
        for file in self.files:
            file_list = []
            file_path = self.path / Path(file)
            if not file.endswith("/"):
                file_list = [file_path]
            else:
                for root, _, files in os.walk(file_path):
                    root = Path(root)
                    file_list += [root / f for f in files]

            time_list += [os.stat(f).st_mtime for f in file_list]

        new_sum = sum(time_list)
        result = new_sum != self.old_sum
        self.old_sum = new_sum
        return result

    def run(self):
        print("Building", self.name)
        process = subprocess.Popen(
            f"npx lerna run build --scope={self.package_name}",
            shell=True,
            #cwd=self.path,
        )

        status = process.wait()
        if status:
            raise Exception("NPM run failed")


class NoFileModule(Module):

    def check_dir(self):
        return False

    def run(self):
        pass


utils = FileModule("utils", "@noworkflow/utils")
history = FileModule("history", "@noworkflow/history", dependencies=[utils])
trial = FileModule("trial", "@noworkflow/trial", dependencies=[utils])
nowvis = FileModule("nowvis", "@noworkflow/nowvis", dependencies=[history, trial])
labextension = FileModule("labextension", "@noworkflow/labextension", dependencies=[history, trial])

ALL = NoFileModule("ALL", dependencies=[nowvis, labextension])
# Disable labextension for now
ALL = NoFileModule("ALL", dependencies=[nowvis])


print("Monitoring packages...")
while True:
    visited = {}
    try:
        ALL.check(visited=visited)
    except Exception as e:
        print("Failed: {}".format(e))
    sleep(1.0)
