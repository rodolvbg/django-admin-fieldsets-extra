from django.contrib import admin
from django.urls import path

from tests.admin import controls_site, unfold_site
from tests.admin import site as test_admin_site

urlpatterns = [
    path("admin/", admin.site.urls),
    path("test-admin/", test_admin_site.urls),
]
if controls_site is not None:
    urlpatterns.append(path("controls-admin/", controls_site.urls))
if unfold_site is not None:
    urlpatterns.append(path("unfold-admin/", unfold_site.urls))
