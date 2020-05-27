#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Running the tests:
# $ python3 -m unittest discover --start-directory ./tests/
# Checking the coverage of the tests:
# $ coverage run --include=./*.py --omit=tests/* -m unittest discover && rm -rf html_dev/coverage && coverage html --directory=html_dev/coverage --title="Code test coverage for trello-team-sync"

from datetime import datetime, timedelta
import unittest
from app import create_app, db
from app.models import User, load_user, Task, Mapping
from config import Config, basedir
import sys
import io
import contextlib
import os
from unittest.mock import patch, call, MagicMock
from sqlalchemy.exc import IntegrityError
from redis.exceptions import RedisError
from rq.exceptions import NoSuchJobError
from datetime import datetime, timedelta
import json

if not os.environ.get("FLASK_DEBUG"):
    # Suppress output when starting up app from website.py or app/tasks.py
    with contextlib.redirect_stderr(io.StringIO()):
        from app.tasks import _set_task_progress, run_mapping
        from website import make_shell_context
else:
    from app.tasks import _set_task_progress, run_mapping
    from website import make_shell_context


class TestMakeShellContext(unittest.TestCase):
    def test_make_shell_context(self):
        return_value = make_shell_context()
        for i in ("db", "User", "Notification", "Task", "Mapping"):
            self.assertTrue(i in return_value)


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'


class ModelCase(unittest.TestCase):
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

    def test_repr(self):
        u = User(username='john', email='john@example.com')
        self.assertEqual(str(u), "<User john>")

    def test_password_reset_token_valid(self):
        u1 = User(username='john', email='john@example.com')
        db.session.add(u1)
        db.session.commit()
        token = u1.get_reset_password_token()
        u2 = User.verify_reset_password_token(token)
        self.assertEqual(u2, u1)

    def test_password_reset_token_invalid(self):
        u = User.verify_reset_password_token("Invalid token")
        self.assertEqual(u, None)

    def test_add_notification(self):
        u = User(username='john', email='john@example.com')
        db.session.add(u)
        n1 = u.add_notification("First notification", {"aa": "abc", "bb": "def"})
        n2 = u.add_notification("Second notification", {"cc": "ghi"})
        self.assertEqual(u.notifications.all(), [n1, n2])

    def test_run_mapping_valid_task(self):
        u = User(username='john', email='john@example.com')
        mock = MagicMock()
        mock.get_id.side_effect = ['foobarbaz', 'other_id']
        with patch.object(self.app.task_queue, 'enqueue', return_value=mock) \
            as mock_enqueue_method:
            t1 = u.launch_task("run_mapping", (123, "board", "abc"), "Description")
            t1.complete = True
            t2 = u.launch_task("run_mapping", (123, "board", "abc"), "Desc 2")
        self.assertEqual(t1.id, 'foobarbaz')
        self.assertEqual(t1.name, 'run_mapping')
        self.assertEqual(t1.description, 'Description')
        self.assertEqual(t1.user, u)
        self.assertEqual(u.tasks.all(), [t1, t2])
        expected_calls = [
            call('app.tasks.run_mapping', 123, 'board', 'abc'),
            call('app.tasks.run_mapping', 123, 'board', 'abc')
        ]
        self.assertEqual(mock_enqueue_method.mock_calls, expected_calls)
        self.assertEqual(u.get_tasks_in_progress(), [t2])
        self.assertEqual(u.get_task_in_progress("run_mapping"), t2)
        self.assertEqual(u.get_recent_tasks(), [t2, t1])

    def test_launch_task_invalid(self):
        u = User(username='john', email='john@example.com')
        t1 = u.launch_task("name", (), "description")
        t2 = u.launch_task("run_mapping", (None, None), "description")
        self.assertEqual(t1, None)
        self.assertEqual(t2, None)

    def test_same_username(self):
        u1 = User(username='john', email='john1@example.com')
        u2 = User(username='john', email='john2@example.com')
        db.session.add(u1)
        db.session.add(u2)
        with self.assertRaises(IntegrityError) as cm:
            db.session.commit()
        self.assertEqual(str(cm.exception.orig),
            'UNIQUE constraint failed: user.username')

    def test_same_email(self):
        u1 = User(username='john1', email='john@example.com')
        u2 = User(username='john2', email='john@example.com')
        db.session.add(u1)
        db.session.add(u2)
        with self.assertRaises(IntegrityError) as cm:
            db.session.commit()
        self.assertEqual(str(cm.exception.orig),
            'UNIQUE constraint failed: user.email')

    def test_load_user(self):
        u = User(username='john', email='john1@example.com')
        db.session.add(u)
        self.assertEqual(load_user(1), u)

    def test_notification_get_data(self):
        u = User(username='john', email='john@example.com')
        db.session.add(u)
        n1 = u.add_notification("First notification", {"aa": "abc", "bb": "def"})
        data = n1.get_data()
        self.assertEqual(data["aa"], "abc")
        self.assertEqual(data["bb"], "def")

    @patch("rq.job.Job.fetch")
    def test_task_get_rq_job(self, rjjf):
        t = Task()
        # First test Redis/rq errors, then mock a running Redis server
        rjjf.side_effect = [RedisError(), NoSuchJobError(), "abc"]
        self.assertEqual(t.get_rq_job(), None)
        self.assertEqual(t.get_rq_job(), None)
        self.assertEqual(t.get_rq_job(), "abc")

    @patch("app.models.Task.get_rq_job")
    def test_task_get_progress(self, tgrj):
        t = Task()
        mock_job = MagicMock()
        mock_job.meta.get.return_value = 27
        tgrj.side_effect = [None, mock_job]
        # Non-existing job returns 100% done
        self.assertEqual(t.get_progress(), 100)
        self.assertEqual(t.get_progress(), 27)

    def test_task_get_duration(self):
        now = datetime.utcnow()
        data = [
            [now - timedelta(seconds=3),   now, "3s"],
            [now - timedelta(seconds=60),  now, "1m 0s"],
            [now - timedelta(seconds=61),  now, "1m 1s"],
            [now - timedelta(seconds=627), now, "10m 27s"]
        ]
        for d in data:
            t = Task(timestamp_start=d[0], timestamp_end=d[1])
            self.assertEqual(t.get_duration(), d[2])
        # No end timestamp
        t = Task(timestamp_start=now)
        self.assertEqual(t.get_duration(), "unknown")

    def test_mapping(self):
        u = User(username='john', email='john@example.com')
        destination_lists = {
            "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
            "Label Two": ["ddd"],
            "All Teams": [
                "a1a1a1a1a1a1a1a1a1a1a1a1",
                "ddd"
            ]
        }
        dl = json.dumps(destination_lists)
        m1 = Mapping(name="abc", destination_lists=dl)
        self.assertEqual(str(m1), "<Mapping abc>")
        self.assertEqual(m1.get_num_labels(), 3)
        self.assertEqual(m1.get_num_dest_lists(), 4)
        u.mappings.append(m1)
        m2 = Mapping(name="def")
        u.mappings.append(m2)
        self.assertEqual(u.get_mappings(), [m1, m2])


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
