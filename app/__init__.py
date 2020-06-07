#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

import logging
from logging.handlers import SMTPHandler, RotatingFileHandler
import os
from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_babel import Babel, lazy_gettext as _l
from flask_caching import Cache
from secure import SecureHeaders, SecurePolicies
from flask_paranoid import Paranoid
from redis import Redis
import rq
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = _l('Please log in to access this page.')
login.session_protection = "strong"
mail = Mail()
bootstrap = Bootstrap()
moment = Moment()
babel = Babel()
cache = Cache()
csp_value = (
    SecurePolicies.CSP()
    .default_src(SecurePolicies.CSP().Values.none)
    .block_all_mixed_content()
    .base_uri(SecurePolicies.CSP().Values.self_)
    .script_src(SecurePolicies.CSP().Values.self_,
        SecurePolicies.CSP().Values.unsafe_inline,
        "cdn.jsdelivr.net/npm/jquery@3.4.1/",
        "cdn.jsdelivr.net/npm/popper.js@1.14.0/",
        "cdn.jsdelivr.net/npm/bootstrap@4.3.1/",
        "cdnjs.cloudflare.com/ajax/libs/moment.js/",
        "cdn.jsdelivr.net/npm/cookieconsent@3/")
    .style_src(SecurePolicies.CSP().Values.self_,
        SecurePolicies.CSP().Values.unsafe_inline,
        "cdn.jsdelivr.net/npm/bootstrap@4.3.1/",
        "cdn.jsdelivr.net/npm/cookieconsent@3/")
    .form_action(SecurePolicies.CSP().Values.self_)
    .connect_src(SecurePolicies.CSP().Values.self_)
    .img_src(SecurePolicies.CSP().Values.self_, "data:")
)
secure_headers = SecureHeaders(server="None", feature=True, csp=csp_value)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app)
    cache.init_app(app)
    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.task_queue = rq.Queue('syncboom-tasks', connection=app.redis)
    paranoid = Paranoid(app)
    paranoid.redirect_view = '/'

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.mapping import bp as mapping_bp
    app.register_blueprint(mapping_bp, url_prefix='/mapping')

    if not app.debug and not app.testing:
        if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'],
                        app.config['MAIL_PASSWORD'])
            secure = None
            if app.config['MAIL_USE_TLS']:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr='no-reply@' + app.config['MAIL_SERVER'],
                toaddrs=app.config['ADMINS'], subject='[SyncBoom] Failure',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)

        if app.config['LOG_TO_STDOUT']:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler('logs/syncboom.log',
                                               maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s '
                '[in %(pathname)s:%(lineno)d]'))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)

    # Serve local Bootstrap files when in debug mode
    app.config["BOOTSTRAP_SERVE_LOCAL"] = app.debug

    @app.after_request
    def set_secure_headers(response):
        secure_headers.flask(response)
        return response

    return app


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(current_app.config['LANGUAGES'])


from app import models
