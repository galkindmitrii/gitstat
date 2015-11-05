#!/usr/bin/env python
import requests
import json


sample_data = '''{"url": "https://github.com/galkindmitrii/HapticFeedback",
                  "branch": "master",
                  "revision": "60f36e54065bd44bfd29f5efd7ba88efc2c0c970"}'''

response = requests.post("http://localhost:8080/resources/",
                         data = json.dumps(sample_data))

print "Response Status Code:", response.status_code
print "Response Message:", response.text
