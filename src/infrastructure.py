import os
import socket
import utils
import platform

metadata = {}

metadata['environment variables'] = os.environ
metadata['current directory'] = os.getcwd()
metadata['user'] = os.getlogin()
metadata['process'] = os.getpid()
metadata['operating system name'], thresh, metadata['operating system release'], metadata['operating system version'], thresh = os.uname()
metadata['hostname'] = socket.gethostname()

sysconf = {}
for name in os.sysconf_names:
    sysconf[name] = os.sysconf(name)
for name in os.confstr_names:
    sysconf[name] = os.confstr(name)
metadata['system configuration'] = sysconf

metadata['architecture'] = platform.architecture()[0]
metadata['processor'] = platform.processor()
metadata['python implementation'] = platform.python_implementation()
metadata['python version'] = platform.python_version()


# Processor load. Should be collected from time to time (there are static and dynamic metadata)
# print os.getloadavg()

utils.pp(metadata)