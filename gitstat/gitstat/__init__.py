from os import environ

from flask import Flask
from flask_redis import Redis


# define the file with configuration as env var
environ["GITSTAT_CONFIG"] = "gitstat.conf"

# create a gitstat application
app = Flask(__name__)
app.config.from_envvar('GITSTAT_CONFIG', silent=True)

# and init redis with it
redis = Redis(app)

# file with all routes
import gitstat.routes
