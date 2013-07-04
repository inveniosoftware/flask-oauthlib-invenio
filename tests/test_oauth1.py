# coding: utf-8

import os
import tempfile
import unittest
from nose.tools import raises
from urlparse import urlparse
from flask import Flask
from flask_oauthlib.client import OAuth, OAuthException
from .oauth1_server import create_server, db
from .oauth1_client import create_client


class BaseSuite(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.debug = True
        app.testing = True
        app.secret_key = 'development'

        self.db_fd, self.db_file = tempfile.mkstemp()
        config = {
            'OAUTH1_PROVIDER_ENFORCE_SSL': False,
            'OAUTH1_PROVIDER_KEY_LENGTH': (3, 30),
            'OAUTH1_PROVIDER_REALMS': ['email', 'address'],
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///%s' % self.db_file
        }
        app.config.update(config)

        app = create_server(app)
        app = self.create_client(app)

        self.app = app
        self.client = app.test_client()
        return app

    def tearDown(self):
        db.session.remove()
        db.drop_all()

        os.close(self.db_fd)
        os.unlink(self.db_file)

    def create_client(self, app):
        create_client(app)
        return app


class TestWebAuth(BaseSuite):
    def test_full_flow(self):
        rv = self.client.get('/login')
        assert 'oauth_token' in rv.location

        auth_url = clean_url(rv.location)
        rv = self.client.get(auth_url)
        assert '</form>' in rv.data

        rv = self.client.post(auth_url, data={
            'confirm': 'yes'
        })
        assert 'oauth_token' in rv.location

        token_url = clean_url(rv.location)
        rv = self.client.get(token_url)
        assert 'oauth_token_secret' in rv.data

        rv = self.client.get('/')
        assert 'email' in rv.data

    def test_no_confirm(self):
        rv = self.client.get('/login')
        assert 'oauth_token' in rv.location

        auth_url = clean_url(rv.location)
        rv = self.client.post(auth_url, data={
            'confirm': 'no'
        })
        assert 'error=denied' in rv.location

    def test_invalid_request_token(self):
        rv = self.client.get('/login')
        assert 'oauth_token' in rv.location
        loc = rv.location.replace('oauth_token=', 'oauth_token=a')

        auth_url = clean_url(loc)
        rv = self.client.get(auth_url)
        assert 'error' in rv.location

        rv = self.client.post(auth_url, data={
            'confirm': 'yes'
        })
        assert 'error' in rv.location


class TestNoClient(BaseSuite):
    @raises(OAuthException)
    def test_request(self):
        rv = self.client.get('/login')

    def create_client(self, app):
        oauth = OAuth(app)

        remote = oauth.remote_app(
            'dev',
            consumer_key='noclient',
            consumer_secret='dev',
            request_token_params={'realm': 'email'},
            base_url='http://127.0.0.1:5000/api/',
            request_token_url='http://127.0.0.1:5000/oauth/request_token',
            access_token_method='GET',
            access_token_url='http://127.0.0.1:5000/oauth/access_token',
            authorize_url='http://127.0.0.1:5000/oauth/authorize'
        )
        create_client(app, remote)
        return app


def clean_url(location):
    ret = urlparse(location)
    return '%s?%s' % (ret.path, ret.query)