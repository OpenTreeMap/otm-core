#!/bin/bash

# vagrant mounts the share as the wrong user (vagrant)
# umount and remount as otm.
mountpoint -q /usr/local/otm/app/ && umount /usr/local/otm/app/
mkdir -p /usr/local/otm/app
success_message="Remounted /usr/local/otm/app as otm"
if mount -t vboxsf -o uid=`id -u otm`,gid=`id -g vagrant` '/usr/local/otm/app' /usr/local/otm/app/ ; then
  echo $success_message
else
  echo "Remounting failed. Trying alternate syntax..."
  if mount.vboxsf -o uid=`id -u otm`,gid=`id -g vagrant` usr_local_otm_app /usr/local/otm/app/ ; then
    echo $success_message
  fi
fi
