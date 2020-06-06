#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from guess_language import guess_language
from app import db
from app.main.forms import EditProfileForm
from app.models import User, Notification
from app.main import bp


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())


@bp.route('/')
@login_required
def index():
    redirect_url = "http://127.0.0.1:5000/auth/validate_trello_token"
    trello_authorizing_url = "https://trello.com/1/authorize?" \
        "name=%s&" \
        "scope=read,write&" \
        "expiration=never&" \
        "return_url=%s&" \
        "key=%s&" \
        "callback_method=fragment" % \
        (
            "SyncBoom",
            redirect_url,
            current_app.config["TRELLO_API_KEY"]
        )
    return render_template('index.html', title=_('Home'),
        trello_authorizing_url=trello_authorizing_url)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data.lower()
        db.session.commit()
        flash(_('Your changes have been saved.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username.lower()
    return render_template('edit_profile.html', title=_('Edit Profile'),
                           form=form)


@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])


@bp.route('/contact')
def contact():
    return render_template('contact.html', title=_('Contact Us'))
