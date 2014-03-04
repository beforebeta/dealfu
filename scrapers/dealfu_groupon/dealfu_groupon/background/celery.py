from __future__ import absolute_import
from celery import Celery

app = Celery('dealfu_groupon.background',
             broker='redis://192.168.0.113:6379/0',
             backend='redis://192.168.0.113:6379/0',
             include=['dealfu_groupon.background.retry',
                      'dealfu_groupon.background.example'])

# Optional configuration, see the application user guide.
app.conf.update(
    CELERY_TIMEZONE = 'Europe/London',
    CELERYD_MAX_TASKS_PER_CHILD=1 #we need that because of twisted reactor not being restartable
)

if __name__ == '__main__':
    app.start()