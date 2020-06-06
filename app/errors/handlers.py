#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from flask import render_template, request
from flask_babel import _
from app import db
from app.errors import bp
from syncboom import TrelloConnectionError, TrelloAuthenticationError


@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html', title=_('Page Not Found')), 404


@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html', title=_('Unexpected Error')), 500


@bp.app_errorhandler(TrelloConnectionError)
def trello_connection_error(error):
    db.session.rollback()
    return render_template('errors/trello_connection.html',
        title=_('Trello Connection Error')), 500


@bp.app_errorhandler(TrelloAuthenticationError)
def trello_authentication_error(error):
    db.session.rollback()
    return render_template('errors/trello_authentication.html',
        title=_('Trello Authentication Error')), 500
