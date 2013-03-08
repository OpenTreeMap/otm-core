""" Fabric script to handle common iOS building tasks """
from fabric.api import cd, run, require, sudo, env, local

import os

def _set_defaults():
    if 'venv_path' not in env:
        env.venv_path = '/usr/local/otm_env/env'

    if 'site_path' not in env:
        env.site_path = '/usr/local/otm/opentreemap'

    if 'static_path' not in env:
        env.static_path = '/usr/local/otm_static/static'

def vagrant():
    data = {}
    for l in local('vagrant ssh-config', capture=True).split('\n'):
        try:
            l = l.strip()
            i = l.index(' ')
            data[l[0:i].strip()] = l[i+1:].strip()
        except Exception, e:
            pass

    env.key_filename = data['IdentityFile']
    env.user = data['User']
    env.hosts = ['localhost:%s' % data['Port']]

    _set_defaults()

def me():
    env.hosts = ['localhost']
    _set_defaults()

def _venv_exec(cmd):
    require('venv_path')
    return '%s/bin/%s' % (env.venv_path, cmd)

def _python(cmd):
    require('venv_path')
    return _venv_exec('python %s' % cmd)

def collectstatic():
    require('site_path')
    require('venv_path')

    with cd(env.site_path):
        sudo('rm -rf "%s"' % env.static_path)
        sudo(_python('manage.py collectstatic --noinput'))

# Requires java?!?
def blend():
    require('static_path')
    require('venv_path')

    with cd(os.path.join(env.static_path, 'js')):
        sudo(_venv_exec('blend'))

def static():
    collectstatic()
    blend()
