from django.conf.urls import url
from mayx import views

urlpatterns = (
    url(r'^login/$', views.login, name="login"),
    url(r'^reg/$', views.reg, name="reg"),
    url(r'^$', views.containerview, name="containerview"),
    url(r'^public/(?P<account>.+?)/(?P<container>.+?)/(?P<prefix>(.+)+)?$',
        views.public_objectview, name="public_objectview"),
    url(r'^toggle_public/(?P<container>.+?)/$', views.toggle_public,
        name="toggle_public"),
    url(r'^tempurl/(?P<container>.+?)/(?P<objectname>.+?)$', views.tempurl,
        name="tempurl"),
    url(r'^viewfile/(?P<container>.+?)/(?P<objectname>.+?)$', views.viewfile,
        name="viewfile"),
    url(r'^copysource/(?P<container>.+?)/(?P<objectname>.+?)$', views.copysource,
        name="copysource"),
    url(r'^movesource/(?P<container>.+?)/(?P<objectname>.+?)$', views.movesource,
        name="movesource"),
    url(r'^upload/(?P<container>.+?)/(?P<prefix>.+)?$', views.upload, name="upload"),
    url(r'^copydest/(?P<container>.+?)/(?P<prefix>.+)?$', views.copydest, name="copydest"),
    url(r'^create_pseudofolder/(?P<container>.+?)/(?P<prefix>.+)?$',
        views.create_pseudofolder, name="create_pseudofolder"),
    url(r'^create_container$', views.create_container, name="create_container"),
    url(r'^delete_container/(?P<container>.+?)$', views.delete_container,
        name="delete_container"),
    url(r'^download/(?P<container>.+?)/(?P<objectname>.+?)$', views.download,
        name="download"),
    url(r'^delete/(?P<container>.+?)/(?P<objectname>.+?)$', views.delete_object,
        name="delete_object"),
    url(r'^objects/(?P<container>.+?)/(?P<prefix>(.+)+)?$', views.objectview,
        name="objectview"),
    url(r'^acls/(?P<container>.+?)/$', views.edit_acl, name="edit_acl"),
)
