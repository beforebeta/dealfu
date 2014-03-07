from __future__ import absolute_import
from celery import Celery
from dealfu_groupon.utils import from_obj_settings

app = Celery('dealfu_groupon.background',
             broker='redis://192.168.0.113:6379/0',
             backend='redis://192.168.0.113:6379/0',
             include=['dealfu_groupon.background.retry',
                      'dealfu_groupon.background.example',
                      'dealfu_groupon.background.geocode'])

# Optional configuration, see the application user guide.
app.conf.update(
    CELERY_TIMEZONE = 'Europe/London',
    CELERYD_MAX_TASKS_PER_CHILD=1, #we need that because of twisted reactor not being restartable
    CELERY_CREATE_MISSING_QUEUES=True,
    CELERY_ROUTES = {'dealfu_groupon.background.geocode.process_geo_requests': {'queue': 'geolong'}}
)


from celery.signals import celeryd_after_setup


@celeryd_after_setup.connect
def setup_direct_queue(sender, instance, **kwargs):
    #should find here a way fro different settings right !
    from dealfu_groupon import settings
    from dealfu_groupon.background.geocode import process_geo_requests

    #we need that one to be startd when system is up
    settings_dict = from_obj_settings(settings)
    process_geo_requests.delay(settings_dict)



if __name__ == '__main__':
    app.start()