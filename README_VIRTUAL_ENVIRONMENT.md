Virtual environment setup
=========================

Create the environment:
-----------------------
```bash
$ mkdir -p ~/.python-virtual-environment/trello-team-sync
$ python3 -m venv ~/.python-virtual-environment/trello-team-sync
$ pip3 install -r requirements.txt
```

Activate the virtual environment:
---------------------------------
`$ source ~/.python-virtual-environment/trello-team-sync/bin/activate`

When done:
----------
`$ deactivate`

Update the dependencies:
------------------------
`$ pip3 install -r requirements.txt`

First time creation/update of the dependencies:
-----------------------------------------------
`$ pip3 freeze > requirements.txt`
