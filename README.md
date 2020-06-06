# SyncBoom
Syncing cards between different teams' Trello boards

[![Build Status](https://travis-ci.com/e2jk/syncboom.svg?branch=master)](https://travis-ci.com/e2jk/syncboom)
[![codecov](https://codecov.io/gh/e2jk/syncboom/branch/master/graph/badge.svg)](https://codecov.io/gh/e2jk/syncboom)
[![GitHub last commit](https://img.shields.io/github/last-commit/e2jk/syncboom.svg)](https://github.com/e2jk/syncboom/commits/master)


*********

**Disclaimer/Warning:** This tool gives you the ability to mass produce cards in Trello, and even to *delete all the cards* in Trello lists and boards. Create test boards/lists to test the tool out before pointing it to your production boards. You are the only one responsible for messing up your boards, or losing data!

What it does
============

This software enables you to "push" cards from one *Master* [Trello](https://trello.com) board onto one or multiple *destination lists*.\
This is achieved by adding *labels* to the *master cards* on the *master board*, and defining in a *configuration file* to which *destination list(s)* the cards that have these labels should be pushed towards.

Most of the content on the master cards will be copied over (such as attachments, checklists, comments, due dates, stickers), but note that labels and owners will not: there might be different labels on the destination lists that on the master board, and people owning the child cards might not have access to the master board.

Definitions:
------------

* Master board: the main Trello board from which cards should be selected to be duplicated onto *destination lists*
* Destination list: a "column" in Trello (usually on a separate board than the master board) to which the cards from the *master board* should be pushed towards
* Master card: A card from the *master board* that is flagged (see *Label* below) to be duplicated onto a *destination list*
* Child card: a copy of a master card, living on a destination list
* Labels: the mechanisms that drives which master cards should be copied to which destination list(s). One label can be configured to copy a card to multiple lists at once
* Configuration file: a text file that contains the IDs of the master board, the list of labels and to which destination lists these map, as well as technical information such as the key and token to access your Trello boards and cards.

How it works
============

There are three distinct components available:
- A script that allows you to do all the heavy lifting manually from the command-line
- A website providing multi-user functionality to sync cards for the boards they have access to
- `FUTURE` An API that exposes the working of the script

Different environments/configurations are supported, each having its own configuration file.

Script
------

[TODO: Describe what the script does]\
See below for examples calling the script, and the full help text of the script indicating which arguments are supported.

### Examples

* Configuration file

  * Create a new config file

    `$ python3 syncboom.py --new-config`

* Synchronization

  * Synchronize all cards on the master board

    `$ python3 syncboom.py --propagate`

  * Synchronize all cards on the master board, indicating what is going on

    `$ python3 syncboom.py --propagate --verbose`

  * Synchronize all cards from a specific list (which itself is on the master board) [replace `<list_id>` with the ID of the list]

    `$ python3 syncboom.py --propagate --list <list_id>`

  * Synchronize a specific card (which is on the master board) [replace `<card_id>` with the ID of the card]

    `$ python3 syncboom.py --propagate --card <card_id>`

* Webhooks

  * Set up a webhook that gets called each time an element on the master board gets modified

    `$ python3 syncboom.py --webhook --new`

  * List all the webhooks present for you account

    `$ python3 syncboom.py --webhook --list`

  * Delete the webhook for your master board

    `$ python3 syncboom.py --webhook --delete`

* Cleaning up (to be used in DEMO MODE only)

  * Delete all the cards from the destination lists and clean up the cards on the main board. **WARNING**: only to be used while testing, **YOU WILL LOSE ALL THE DATA** on the destination lists!

    `$ python3 syncboom.py --cleanup --debug`

### Script help text
```
$python3 syncboom.py --help
usage: syncboom.py [-h] (-p | -cu | -nc | -w {new,list,delete}) [-c CARD] [-l LIST] [-dr] [-cfg CONFIG] [-d] [-v]

Sync cards between different teams' Trello boards

optional arguments:
  -h, --help            show this help message and exit
  -p, --propagate       Propagate the master cards to the slave boards
  -cu, --cleanup        Clean up all master cards and delete all cards from the slave boards (ONLY TO BE USED IN DEMO MODE)
  -nc, --new-config     Create a new configuration file
  -w {new,list,delete}, --webhook {new,list,delete}
                        Create new, list or delete existing webhooks
  -c CARD, --card CARD  Specify which master card to propagate. Only to be used in conjunction with --propagate
  -l LIST, --list LIST  Specify which master list to propagate. Only to be used in conjunction with --propagate
  -dr, --dry-run        Do not create, update or delete any records
  -cfg CONFIG, --config CONFIG
                        Path to the configuration file to use
  -d, --debug           Print lots of debugging statements
  -v, --verbose         Be verbose
```

Website
-------
The website allows users to set up, configure and manage the syncing of cards between boards to which they have access to.

### Running the website

  `$ flask run`

### Running tasks

Launch a worker:

`$ rq worker syncboom-tasks`

You will need to have installed Redis on your system beforehand. For example, on a Debian-based machine:

  `$ sudo apt install redis`

### How to test sending emails from the website

The following section is copied from Miguel Grinberg's wonderful [Flask Mega-Tutorial, Part VII: Error Handling](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-vii-error-handling):\
There are two approaches to test this feature. The easiest one is to use the SMTP debugging server from Python. This is a fake email server that accepts emails, but instead of sending them, it prints them to the console. To run this server, open a second terminal session and run the following command on it:

  `$ python3 -m smtpd -n -c DebuggingServer localhost:8025`

Leave the debugging SMTP server running and go back to your first terminal and set `export MAIL_SERVER=localhost` and `MAIL_PORT=8025` in the environment (use `set` instead of `export` if you are using Microsoft Windows). Make sure the `FLASK_DEBUG` variable is set to 0 or not set at all, since the application will not send emails in debug mode.

API
---
**TO BE DEVELOPED**\
The API provides the glue between the script and the website.\
[TODO: Create the API and document it here]

Configuration file
------------------

The `--cleanup` argument will only work if the boards that are allowed to be cleaned up (i.e. all the cards on all their lists get deleted) are listed in the `cleanup_boards` section of the configuration file.

[TODO: Give examples of config files]


Miscellaneous
=============

Software created by [Emilien Klein](https://github.com/e2jk).
