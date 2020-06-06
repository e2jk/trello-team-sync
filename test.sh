coverage run --include=./*.py --omit=tests/*,app/cli.py,.venv-syncboom/* -m unittest discover && \
rm -rf html_dev/coverage && \
coverage html --directory=html_dev/coverage --title="Code test coverage for SyncBoom"
