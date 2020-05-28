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
from urllib.parse import quote

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
    WTF_CSRF_ENABLED = False


class WebsiteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()


class ModelCase(WebsiteTestCase):
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


class TaskCase(WebsiteTestCase):
    @patch("app.tasks.get_current_job")
    def test_run_task(self, rgcj):
        mock_job = MagicMock()
        mock_job.get_id.return_value = "foobarbaz"
        rgcj.return_value = mock_job
        u = User(username='john', email='john@example.com')
        db.session.add(u)
        mock = MagicMock()
        mock.get_id.return_value = 'foobarbaz'
        with patch.object(self.app.task_queue, 'enqueue', return_value=mock) \
            as mock_enqueue_method:
            t = u.launch_task("run_mapping", (123, "board", "abc"), "Description")
        db.session.add(t)
        _set_task_progress(33)
        self.assertEqual(rgcj.mock_calls[2], call().meta.__setitem__('progress', 33))
        self.assertEqual(t.status, None)
        _set_task_progress(66, "Nice message")
        self.assertEqual(t.status, "Nice message")
        self.assertFalse(t.complete)
        _set_task_progress(100)
        self.assertTrue(t.complete)

    def test_run_mapping_invalid_mapping(self):
        f = io.StringIO()
        with self.assertLogs(level='INFO') as cm, contextlib.redirect_stderr(f):
            run_mapping(0, "", "")
        expected_logging = ['INFO:app:Starting task for mapping 0,  ',
            'ERROR:app:Invalid task, ignoring',
            'INFO:app:Completed task for mapping 0,  ']
        self.assertEqual(cm.output, expected_logging)
        for l in expected_logging:
            self.assertTrue(l.split(":app:")[1] in f.getvalue())

    def test_run_mapping_vm_invalid_args(self):
        m = Mapping(name="def")
        db.session.add(m)
        db.session.commit()
        f = io.StringIO()
        with self.assertLogs(level='INFO') as cm, contextlib.redirect_stderr(f):
            run_mapping(m.id, "", "")
        expected_logging = ['INFO:app:Starting task for mapping 1,  ',
            'ERROR:app:Invalid task, ignoring',
            'INFO:app:Completed task for mapping 1,  ']
        self.assertEqual(cm.output, expected_logging)
        for l in expected_logging:
            self.assertTrue(l.split(":app:")[1] in f.getvalue())

    def test_run_mapping_vm_valid_args_invalid_json(self):
        m = Mapping(name="def")
        db.session.add(m)
        db.session.commit()
        f = io.StringIO()
        with self.assertLogs(level='INFO') as cm, contextlib.redirect_stderr(f):
            run_mapping(m.id, "card", "abc")
        expected_logging_base = "TypeError: the JSON object must be str, bytes or "\
            "bytearray, not %s"
        expected_logging1 = expected_logging_base % "NoneType"
        expected_logging2 = expected_logging_base % "'NoneType'"
        self.assertTrue(expected_logging1 in cm.output[1] or
            expected_logging2 in cm.output[1])

    @patch("app.tasks._set_task_progress")
    @patch("app.tasks.process_master_card")
    @patch("app.tasks.perform_request")
    def test_run_mapping_vm_valid_args_card(self, atpr, atpmc, atstp):
        destination_lists = {
            "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
            "Label Two": ["ddd"],
            "All Teams": [
                "a1a1a1a1a1a1a1a1a1a1a1a1",
                "ddd"
            ]
        }
        dl = json.dumps(destination_lists)
        m = Mapping(name="abc", destination_lists=dl)
        db.session.add(m)
        db.session.commit()
        atpr.return_value = {"name": "Card name"}
        atpmc.return_value = (1, 2, 3)
        f = io.StringIO()
        with self.assertLogs(level='INFO') as cm, contextlib.redirect_stderr(f):
            run_mapping(m.id, "card", "abc")
        expected_calls = [call('GET', 'cards/abc', key=None, token=None)]
        self.assertEqual(atpr.mock_calls, expected_calls)
        expected_logging = "INFO:app:Processing master card 1/1 - Card name"
        self.assertEqual(cm.output[1], expected_logging)
        self.assertTrue(list(atpmc.call_args[0][1].keys()),
            ['destination_lists', 'key', 'token'])
        expected_call = call(100, 'Run complete. Processed 1 master cards (' \
            'of which 1 active) that have 2 slave cards (of which 3 new).')
        self.assertEqual(atstp.mock_calls[-1], expected_call)

    @patch("app.tasks._set_task_progress")
    @patch("app.tasks.process_master_card")
    @patch("app.tasks.perform_request")
    def test_run_mapping_vm_valid_args_list(self, atpr, atpmc, atstp):
        destination_lists = {
            "Label One": ["a1a1a1a1a1a1a1a1a1a1a1a1"],
            "Label Two": ["ddd"],
            "All Teams": [
                "a1a1a1a1a1a1a1a1a1a1a1a1",
                "ddd"
            ]
        }
        dl = json.dumps(destination_lists)
        m = Mapping(name="abc", destination_lists=dl)
        db.session.add(m)
        db.session.commit()
        atpr.return_value = [{"name": "Card name"}, {"name": "Second card"}]
        atpmc.side_effect = [(4, 5, 6), (7, 8, 9)]
        f = io.StringIO()
        with self.assertLogs(level='INFO') as cm, contextlib.redirect_stderr(f):
            run_mapping(m.id, "list", "def")
        expected_calls = [call('GET', 'list/def/cards', key=None, token=None)]
        self.assertEqual(atpr.mock_calls, expected_calls)
        expected_logging = ['INFO:app:Starting task for mapping 1, list def',
            'INFO:app:Processing master card 1/2 - Card name',
            'INFO:app:Processing master card 2/2 - Second card',
            'INFO:app:Completed task for mapping 1, list def']
        self.assertEqual(cm.output, expected_logging)
        expected_calls = [call(0),
            call(0, 'Job running... Processing 2 cards.'),
            call(50),
            call(100, 'Run complete. Processed 2 master cards (of which 11 ' \
                'active) that have 13 slave cards (of which 15 new).')]
        self.assertEqual(atstp.mock_calls, expected_calls)


class AuthCase(WebsiteTestCase):
    def register(self, username, email, password, password2):
        return self.client.post(
            '/auth/register',
            data=dict(username=username, email=email,
                password=password, password2=password2),
            follow_redirects=True
        )

    def create_user(self, username, password, email=None):
        u = User(username=username, email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    def login(self, username, password, follow_redirects=True):
        return self.client.post(
            '/auth/login',
            data=dict(username=username, password=password),
            follow_redirects=follow_redirects
        )

    def test_register_invalid(self):
        response = self.register(None, None, None, None)
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<input class="form-control is-invalid" id="username" ' \
                'name="username" required type="text" value="">',
            '<div class="invalid-feedback">This field is required.</div>',
            '<input class="form-control is-invalid" id="email" name="email" ' \
                'required type="text" value="">',
            '<input class="form-control is-invalid" id="password" ' \
                'name="password" required type="password" value="">',
            '<input class="form-control is-invalid" id="password2" ' \
                'name="password2" required type="password" value="">']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

    def test_register(self):
        # First registration is succesful
        response = self.register("john", "john@example.com", "abc", "abc")
        self.assertEqual(response.status_code, 200)
        ec = '<div class="alert alert-info" role="alert">Congratulations, ' \
            'you are now a registered user!</div>'
        self.assertIn(str.encode(ec), response.data)
        # Double registration fails
        response = self.register("john", "john@example.com", "abc", "abc")
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<div class="invalid-feedback">Please use a different username.</div>',
            '<div class="invalid-feedback">Please use a different email address.</div>']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

    def test_login_invalid(self):
        self.create_user("john", "abc")
        # Invalid username
        response = self.login("johnny", "abc")
        self.assertEqual(response.status_code, 200)
        ec = '<div class="alert alert-info" role="alert">Invalid username or ' \
            'password</div>'
        self.assertIn(str.encode(ec), response.data)
        # Invalid password, same error message
        response = self.login("john", "def")
        self.assertEqual(response.status_code, 200)
        self.assertIn(str.encode(ec), response.data)

    def test_login_valid(self):
        self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<li class="nav-item"><a class="nav-link" href="/edit_profile">' \
                'Profile</a></li>',
            '<li class="nav-item"><a class="nav-link" href="/auth/logout">' \
                'Logout</a></li>',
            '<h2>New mapping</h2>',
            '<a class="btn btn-info" href="/mapping/new" role="button">Create ' \
                'a new mapping</a>']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

    def test_login_double(self):
        self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        # Logging in while already logged in redirects to home
        response = self.login("john", "abc", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/")

    def test_login_register(self):
        self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        # GETting the registration page while logged in redirects to home
        response = self.client.get('/auth/register')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/")

    def test_logout(self):
        self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/auth/logout')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/")

    def test_reset_password_request(self):
        self.create_user("john", "abc", "a@a.com")

        # GETting the password reset form page while not logged in shows reset form
        response = self.client.get('/auth/reset_password_request')
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<h1>Reset Password</h1>',
            '<input class="btn btn-secondary btn-md" id="submit" ' \
                'name="submit" type="submit" value="Request Password Reset">']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

        # Valid form submission redirects to login page
        response = self.client.post('/auth/reset_password_request',
            data=dict(email="a@a.com"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/auth/login")

        # GETting the password reset form page while logged in redirects to home
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/auth/reset_password_request')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/")

    def test_reset_password(self):
        u = self.create_user("john", "abc", "a@a.com")

        # GETting the password reset page with an invalid token redirects to home
        response = self.client.get('/auth/reset_password/abc')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/")

        # GETting the password reset page with a valid token shows reset form
        token = u.get_reset_password_token()
        response = self.client.get('/auth/reset_password/%s' % token)
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<h1>Reset Your Password</h1>',
            '<input class="btn btn-secondary btn-md" id="submit" ' \
                'name="submit" type="submit" value="Reset Password">']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

        # Valid form submission redirects to login page
        self.assertTrue(u.check_password("abc"))
        response = self.client.post('/auth/reset_password/%s' % token,
            data=dict(password="def", password2="def"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/auth/login")
        self.assertTrue(u.check_password("def"))

        # GETting the password reset page while logged in redirects to home
        response = self.login("john", "def")
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/auth/reset_password/abc')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/")

    def test_main_routes_not_logged_in_redirects(self):
        # GETting these pages without being logged in redirects to login page
        for url in ("/", "/edit_profile", "/notifications"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"],
                "http://localhost/auth/login?next=%s" % quote(url, safe=''))

    def test_main_routes_home(self):
        u = self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<title>Home - Trello Team Sync</title>',
            '<li class="nav-item"><a class="nav-link" href="/auth/logout">' \
                'Logout</a></li>',
            '<h1>Hi, john!</h1>',
            '<h2>New mapping</h2>',
            '<a class="btn btn-info" href="/mapping/new" role="button">' \
                'Create a new mapping</a>']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

    def test_main_routes_notifications(self):
        u = self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/notifications')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b'[]\n', response.data)

        n1 = u.add_notification("First notification", {"aa": "abc", "bb": "def"})
        n2 = u.add_notification("Second notification", {"cc": "ghi"})
        response = self.client.get('/notifications')
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '[{"data":{"aa":"abc","bb":"def"},"name":"First notification","timestamp":',
            '},{"data":{"cc":"ghi"},"name":"Second notification","timestamp":']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

    def test_main_routes_edit_profile_get(self):
        u = self.create_user("john", "abc")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/edit_profile')
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<title>Edit Profile - Trello Team Sync</title>',
            '<h1>Edit Profile</h1>',
            '<input class="form-control" id="username" name="username" ' \
                'required type="text" value="john">']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)

    def test_main_routes_edit_profile_post(self):
        u = self.create_user("john", "abc")
        self.assertEqual(u.username, "john")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/edit_profile', data=dict(username="j2"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "http://localhost/edit_profile")
        self.assertEqual(u.username, "j2")

    def test_main_routes_edit_profile_post_collision(self):
        u1 = self.create_user("john", "abc")
        u2 = self.create_user("j2", "def")
        self.assertEqual(u1.username, "john")
        response = self.login("john", "abc")
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/edit_profile', data=dict(username="j2"))
        self.assertEqual(response.status_code, 200)
        expected_content = [
            '<title>Edit Profile - Trello Team Sync</title>',
            '<h1>Edit Profile</h1>',
            '<div class="invalid-feedback">Please use a different username.</div>']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)
        self.assertEqual(u1.username, "john")

    def test_error_404(self):
        response = self.client.get('/non_existent_route')
        self.assertEqual(response.status_code, 404)
        expected_content = [
            '<title>Welcome to Trello Team Sync</title>',
            '<h1>Not Found</h1>']
        for ec in expected_content:
            self.assertIn(str.encode(ec), response.data)


if __name__ == '__main__':
    unittest.main()
