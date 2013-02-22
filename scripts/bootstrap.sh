#!/bin/bash

# Create otm user
if [ -z "$(getent passwd otm)" ];
then
    useradd -m -k /home/vagrant -s /bin/bash otm
    echo "otm ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/80-allow-otm-sudo
    chmod 0440 /etc/sudoers.d/80-allow-otm-sudo
fi

rm -rf /usr/local/otm
ln -s /vagrant /usr/local/otm
