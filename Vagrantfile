# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  # Every Vagrant virtual environment requires a box to build off of.
  config.vm.box = "precise64"

  config.vm.network :forwarded_port, guest: 80, host: 6060

  config.vm.synced_folder ".", "/usr/local/otm/app/"

  config.vm.provision :shell, :path => "scripts/bootstrap.sh"

  config.vm.provider :virtualbox do |vb, override|
    override.vm.box_url = "http://files.vagrantup.com/precise64.box"
    override.vm.provision :shell, :path => "scripts/virtualbox.sh"
    vb.customize ["modifyvm", :id, "--memory", 2048, "--cpus", "2"]
  end
  config.vm.provider :lxc do |lxc, override|
    override.vm.box_url = "http://bit.ly/vagrant-lxc-precise64-2013-07-12"
    override.vm.provision "shell", inline: "sudo apt-get install -qy python-apt"
    lxc.customize "cgroup.memory.limit_in_bytes", '2048M'
  end
end
