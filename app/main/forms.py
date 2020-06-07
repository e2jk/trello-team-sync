#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Length
from flask_babel import _, lazy_gettext as _l
from app.models import User


class EditAccountForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    submit = SubmitField(_l('Submit'))

    def __init__(self, original_username, *args, **kwargs):
        super(EditAccountForm, self).__init__(*args, **kwargs)
        self.original_username = original_username.lower()

    def validate_username(self, username):
        if username.data.lower() != self.original_username:
            user = User.query.filter_by(username=self.username.data.lower()).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))
