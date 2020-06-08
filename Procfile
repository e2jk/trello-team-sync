web: flask db upgrade; gunicorn website:app
worker: rq worker -u $REDIS_URL syncboom-tasks
