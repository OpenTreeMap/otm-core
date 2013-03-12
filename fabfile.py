""" Fabric script to handle common building tasks """
from fabric.api import cd, run, require, sudo, env, local

import os

def _set_default_paths(env):
    """ Modify the fabric environment to have default otm paths set """

    base_dir = '/usr/local/otm/'
    if 'venv_path' not in env:
        env.venv_path = os.path.join(base_dir, 'env')

    if 'site_path' not in env:
        env.site_path = os.path.join(base_dir, 'app', 'opentreemap')

    if 'static_path' not in env:
        env.static_path = os.path.join(base_dir, 'static')

_set_default_paths(env)

def vagrant():
    """ Configure fabric to use vagrant as a host.

    Use the current vagrant directory to gather ssh-config settings
    for the vagrant VM. Write these settings to the fabric env.

    This should prefix any commands to be run in this context.

    EX:
    fab vagrant <command_name>
    """
    vagrant_ssh_config = {}
    for l in local('vagrant ssh-config', capture=True).split('\n'):
        try:
            l = l.strip()
            i = l.index(' ')

            setting_name = l[:i].strip()
            setting_value = l[i+1:].strip()

            vagrant_ssh_config[setting_name] = setting_value
        except Exception, e:
            pass

    env.key_filename = vagrant_ssh_config['IdentityFile']
    env.user = vagrant_ssh_config['User']
    env.hosts = ['localhost:%s' % vagrant_ssh_config['Port']]

def me():
    """ Configure fabric to use localhost as a host.

    This should prefix any commands to be run in this context.

    EX:
    fab me <command_name>
    """
    env.hosts = ['localhost']

def _venv_exec(cmd):
    require('venv_path')
    return '%s/bin/%s' % (env.venv_path, cmd)

def _python(cmd):
    require('venv_path')
    return _venv_exec('python %s' % cmd)

def _manage(cmd):
    """ Execute 'cmd' as a python management command in the venv """
    with cd(env.site_path):
        sudo(_python('manage.py %s' % cmd))

def _collectstatic():
    """ Collect static files. """
    require('site_path')
    require('venv_path')

    with cd(env.site_path):
        sudo('rm -rf "%s"' % env.static_path)

    _manage('collectstatic --noinput')

def _blend():
    """ Lint, compile and minify javascript files. """
    require('static_path')
    require('venv_path')

    with cd(os.path.join(env.static_path, 'js')):
        sudo(_venv_exec('blend'))

def static():
    """ Collect static files and minify javascript. """
    _collectstatic()
    _blend()

def syncdb(dev_data=False):
    """ Run syncdb and all migrations

    Set dev_data to True to load in the development data
    """
    require('site_path')
    require('venv_path')

    _manage('syncdb --noinput')
    _manage('migrate --noinput')

    if dev_data:
        _manage('loaddata development_data.json')

def restart_app():
    """ Restart the gunicorns running the app """
    sudo("service otm-unicorn restart")
