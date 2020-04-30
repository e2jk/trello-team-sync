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

MS Windows equivalents:
-----------------------
```
mkdir Documents\devel\venv\trello-team-sync
AppData\Local\Programs\Python\Python38-32\python.exe -m venv Documents\devel\venv\trello-team-sync
Documents\devel\venv\trello-team-sync\Scripts\pip3.exe install -r Documents\devel\trello-team-sync\requirements.txt
Documents\devel\venv\trello-team-sync4\Scripts\activate.bat
```
