#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, \
    BooleanField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, \
    Regexp, Length
from flask_babel import _, lazy_gettext as _l
from app.models import User


class LoginForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Remember Me'))
    submit = SubmitField(_l('Sign In'))

def makeRegistrationForm(privacy_link, terms_link):
    class RegistrationForm(FlaskForm):
        username = StringField(_l('Username'), validators=[DataRequired()])
        email = StringField(_l('Email'), validators=[DataRequired(), Email(),
            Length(min=5, max=255)])
        password = PasswordField(_l('Password'), validators=[DataRequired(),
            Length(min=8, max=128)])
        password2 = PasswordField(
            _l('Repeat Password'), validators=[DataRequired(),
                                               EqualTo('password')])
        privacy_policy= _l("Privacy Policy")
        privacy_policy_link = '<a href="%s">%s</a>' % (privacy_link, privacy_policy)
        terms_conditions= _l("Terms and Conditions")
        terms_conditions_link = '<a href="%s">%s</a>' % (terms_link, terms_conditions)
        accept_terms_text = _l("By signing up, you confirm that you've read and accepted our {terms_conditions_link} and {privacy_policy_link}.".format_map({"terms_conditions_link": terms_conditions_link, "privacy_policy_link": privacy_policy_link}))
        accept_terms = BooleanField(_l(accept_terms_text),
            validators=[DataRequired()])
        submit = SubmitField(_l('Register'))

        def validate_username(self, username):
            user = User.query.filter_by(username=username.data.lower()).first()
            if user is not None:
                raise ValidationError(_('Please use a different username.'))

        def validate_email(self, email):
            user = User.query.filter_by(email=email.data).first()
            if user is not None:
                raise ValidationError(_('Please use a different email address.'))

    return RegistrationForm()


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(_l('Email'), validators=[DataRequired(), Email(),
        Length(min=5, max=255)])
    submit = SubmitField(_l('Request Password Reset'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    password2 = PasswordField(
        _l('Repeat Password'), validators=[DataRequired(),
                                           EqualTo('password')])
    submit = SubmitField(_l('Reset Password'))


class ValidateTrelloTokenForm(FlaskForm):
    trello_token_regexp = "^(.*/auth/validate_trello_token)?(#)?(token=)?([0-9a-fA-F]{64})$"
    trello_token = StringField(_l('Trello token'), validators=[DataRequired(), \
        Regexp(trello_token_regexp,
        message=_l('Invalid Trello token format, it must be a 64 character string.'))])
    submit_trello_token = SubmitField(_l('Validate Trello token'))
