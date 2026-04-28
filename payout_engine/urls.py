from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("core.urls")),
    path("", TemplateView.as_view(template_name="index.html"), name="frontend"),
    re_path(
        r"^(?!api/v1/|admin/|static/).*$",
        TemplateView.as_view(template_name="index.html"),
        name="frontend-catchall",
    ),
]
