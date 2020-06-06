#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from app import create_app, db, cli
from app.models import User, Notification, Task, Mapping

app = create_app()
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Notification': Notification, 'Task': Task,
        'Mapping': Mapping}
