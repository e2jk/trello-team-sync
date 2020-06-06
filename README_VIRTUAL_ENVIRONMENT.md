Virtual environment setup
=========================

Create the environment:
-----------------------
```bash
$ mkdir -p ~/.python-virtual-environment/syncboom
$ python3 -m venv ~/.python-virtual-environment/syncboom
$ pip3 install -r requirements.txt
```

Activate the virtual environment:
---------------------------------
`$ source ~/.python-virtual-environment/syncboom/bin/activate`

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
mkdir Documents\devel\venv\syncboom
AppData\Local\Programs\Python\Python38-32\python.exe -m venv Documents\devel\venv\syncboom
Documents\devel\venv\syncboom\Scripts\pip3.exe install -r Documents\devel\syncboom\requirements.txt
Documents\devel\venv\syncboom\Scripts\activate.bat
```
