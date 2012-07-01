# encoding: utf-8

# FastCGI Windows Server Django installation command
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

__author__ = 'Antoine Martin <antoine@openance.com>'

import os
import os.path
import logging
import sys
import re
from optparse import OptionParser
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from optparse import make_option
import subprocess

class Command(BaseCommand):
    args = '[root_path]'
    help = '''Installs the current application as a fastcgi application under windows.

    If the root path is not specified, the command will take the
    root directory of the project.
    '''
        
    CONFIGURATION_TEMPLATE = '''/+"[fullPath='{python_interpreter}',arguments='{script} winfcgi --pythonpath={project_dir}',maxInstances='{maxInstances}',idleTimeout='{idleTimeout}',activityTimeout='{activityTimeout}',requestTimeout='{requestTimeout}',instanceMaxRequests='{instanceMaxRequests}',protocol='NamedPipe',flushNamedPipe='False',monitorChangesTo='{monitorChangesTo}']"'''
    
    FASTCGI_SECTION = 'system.webServer/fastCgi'
    
    option_list = BaseCommand.option_list + (
        make_option('--max-instances',
            dest='maxInstances',
            default=4,
            help='Maximum number of pyhton processes'),
        make_option('--idle-timeout',
            dest='idleTimeout',
            default=1800,
            help='Idle time in seconds after which a python process is recycled'),
        make_option('--activity-timeout',
            dest='activityTimeout',
            default=30,
            help='Number of seconds without data transfer after which a process is stopped'),
        make_option('--request-timeout',
            dest='requestTimeout',
            default=90,
            help='Total time in seconds for a request'),
        make_option('--instance-max-requests',
            dest='instanceMaxRequests',
            default=10000,
            help='Number of requests after which a python process is recycled'),
        make_option('--monitor-changes-to',
            dest='monitorChangesTo',
            default='web.config',
            help='Application is restarted when this file changes'),
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.appcmd = os.path.join(os.environ['windir'], 'system32', 'inetsrv', 'appcmd.exe')
        
    def config_command(self, command, section, *args):
        arguments = [ self.appcmd, command, section]
        arguments.extend(args)
        return subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
    def check_config_section_exists(self, section_name):
        command = self.config_command('list', 'config', '-section:%s' % section_name)
        (out, err) = command.communicate()
        return command.returncode == 0
        
    def create_fastcgi_section(self, script, project_dir, options):
        template_options = options.copy()
        template_options['script'] = script
        template_options['project_dir'] = project_dir
        template_options['python_interpreter'] = sys.executable
        param = self.CONFIGURATION_TEMPLATE.format(**template_options)
        print param

    def handle(self, *args, **options):
        current_script = os.path.abspath(sys.argv[0])
        project_dir, script_name = os.path.split(current_script)
        python_interpreter = sys.executable
        if script_name == 'django-admin.py':
            raise CommandError("""\
This command does not work when used with django-admin.py.
Please run it with the manage.py of the root directory of your project.
""")
        # Getting installation directory and doing some little checks
        install_dir = args[0] if args else project_dir
        if not os.path.exists(install_dir):
            raise CommandError('The web site directory [%s] does not exist !' % install_dir)
            
        if not os.path.isdir(install_dir):
            raise CommandError('The web site directory [%s] is not a directory !' % install_dir)
            
        install_dir = os.path.normcase(os.path.abspath(install_dir))
        
        if os.path.exists(os.path.join(install_dir, 'web.config')):
            raise CommandError('A web site configuration already exists in [%s] !' % install_dir)
        
        print 'Using installation directory %s' % install_dir
        
        # now getting static files directory and URL
        static_dir = os.path.normcase(os.path.abspath(getattr(settings, 'STATIC_ROOT', '')))
        static_url = getattr(settings, 'STATIC_URL', '/static/')
        
        static_match = re.match('^/([^/]+)/$', static_url)
        if static_match:        
            static_is_local = True            
            static_name = static_match.group(1)
            static_needs_virtual_dir = static_dir != os.path.join(install_dir,static_name)
        else:
            static_is_local = False
        
        if static_dir == install_dir and static_is_local:
            raise CommandError('''\
The web site directory cannot be the same as the static directory,
for we cannot have two different web.config files in the same
directory !''')
            
        if not os.path.exists(self.appcmd):
            raise CommandError('It seems that IIS is not installed on your machine')

        if not self.check_config_section_exists(self.FASTCGI_SECTION):
            raise CommandError('It seems that The CGI module is not installed')
            
        self.create_fastcgi_section(current_script, project_dir, options)

if __name__ == '__main__':
    print 'This is supposed to be run as a django management command'
        