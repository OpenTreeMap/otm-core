#!/bin/bash

apt-get install -y debconf
update-locale LC_CTYPE="en_US.UTF-8" LC_ALL="en_US.UTF-8" LANG="en_US.UTF-8"
dpkg-reconfigure locales

# Create otm user
if [ -z "$(getent passwd otm)" ];
then
    useradd -m -k /home/vagrant -s /bin/bash otm
    echo "otm ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/80-allow-otm-sudo
    chmod 0440 /etc/sudoers.d/80-allow-otm-sudo
fi

umount /usr/local/otm
mount -t vboxsf -o uid=`id -u otm`,gid=`id -g vagrant` share /usr/local/otm
