from django.contrib import admin
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.views.static import serve
from django.urls import re_path

urlpatterns = [path("i18n/", include("django.conf.urls.i18n"))]
urlpatterns += i18n_patterns(path("admin/", admin.site.urls), path("", include("core.urls")))
urlpatterns += [re_path(r"^media/(?P<path>.*)$",serve,{"document_root":settings.MEDIA_ROOT})]
