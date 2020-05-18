#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from flask import Blueprint

bp = Blueprint('main', __name__)

from app.main import routes
