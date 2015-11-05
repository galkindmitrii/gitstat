#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='GitStat',
    version='0.1',
    long_description='A small tool to operate Git repos',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Flask==0.10.1',
        'Flask-And-Redis==0.6',
        'GitPython==1.0.1',
        'Jinja2==2.8',
        'MarkupSafe==0.23',
        'Werkzeug==0.10.4',
        'argparse==1.2.1',
        'decorator==4.0.4',
        'gitdb==0.6.4',
        'itsdangerous==0.24',
        'redis==2.10.3',
        'requests==2.8.1',
        'simplejson==3.8.1',
        'six==1.10.0',
        'smmap==0.9.0',
        'validators==0.9',
        'wsgiref==0.1.2']
    )
