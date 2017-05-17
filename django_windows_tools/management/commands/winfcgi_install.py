# encoding: utf-8

# FastCGI Windows Server Django installation command
#
# Copyright (c) 2012 Openance SARL
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

import os
import os.path
import sys
import re
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import get_template
from django.conf import settings
import subprocess

__author__ = 'Antoine Martin <antoine@openance.com>'


def set_file_readable(filename):
    import win32api
    import win32security
    import ntsecuritycon as con

    WinBuiltinUsersSid = 27  # not exported by win32security. according to WELL_KNOWN_SID_TYPE enumeration from http://msdn.microsoft.com/en-us/library/windows/desktop/aa379650%28v=vs.85%29.aspx
    users = win32security.CreateWellKnownSid(WinBuiltinUsersSid)
    WinBuiltinAdministratorsSid = 26  # not exported by win32security. according to WELL_KNOWN_SID_TYPE enumeration from http://msdn.microsoft.com/en-us/library/windows/desktop/aa379650%28v=vs.85%29.aspx
    admins = win32security.CreateWellKnownSid(WinBuiltinAdministratorsSid)
    user, domain, type = win32security.LookupAccountName("", win32api.GetUserName())

    sd = win32security.GetFileSecurity(filename, win32security.DACL_SECURITY_INFORMATION)

    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, users)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, user)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.FILE_ALL_ACCESS, admins)
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(filename, win32security.DACL_SECURITY_INFORMATION, sd)


class Command(BaseCommand):
    args = '[root_path]'
    help = '''Installs the current application as a fastcgi application under windows.

    If the root path is not specified, the command will take the
    root directory of the project.
    
    Don't forget to run this command as Administrator
    '''

    CONFIGURATION_TEMPLATE = '''/+[fullPath='{python_interpreter}',arguments='{script} winfcgi --pythonpath={project_dir}',maxInstances='{maxInstances}',idleTimeout='{idleTimeout}',activityTimeout='{activityTimeout}',requestTimeout='{requestTimeout}',instanceMaxRequests='{instanceMaxRequests}',protocol='NamedPipe',flushNamedPipe='False',monitorChangesTo='{monitorChangesTo}']'''

    DELETE_TEMPLATE = '''/[arguments='{script} winfcgi --pythonpath={project_dir}']'''

    FASTCGI_SECTION = 'system.webServer/fastCgi'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            dest='delete',
            default=False,
            help='Deletes the configuration instead of creating it')
        parser.add_argument(
            '--max-instances',
            dest='maxInstances',
            default=4,
            help='Maximum number of pyhton processes')
        parser.add_argument(
            '--idle-timeout',
            dest='idleTimeout',
            default=1800,
            help='Idle time in seconds after which a python process is recycled')
        parser.add_argument(
            '--max-content-length',
            dest='maxContentLength',
            default=30000000,
            help='Maximum allowed request content length size')
        parser.add_argument(
            '--activity-timeout',
            dest='activityTimeout',
            default=30,
            help='Number of seconds without data transfer after which a process is stopped')
        parser.add_argument(
            '--request-timeout',
            dest='requestTimeout',
            default=90,
            help='Total time in seconds for a request')
        parser.add_argument(
            '--instance-max-requests',
            dest='instanceMaxRequests',
            default=10000,
            help='Number of requests after which a python process is recycled')
        parser.add_argument(
            '--monitor-changes-to',
            dest='monitorChangesTo',
            default='',
            help='Application is restarted when this file changes')
        parser.add_argument(
            '--site-name',
            dest='site_name',
            default='',
            help='IIS site name (defaults to name of installation directory)')
        parser.add_argument(
            '--binding',
            dest='binding',
            default='http://*:80',
            help='IIS site binding. Defaults to http://*:80')
        parser.add_argument(
            '--skip-fastcgi',
            action='store_true',
            dest='skip_fastcgi',
            default=False,
            help='Skips the FastCGI application installation')
        parser.add_argument(
            '--skip-site',
            action='store_true',
            dest='skip_site',
            default=False,
            help='Skips the site creation')
        parser.add_argument(
            '--skip-config',
            action='store_true',
            dest='skip_config',
            default=False,
            help='Skips the configuration creation')
        parser.add_argument(
            '--log-dir',
            dest='log_dir',
            default='',
            help=r'Directory for IIS logfiles (defaults to %SystemDrive%\inetpub\logs\LogFiles)')

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.appcmd = os.path.join(os.environ['windir'], 'system32', 'inetsrv', 'appcmd.exe')
        self.current_script = os.path.abspath(sys.argv[0])
        self.project_dir, self.script_name = os.path.split(self.current_script)
        self.python_interpreter = sys.executable
        self.last_command_error = None

    def config_command(self, command, section, *args):
        arguments = [self.appcmd, command, section]
        arguments.extend(args)
        # print ' '.join(arguments)
        return subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def run_config_command(self, command, section, *args):
        command_process = self.config_command(command, section, *args)
        (out, err) = command_process.communicate()
        result = command_process.returncode == 0
        self.last_command_error = out if not result else None
        return result

    def check_config_section_exists(self, section_name):
        return self.run_config_command('list', 'config', '-section:%s' % section_name)

    def create_fastcgi_section(self, options):
        template_options = options.copy()
        template_options['script'] = self.current_script
        template_options['project_dir'] = self.project_dir
        template_options['python_interpreter'] = self.python_interpreter
        param = self.CONFIGURATION_TEMPLATE.format(**template_options)
        return self.run_config_command('set', 'config', '-section:%s' % self.FASTCGI_SECTION, param, '/commit:apphost')

    def delete_fastcgi_section(self):
        template_options = dict(script=self.current_script, project_dir=self.project_dir)
        param = self.DELETE_TEMPLATE.format(**template_options)
        return self.run_config_command('clear', 'config', '-section:%s' % self.FASTCGI_SECTION, param,
                                       '/commit:apphost')

    def install(self, args, options):
        if os.path.exists(self.web_config) and not options['skip_config']:
            raise CommandError('A web site configuration already exists in [%s] !' % self.install_dir)

        # now getting static files directory and URL
        static_dir = os.path.normcase(os.path.abspath(getattr(settings, 'STATIC_ROOT', '')))
        static_url = getattr(settings, 'STATIC_URL', '/static/')

        static_match = re.match('^/([^/]+)/$', static_url)
        if static_match:
            static_is_local = True
            static_name = static_match.group(1)
            static_needs_virtual_dir = static_dir != os.path.join(self.install_dir, static_name)
        else:
            static_is_local = False

        if static_dir == self.install_dir and static_is_local:
            raise CommandError('''\
The web site directory cannot be the same as the static directory,
for we cannot have two different web.config files in the same
directory !''')

        # create web.config
        if not options['skip_config']:
            print("Creating web.config")
            template = get_template('windows_tools/iis/web.config')
            file = open(self.web_config, 'w')
            file.write(template.render(self.__dict__))
            file.close()
            set_file_readable(self.web_config)

        if options['monitorChangesTo'] == '':
            options['monitorChangesTo'] = os.path.join(self.install_dir, 'web.config')

        # create FastCGI application
        if not options['skip_fastcgi']:
            print("Creating FastCGI application")
            if not self.create_fastcgi_section(options):
                raise CommandError(
                    'The FastCGI application creation has failed with the following message :\n%s' % self.last_command_error)

        # Create sites
        if not options['skip_site']:
            site_name = options['site_name']
            print("Creating application pool with name %s" % site_name)
            if not self.run_config_command('add', 'apppool', '/name:%s' % site_name):
                raise CommandError(
                    'The Application Pool creation has failed with the following message :\n%s' % self.last_command_error)

            print("Creating the site")
            if not self.run_config_command('add', 'site', '/name:%s' % site_name, '/bindings:%s' % options['binding'],
                                           '/physicalPath:%s' % self.install_dir):
                raise CommandError(
                    'The site creation has failed with the following message :\n%s' % self.last_command_error)

            print("Adding the site to the application pool")
            if not self.run_config_command('set', 'app', '%s/' % site_name, '/applicationPool:%s' % site_name):
                raise CommandError(
                    'Adding the site to the application pool has failed with the following message :\n%s' % self.last_command_error)

            if static_is_local and static_needs_virtual_dir:
                print("Creating virtual directory for [%s] in [%s]" % (static_dir, static_url))
                if not self.run_config_command('add', 'vdir', '/app.name:%s/' % site_name, '/path:/%s' % static_name,
                                               '/physicalPath:%s' % static_dir):
                    raise CommandError(
                        'Adding the static virtual directory has failed with the following message :\n%s' % self.last_command_error)

            log_dir = options['log_dir']
            if log_dir:
                if not self.run_config_command('set', 'site', '%s/' % site_name, '/logFile.directory:%s' % log_dir):
                    raise CommandError(
                        'Setting the logging directory has failed with the following message :\n%s' % self.last_command_error)

            maxContentLength = options['maxContentLength']
            if not self.run_config_command('set', 'config', '/section:requestfiltering',
                                           '/requestlimits.maxallowedcontentlength:' + str(maxContentLength)):
                raise CommandError(
                    'Setting the maximum content length has failed with the following message :\n%s' % self.last_command_error)

    def delete(self, args, options):
        if not os.path.exists(self.web_config) and not options['skip_config']:
            raise CommandError('A web site configuration does not exists in [%s] !' % self.install_dir)

        if not options['skip_config']:
            print("Removing site configuration")
            os.remove(self.web_config)

        if not options['skip_site']:
            site_name = options['site_name']
            print("Removing The site")
            if not self.run_config_command('delete', 'site', site_name):
                raise CommandError(
                    'Removing the site has failed with the following message :\n%s' % self.last_command_error)

            print("Removing The application pool")
            if not self.run_config_command('delete', 'apppool', site_name):
                raise CommandError(
                    'Removing the site has failed with the following message :\n%s' % self.last_command_error)

        if not options['skip_fastcgi']:
            print("Removing FastCGI application")
            if not self.delete_fastcgi_section():
                raise CommandError('The FastCGI application removal has failed')

    def handle(self, *args, **options):
        if self.script_name == 'django-admin.py':
            raise CommandError("""\
This command does not work when used with django-admin.py.
Please run it with the manage.py of the root directory of your project.
""")
        # Getting installation directory and doing some little checks
        self.install_dir = args[0] if args else self.project_dir
        if not os.path.exists(self.install_dir):
            raise CommandError('The web site directory [%s] does not exist !' % self.install_dir)

        if not os.path.isdir(self.install_dir):
            raise CommandError('The web site directory [%s] is not a directory !' % self.install_dir)

        self.install_dir = os.path.normcase(os.path.abspath(self.install_dir))

        print('Using installation directory %s' % self.install_dir)

        self.web_config = os.path.join(self.install_dir, 'web.config')

        if options['site_name'] == '':
            options['site_name'] = os.path.split(self.install_dir)[1]

        if not os.path.exists(self.appcmd):
            raise CommandError('It seems that IIS is not installed on your machine')

        if not self.check_config_section_exists(self.FASTCGI_SECTION):
            raise CommandError(
                'Failed to detect the CGI module with the following message:\n%s' % self.last_command_error)

        if options['delete']:
            self.delete(args, options)
        else:
            self.install(args, options)


if __name__ == '__main__':
    print('This is supposed to be run as a django management command')
