#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of SyncBoom and is MIT-licensed.
#    Originally based on microblog, licensed under the MIT License.

from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, send_from_directory
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from guess_language import guess_language
from app import db
from app.main.forms import makeAccountEditForm
from app.models import User, Notification
from app.main import bp
from syncboom import perform_request


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    g.locale = str(get_locale())


@bp.route('/')
def index():
    if current_user.is_authenticated:
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
        return render_template('index_loggedin.html', title=_('Home'),
            trello_authorizing_url=trello_authorizing_url)
    else:
        return render_template('index_not_loggedin.html', title=_('Welcome'))


@bp.route('/account')
@bp.route('/account/edit/<any(username, email, password):edit_element>',
    methods=['GET', 'POST'])
@login_required
def account(edit_element=None):
    trello_details = perform_request("GET", "members/me",
        key=current_app.config['TRELLO_API_KEY'],
        token=current_user.trello_token)
    trello_username=trello_details["username"]
    if not edit_element:
        return render_template('account.html', title=_('Account'),
            trello_username=trello_username)
    else:
        original_value = getattr(current_user, edit_element) \
            if hasattr(current_user, edit_element) else ""
        form = makeAccountEditForm(edit_element, original_value)
        if form.validate_on_submit():
            if edit_element != "password":
                setattr(current_user, edit_element,
                    getattr(form, edit_element).data.lower())
            else:
                current_user.set_password(form.password.data)
            db.session.commit()
            flash(_('Your %s has been updated.' % edit_element))
            return redirect(url_for('main.account'))
        elif request.method == 'GET':
            getattr(form, edit_element).data = original_value.lower()
        return render_template('account_edit.html',
            title=_('Edit %s' % edit_element), form=form,
            trello_username=trello_username)


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


@bp.route('/pricing')
def pricing():
    return render_template('pricing.html', title=_('Pricing'))


@bp.route('/privacy')
def privacy():
    return render_template('privacy.html', title=_('Privacy Policy'))


@bp.route('/legal')
def legal():
    return render_template('legal.html', title=_('Terms and Conditions'))

@bp.route('/robots.txt')
@bp.route('/sitemap.txt')
def static_from_root():
    return send_from_directory(current_app.static_folder, request.path[1:])
