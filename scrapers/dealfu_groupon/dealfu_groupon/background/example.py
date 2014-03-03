import time
from dealfu_groupon.background.celery import app


@app.task
def some_long_operation():
    time.sleep(5)
    return "DONE"


@app.task
def mul(x, y):
    return x * y
