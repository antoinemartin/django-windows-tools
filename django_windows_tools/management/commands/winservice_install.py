# encoding: utf-8

# Django command installing a Windows Service that runs Django commands
#
# Copyright (c) 2012 Openance
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

from __future__ import print_function

__author__ = 'Antoine Martin <antoine@openance.com>'

import os
import sys
import platform
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import get_template


def set_file_readable(filename):
    import win32api
    import win32security
    import ntsecuritycon as con

    users = win32security.ConvertStringSidToSid("S-1-5-32-545")
    admins = win32security.ConvertStringSidToSid("S-1-5-32-544")
    user, domain, type = win32security.LookupAccountName("", win32api.GetUserName())

    sd = win32security.GetFileSecurity(filename, win32security.DACL_SECURITY_INFORMATION)

    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, users)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, user)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, admins)
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(filename, win32security.DACL_SECURITY_INFORMATION, sd)


class Command(BaseCommand):
    args = ''
    help = '''Creates an NT Service that runs Django commands.

    This command creates a service.py script and a service.ini
    configuration file at the same level that the manage.py command.
    
    The django commands configured in the service.ini file can
    then be run as a Windows NT service by installing the service with
    the command:
    
      C:\project> python service.py --startup=auto install
    
    It can be started with the command:
    
      C:\project> python service.py start
    
    It can be stopped and removed with one of the commands:
    
      C:\project> python service.py stop
      C:\project> python service.py remove        
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--service-name',
            dest='service_name',
            default='django-%s-service',
            help='Name of the service (takes the name of the project by default')
        parser.add_argument(
            '--display-name',
            dest='display_name',
            default='Django %s background service',
            help='Display name of the service')
        parser.add_argument(
            '--service-script-name',
            dest='service_script_name',
            default='service.py',
            help='Name of the service script (defaults to service.py)')
        parser.add_argument(
            '--config-file-name',
            dest='config_file_name',
            default='service.ini',
            help='Name of the service configuration file (defaults to service.ini)')
        parser.add_argument(
            '--log-directory',
            dest='log_directory',
            default=r'd:\logs',
            help=r'Location for log files (d:\logs by default)')
        parser.add_argument(
            '--beat-machine',
            dest='beat_machine',
            default='BEATSERVER',
            help='Name of the machine that will run the Beat scheduler')
        parser.add_argument(
            '--beat',
            action='store_true',
            dest='is_beat',
            default=False,
            help='Use this machine as host for the beat scheduler')
        parser.add_argument(
            '--overwrite',
            action='store_true',
            dest='overwrite',
            default=False,
            help='Overwrite existing files')

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.current_script = os.path.abspath(sys.argv[0])
        self.project_dir, self.script_name = os.path.split(self.current_script)
        self.project_name = os.path.split(self.project_dir)[1]

    def install_template(self, template_name, filename, overwrite=False, **kwargs):
        full_path = os.path.join(self.project_dir, filename)
        if os.path.exists(full_path) and not overwrite:
            raise CommandError('The file %s already exists !' % full_path)
        print("Creating %s " % full_path)
        template = get_template(template_name)
        file = open(full_path, 'w')
        file.write(template.render(kwargs))
        file.close()
        set_file_readable(full_path)

    def handle(self, *args, **options):
        if self.script_name == 'django-admin.py':
            raise CommandError("""\
This command does not work when used with django-admin.py.
Please run it with the manage.py of the root directory of your project.
""")

        if "%s" in options['service_name']:
            options['service_name'] = options['service_name'] % self.project_name

        if "%s" in options['display_name']:
            options['display_name'] = options['display_name'] % self.project_name

        self.install_template(
            'windows_tools/service/service.py',
            options['service_script_name'],
            options['overwrite'],
            service_name=options['service_name'],
            display_name=options['display_name'],
            config_file_name=options['config_file_name'],
            settings_module=os.environ['DJANGO_SETTINGS_MODULE'],
        )

        if options['is_beat']:
            options['beat_machine'] = platform.node()

        if options['log_directory'][-1:] == '\\':
            options['log_directory'] = options['log_directory'][0:-1]

        self.install_template(
            'windows_tools/service/service.ini',
            options['config_file_name'],
            options['overwrite'],
            log_directory=options['log_directory'],
            beat_machine=options['beat_machine'],
            config_file_name=options['config_file_name'],
            settings_module=os.environ['DJANGO_SETTINGS_MODULE'],
        )


if __name__ == '__main__':
    print('This is supposed to be run as a django management command')
