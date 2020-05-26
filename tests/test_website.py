#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Running the tests:
# $ python3 -m unittest discover --start-directory ./tests/
# Checking the coverage of the tests:
# $ coverage run --include=./*.py --omit=tests/* -m unittest discover && rm -rf html_dev/coverage && coverage html --directory=html_dev/coverage --title="Code test coverage for trello-team-sync"

from datetime import datetime, timedelta
import unittest
from app import create_app, db
from app.models import User
from config import Config, basedir
import sys
import io
import contextlib
import os

sys.path.append('.')
target = __import__("website")


class TestMakeShellContext(unittest.TestCase):
    def test_make_shell_context(self):
        return_value = target.make_shell_context()
        for i in ("db", "User", "Notification", "Task", "Mapping"):
            self.assertTrue(i in return_value)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


class UserModelCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='susan')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_avatar(self):
        u = User(username='john', email='john@example.com')
        self.assertEqual(u.avatar(128), ('https://www.gravatar.com/avatar/'
                                         'd4c74594d841139328695756648b6bd6'
                                         '?d=identicon&s=128'))



class ConfigCase(unittest.TestCase):
    def test_config_values(self):
        self.assertEqual(Config.SECRET_KEY, os.environ.get('SECRET_KEY') or \
            'you-will-never-guess')
        self.assertEqual(Config.SQLALCHEMY_DATABASE_URI, os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'data', 'app.db'))
        self.assertEqual(Config.SQLALCHEMY_TRACK_MODIFICATIONS, False)
        self.assertEqual(Config.LOG_TO_STDOUT, os.environ.get('LOG_TO_STDOUT'))
        self.assertEqual(Config.MAIL_SERVER, os.environ.get('MAIL_SERVER'))
        self.assertEqual(Config.MAIL_PORT, int(os.environ.get('MAIL_PORT') or 25))
        self.assertEqual(Config.MAIL_USE_TLS, os.environ.get('MAIL_USE_TLS') is not None)
        self.assertEqual(Config.MAIL_USERNAME, os.environ.get('MAIL_USERNAME'))
        self.assertEqual(Config.MAIL_PASSWORD, os.environ.get('MAIL_PASSWORD'))
        self.assertEqual(Config.ADMINS, ['your-email@example.com'])
        self.assertEqual(Config.LANGUAGES, ['en'])
        self.assertEqual(Config.REDIS_URL, os.environ.get('REDIS_URL') or 'redis://')


if __name__ == '__main__':
    unittest.main()
