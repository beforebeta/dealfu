from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView

from dealfu.views import DealsDetailView, DealsListView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()


urlpatterns = patterns('',
    url(r'^$', TemplateView.as_view(template_name='base.html')),

    # Examples:
    # url(r'^$', 'rediser.views.home', name='home'),
    # url(r'^rediser/', include('rediser.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    #the restframework url endpoint
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'api/deals/(?P<pk>[a-zA-Z0-9_\-]+)/$', DealsDetailView.as_view(), name="deals_detail"),
    url(r'api/deals/$', DealsListView.as_view(), name="deals_list"),
)
