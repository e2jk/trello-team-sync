#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.

from flask import Blueprint

bp = Blueprint('mapping', __name__)

from app.mapping import routes
