import win32serviceutil
import os, sys, platform
from os.path import abspath, dirname

import win32service
import win32event
import win32con
import win32file
from multiprocessing import Process
from multiprocessing.util import get_logger
import multiprocessing.forking
import logging
import ConfigParser
import ctypes
import traceback

GenerateConsoleCtrlEvent = ctypes.windll.kernel32.GenerateConsoleCtrlEvent


# Get the path of the Django Application. This script is supposed to be living 
# in a `service` subdirectory of the project root
base_path = dirname(dirname(abspath(__file__)))

old_get_preparation_data = multiprocessing.forking.get_preparation_data

# Monkey patch the Windows Process implementation to avoid thinking
# That 'PythonService.exe' is a python script
def new_get_preparation_data(name):
    d = old_get_preparation_data(name)
    if d.has_key('main_path') and d['main_path'].lower().endswith('.exe'):
        del d['main_path']
    return d
    
multiprocessing.forking.get_preparation_data = new_get_preparation_data

def log(msg):
    '''Log a message in the Event Viewer as an informational message'''
    import servicemanager
    servicemanager.LogInfoMsg(str(msg))

def error(msg):
    '''Log a message in the Event Viewer as an error message'''
    import servicemanager
    servicemanager.LogErrorMsg(str(msg))
    
def initialize_logger(config):
    class StdErrWrapper:
        """
            Call wrapper for stderr
        """
        def write(self, s):
            get_logger().info(s)
    import logging
    
    logger = get_logger()
    values = dict(
        format = '[%(levelname)s/%(processName)s] %(message)s',
        filename = None,
        level = 'INFO',
    )
    if config and config.has_section('log'):
        for (name,value) in config.items('log'):
            values[name] = value
        
    if values['filename']:
        formatter = logging.Formatter(values['format'])
        handler = logging.FileHandler(values['filename'])
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, values['level'].upper(), logging.INFO))
        sys.stderr = StdErrWrapper()
    

def start_django_command(config, args):
    '''
    Start a Django management command.
    
    This commands is supposed to start in a spawned (child process).
    It tries to import the settings of the project before handling the command.
    '''
    from django.core.handlers.modpython import handler

    sys.path.append(base_path)
    
    initialize_logger(config)
    
    try:
        import settings # Assumed to be in the base path.
    except ImportError:
        import servicemanager
        error("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
        sys.exit(1)
    from django.core.management import execute_manager
    
    log('Starting command : %s' % ' '.join(args))
    get_logger().info('Starting command : %s' % ' '.join(args))
    try:
        execute_manager(settings, args)
    except:
        error('Exception occured : %s' % traceback.format_exc())
    
def spawn_command(config, server_name):
    '''
    Spawn a command specified in a configuration file and return the process object.
    '''
    args = [__file__]
    args.append(config.get(server_name, 'command'))
    args += config.get(server_name, 'parameters').split()
    process = Process(target=start_django_command, args=(config, args,))
    process.start()
    log('Spawned %s' % ' '.join(args))
    return process


def start_commands(config):
    '''
    Spawn all the commands specified in a configuration file and return an array containing all the processes.
    '''
    processes = []
    node_name = platform.node()
    services = config.get(node_name, 'run') if config.has_section(node_name) else config.get('services', 'run')
    for server_name in services.split():
        processes.append(spawn_command(config, server_name))
    
    return processes
    
def end_commands(processes):
    '''
    Terminate all the processes in the specified array.
    '''
    for process in processes:
        #GenerateConsoleCtrlEvent(1, process.pid)
        process.terminate()
        process.join()

def test_commands():
    '''
    Method to test the spawn and termination of commands present in the configuration file.
    '''
    config = read_config()
    initialize_logger(config)
    processes = start_commands(config)
    import time
    time.sleep(1000)
    end_commands(processes)
    
def get_config_modification_handle():
    '''Returns a handle Directory change handle on the script directory.
    
    This handle will be used to restart the Django commands child processes
    in case some file has changed in the directory.
    '''
    path = dirname(abspath(__file__))
    change_handle = win32file.FindFirstChangeNotification (
        path,
        0,
        win32con.FILE_NOTIFY_CHANGE_LAST_WRITE
    )
    return change_handle


def read_config():
    '''
    Reads the configuration file containing spawned processes information
    '''
    config = ConfigParser.ConfigParser()
    config.optionxform = str
    path = os.path.join(dirname(abspath(__file__)), 'configuration.ini')
    log(path)
    config.read(path)
    return config
    
class DjangoService(win32serviceutil.ServiceFramework):
    """NT Service."""

    _svc_name_ = "django-service"
    _svc_display_name_ = "Django Background Processes"
    _svc_description_ = "Run the Django background Processes"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        log('Initialization')
        # create an event that SvcDoRun can wait on and SvcStop
        # can set.
        self.config = read_config()        
        initialize_logger(self.config)
        sys.path.append(base_path)
        sys.path.append(dirname(base_path))
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        log('starting')
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        
        self.modification_handle = get_config_modification_handle()
        
        keep_running = True
        while keep_running:

            # do the actual start
            self.start()
            
            log('Started. Waiting for stop')
            index = win32event.WaitForMultipleObjects([self.stop_event, self.modification_handle], False, win32event.INFINITE)
            if index == 0:
                # The stop event has been signaled. Stop execution.
                keep_running = False
            else:
                log('Restarting child processes as the configuration has changed')
                win32file.FindNextChangeNotification(self.modification_handle)
                self.stop()
                
        win32file.FindCloseChangeNotification(self.modification_handle)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        log('Stopping')
        # Do the actual stop 
        self.stop()
        log('Stopped')
        win32event.SetEvent(self.stop_event)
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        
    def start(self):
        self.processes = start_commands(self.config)
        
    def stop(self):
        if self.processes:
            end_commands(self.processes)
            self.processes = []
        node_name = platform.node()
        clean = self.config.get(node_name, 'clean') if self.config.has_section(node_name) else self.config.get('services', 'clean')
        if clean:
            for file in clean.split(';'):
                try:
                    os.remove(file)
                except:
                    error("Error while removing %s\n%s" % (file, traceback.format_exc()))
            
    
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_commands()
    else:
        win32serviceutil.HandleCommandLine(DjangoService)
