#!/usr/bin/env python

import argparse
import base64
import datetime
import hashlib
import hmac
import os
import subprocess

try:
    from urllib.parse import urlparse, quote, parse_qs
except ImportError:
    from urllib import quote
    from urlparse import urlparse, parse_qs

from pytz import timezone

SIG_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S"


def main():
    parser = argparse.ArgumentParser(
        description=('Make an HMAC signed request via cURL with support for '
                     'small subset of cURL options. Set ACCESS_KEY and '
                     'SECRET_KEY variables in the environment before '
                     'executing.'))
    parser.add_argument('url', help='The URL to be requested')
    parser.add_argument('-X',
                        '--request',
                        default='GET',
                        help='The HTTP method. Default is GET')
    parser.add_argument('-I',
                        '--head',
                        action='store_true',
                        help='Show document info only')
    parser.add_argument('-s',
                        '--silent',
                        action='store_true',
                        help=('Silent or quiet mode. Don''t show progress '
                              'meter or error messages.'))
    parser.add_argument('-d', '--data', help='The request body')
    parser.add_argument('--debug',
                        action='store_true',
                        help='Print debugging information')
    parser.add_argument('--access_key',
                        help='Access key')
    parser.add_argument('--secret_key',
                        help='Secret key')
    args = parser.parse_args()

    access_key = args.access_key or os.environ.get('ACCESS_KEY')
    secret_key = args.secret_key or os.environ.get('SECRET_KEY')
    if not access_key or not secret_key:
        raise Exception(
            'You must set ACCESS_KEY and SECRET_KEY environment variables')

    timestamp = datetime.datetime.utcnow().strftime(SIG_TIMESTAMP_FORMAT)
    #timestamp = datetime.datetime.strptime('2020-12-28 03-02-52', '%Y-%m-%d %H-%M-%S').strftime(SIG_TIMESTAMP_FORMAT)

    verb = args.request
    url = urlparse(args.url)
    host = url.netloc
    path = url.path
    params = parse_qs(url.query)
    params['access_key'] = access_key
    params['timestamp'] = timestamp

    def stringify_param_value(value):
        if isinstance(value, list):
            return quote(value[0])
        return quote(value)

    sorted_params = [
        '{}={}'.format(k, stringify_param_value(params[k]))
        for k in sorted(params.keys())
    ]

    param_string = '&'.join(sorted_params)
    if args.debug:
        print(param_string)

    string_to_sign = '\n'.join([verb, host, path, param_string])
    if args.debug:
        print(string_to_sign)

    if args.data:
        data = base64.b64encode(args.data.encode())
        if data:
            string_to_sign += data.decode()

    signature = base64.b64encode(
        hmac.new(secret_key.encode(), string_to_sign.encode(),
                 hashlib.sha256).digest())

    signed_url = '{}://{}{}?{}&signature={}'.format(url.scheme, url.netloc,
                                                    url.path, param_string,
                                                    signature.decode())
    import ipdb; ipdb.set_trace() # BREAKPOINT
    if args.debug:
        print(signed_url)

    verb_arg = '-X {} '.format(verb)
    head_arg = '-I ' if args.head else ''
    head_arg = '-s ' if args.silent else ''
    data_arg = "--data '{}' ".format(args.data) if args.data else ''

    command = 'curl {}{}{}"{}"'.format(head_arg, verb_arg, data_arg,
                                       signed_url)
    if args.debug:
        print(command)

    p = subprocess.Popen(command, shell=True)
    p.wait()


if __name__ == "__main__":
    main()
