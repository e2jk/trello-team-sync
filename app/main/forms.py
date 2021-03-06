#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.validators import ValidationError, DataRequired, Length, Email, \
    EqualTo
from flask_babel import _, lazy_gettext as _l
from app.models import User


def makeAccountEditForm(edit_element, original_value):
    class AccountEditForm(FlaskForm):
        username = StringField(_l('Username'), validators=[DataRequired(),
            Length(max=63)])
        email = StringField(_l('Email'), validators=[DataRequired(), Email(),
            Length(min=5, max=255)])
        password = PasswordField(_l('Password'), validators=[DataRequired(),
            Length(min=8, max=128)])
        password2 = PasswordField(
            _l('Repeat Password'), validators=[DataRequired(),
                                               EqualTo('password')])
        trello = BooleanField(_l('OK, unlink my Trello account'),
            validators=[DataRequired()])
        submit = SubmitField(_l('Submit'))

        def __init__(self, original_value, *args, **kwargs):
            super(AccountEditForm, self).__init__(*args, **kwargs)
            self.original_value = original_value.lower()

        def validate_username(self, username):
            if username.data.lower() != self.original_value:
                user = User.query.filter_by(username=self.username.data.lower()).first()
                if user is not None:
                    raise ValidationError(_('Please use a different username.'))

        def validate_email(self, email):
            if email.data.lower() != self.original_value:
                user = User.query.filter_by(email=email.data).first()
                if user is not None:
                    raise ValidationError(_('Please use a different email address.'))

    form = AccountEditForm(original_value)
    # Remove the other elements
    for element in ("username", "email", "trello"):
        if edit_element != element:
            delattr(form, element)
    if edit_element != "password":
        delattr(form, "password")
        delattr(form, "password2")
    return form
