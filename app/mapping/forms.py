#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    This file is part of trello-team-sync and is MIT-licensed.

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, \
    SelectMultipleField
from wtforms import widgets
from wtforms.validators import DataRequired, Regexp
from flask_babel import _, lazy_gettext as _l


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class NewMappingForm(FlaskForm):
    name = StringField(_l('Mapping name'), validators=[DataRequired()])
    description = TextAreaField(_l('Mapping description (optional)'))
    tku = '<a href="https://trello.com/app-key">https://trello.com/app-key</a>'
    token = StringField(_l('Trello token'),
        description=_l('Your Trello token can be created by clicking on the ' \
        '"token" link on top of the at %(url)s page.', url=tku),
        validators=[DataRequired(), Regexp("^[0-9a-fA-F]{64}$",
            message=_l('Invalid Trello token format, it must be a 64 character string.'))])
    master_board = SelectField(_l('Master board'), coerce=str)
    labels = MultiCheckboxField(_l('Which labels need mapping?'), coerce=str, \
        render_kw={'style':'height: auto; list-style: none;'})

# Add 100 fields to map labels to lists
for i in range(100):
    setattr(NewMappingForm, "map_label%d_lists" % i,
        MultiCheckboxField(_l('Map label XX to which Trello lists?'), coerce=str, \
            render_kw={'style':'height: auto; list-style: none;'}))
# Add the Submit button after all the fields
setattr(NewMappingForm, "submit", SubmitField(_l('Submit')))


class DeleteMappingForm(FlaskForm):
    submit = SubmitField(_l('Delete mapping'))


class RunMappingForm(FlaskForm):
    submit_board = SubmitField(_l('Process the entire master board'))
    lists = SelectField(_l('List'), coerce=str,
        validators=[Regexp("^[0-9a-fA-F]{24}$",
        message=_l('Invalid Trello list ID format, it must be a 24 character string.'))])
    submit_list = SubmitField(_l('Process all cards on this list'))
    cards = SelectField(_l('Card'), coerce=str,
        validators=[Regexp("^[0-9a-fA-F]{24}$",
        message=_l('Invalid Trello card ID format, it must be a 24 character string.'))])
    submit_card = SubmitField(_l('Process only this specific card'))
