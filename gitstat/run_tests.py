#!/usr/bin/env python
import os
from gitstat import app, redis
import simplejson as json

import unittest

class FlaskrTestCase(unittest.TestCase):

    test_repo_stats = {'disk_usage': '440K',
                       'last_checkout': 'Thu, 05 Nov 2015 19:10:44 +0000',
                       'url': 'https://github.com/galkindmitrii/openstack_swift_s3',
                       'current_revision': '31e695b60cde8149340303d1e282f194128cc676',
                       'recent_committer': 'Dmitry Galkin'}

    def setUp(self):
        app.config['TESTING'] = True
        app.config['REDIS_DB'] = 1  # separate DB
        self.app = app.test_client()
        redis.flushdb()

    def tearDown(self):
        redis.flushdb()

    def test_get_root_route(self):
        rv = self.app.get('/')
        assert 'Not Found' in rv.data
        assert rv.status_code == 404

    def test_get_empty_resources(self):
        rv = self.app.get('/resources/')
        assert rv.data == '[]'  # it's a str
        assert rv.status_code == 200

    def test_delete_empty_resources(self):
        rv = self.app.delete('/resources/')
        assert 'error' in rv.data
        assert 'Bad Request' in rv.data
        assert rv.status_code == 400

    def test_get_non_empty_existing_resources(self):
        redis.hmset('git_repo_id:1', self.test_repo_stats)
        rv = self.app.get('/resources/')
        assert 'git_repo_id:1' in rv.data
        assert 'https://github.com/galkindmitrii/openstack_swift_s3' in rv.data
        assert rv.status_code == 200

    def test_get_non_empty_not_existing_resources(self):
        redis.hmset('git_repo_id:1', self.test_repo_stats)
        rv = self.app.get('/resources/', data=json.dumps('{"id": [2,3]}'))
        assert '{2: {}}, {3: {}}' in rv.data
        assert rv.status_code == 200

    def test_delete_non_existing_resources(self):
        redis.hmset('git_repo_id:1', self.test_repo_stats)
        rv = self.app.delete('/resources/', data=json.dumps('{"id": [2,3]}'))
        assert 'error' in rv.data
        assert 'Bad Request' in rv.data
        assert rv.status_code == 400

    def test_delete_existing_not_cloned_resources(self):
        redis.hmset('git_repo_id:1', self.test_repo_stats)
        rv = self.app.delete('/resources/', data=json.dumps('{"id": [1]}'))
        assert 'error' in rv.data
        assert 'Bad Request' in rv.data
        assert rv.status_code == 400

    def test_post_non_valid_resources(self):
        rv = self.app.post('/resources/', data=json.dumps('{"foo": "bar"}'))
        assert 'error' in rv.data
        assert 'Bad Request' in rv.data
        assert rv.status_code == 400

    def test_post_non_valid_resources_2(self):
        rv = self.app.post('/resources/', data=json.dumps('{"branch": "master"}'))
        assert 'error' in rv.data
        assert 'Bad Request' in rv.data
        assert rv.status_code == 400

    def test_post_non_valid_resources_3(self):
        rv = self.app.post('/resources/', data=json.dumps('{"revision": "fooobaaar"}'))
        assert 'error' in rv.data
        assert 'Bad Request' in rv.data
        assert rv.status_code == 400


if __name__ == '__main__':
    unittest.main()
