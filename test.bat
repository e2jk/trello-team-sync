@echo off
coverage run --include=./*.py --omit=tests/* -m unittest discover
rd /s /q html_dev\coverage
coverage html --directory=html_dev\coverage --title="Code test coverage for trello-team-sync"
