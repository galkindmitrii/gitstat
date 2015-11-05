#!/usr/bin/env bash
echo "Performing update"
apt-get update

echo "Installing required packages"
apt-get install -y git redis-server python python-pip python-dev python-setuptools

echo "Installing app python dependencies"
python /vagrant/gitstat/setup.py install

echo "Starting app on port 8080. Check localhost:8080/resources/ on your host"
nohup python /vagrant/gitstat/run_app.py > gs.log &
