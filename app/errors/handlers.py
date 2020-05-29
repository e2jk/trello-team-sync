#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from flask import render_template, request
from app import db
from app.errors import bp
from trello_team_sync import TrelloConnectionError


@bp.app_errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


@bp.app_errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500


@bp.app_errorhandler(TrelloConnectionError)
def trello_connection_error(error):
    db.session.rollback()
    return render_template('errors/trello.html'), 500
