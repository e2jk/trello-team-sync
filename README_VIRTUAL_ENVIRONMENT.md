Virtual environment setup
=========================

Create the environment:
-----------------------
```bash
$ cd devel/syncboom/
$ mkdir -p .venv-syncboom
$ python3 -m venv .venv-syncboom
$ source .venv-syncboom/bin/activate
$ pip3 install wheel
$ pip3 install -r requirements.txt
```

Activate the virtual environment:
---------------------------------
`$ source .venv-syncboom/bin/activate`

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
mkdir Documents\devel\syncboom\.venv-syncboom
AppData\Local\Programs\Python\Python38-32\python.exe -m venv Documents\devel\syncboom\.venv-syncboom
Documents\devel\syncboom\.venv-syncboom\Scripts\pip3.exe install -r Documents\devel\syncboom\requirements.txt
Documents\devel\syncboom\.venv-syncboom\Scripts\activate.bat
```
