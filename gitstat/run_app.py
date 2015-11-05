#!/usr/bin/env python
from gitstat import app

from logging import INFO, DEBUG, WARNING
from logging.handlers import RotatingFileHandler


if __name__ == '__main__':
    # configure log handler for application:
    log_handler = RotatingFileHandler('gitstat.log',
                                      maxBytes=10000,
                                      backupCount=1)
    log_handler.setLevel(WARNING)
    app.logger.addHandler(log_handler)

    # run the application:
    app.run('0.0.0.0', 8080)
