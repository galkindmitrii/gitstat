# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "hashicorp/precise32"
  
  # provision git stat app via shell script
  config.vm.provision :shell, path: "setup_gitstat.sh", run: "always"
  
  # forward the port:
  config.vm.network :forwarded_port, guest: 8080, host: 8080

  # SHELL
end
