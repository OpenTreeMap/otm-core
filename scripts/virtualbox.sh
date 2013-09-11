#!/bin/bash

# vagrant mounts the share as the wrong user (vagrant)
# umount and remount as otm.
mountpoint -q /usr/local/otm/app/ && umount /usr/local/otm/app/
mount -t vboxsf -o uid=`id -u otm`,gid=`id -g vagrant` '/usr/local/otm/app' /usr/local/otm/app/
