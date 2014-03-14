from __future__ import absolute_import
from celery import Celery
from dealfu_groupon.utils import from_obj_settings
from scrapy.utils.project import get_project_settings

settings = get_project_settings()

app = Celery('dealfu_groupon.background',
             broker='redis://{0}:{1}/0'.format(settings.get("REDIS_HOST"),
                                               str(settings.get("REDIS_PORT"))),
             backend='redis://{0}:{1}/0'.format(settings.get("REDIS_HOST"),
                                               str(settings.get("REDIS_PORT"))),
             include=['dealfu_groupon.background.retry',
                      'dealfu_groupon.background.geocode',
                      'dealfu_groupon.background.geopoll'
             ])


# Optional configuration, see the application user guide.
app.conf.update(
    CELERY_TIMEZONE = 'Europe/London',
    CELERYD_MAX_TASKS_PER_CHILD=1, #we need that because of twisted reactor not being restartable
    CELERY_CREATE_MISSING_QUEUES=True,
    CELERY_ROUTES = {
        'dealfu_groupon.background.geopoll.process_geo_requests': {'queue': 'geolong'},
        'dealfu_groupon.background.retry.retry_document': {'queue': 'retryq'}
    }
)


from celery.signals import celeryd_after_setup


@celeryd_after_setup.connect
def setup_direct_queue(sender, instance, **kwargs):
    #should find here a way fro different settings right !
    from dealfu_groupon.background.geopoll import process_geo_requests

    #we need that one to be startd when system is up
    settings = get_project_settings()
    settings = from_obj_settings(settings)

    process_geo_requests.delay(settings)



if __name__ == '__main__':
    app.start()