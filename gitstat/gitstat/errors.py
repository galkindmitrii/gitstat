#!/usr/bin/env python

class BadRequest(Exception):

    def __init__(self, message, status_code, payload=None):
        Exception.__init__(self)
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = self.payload
        rv['message'] = self.message
        return rv
