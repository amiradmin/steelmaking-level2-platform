from __future__ import annotations

from django.urls import path

from . import views

urlpatterns = [
    path("auth/me", views.current_user, name="current-user"),
    path("meta", views.api_meta, name="api-meta"),
    path("heats", views.list_heats, name="heat-list"),
    path("heats/<str:heat_no>", views.heat_detail, name="heat-detail"),
    path("heats/<str:heat_no>/overview", views.heat_overview, name="heat-overview"),
    path("equipment", views.equipment, name="equipment"),
    path("steel-grades", views.steel_grades, name="steel-grades"),
    path("events", views.events, name="events"),
    path("alarms", views.alarms, name="alarms"),
    path("historian/latest", views.historian_latest, name="historian-latest"),
    path(
        "historian/tags/<path:tag_name>/samples",
        views.historian_tag_samples,
        name="historian-tag-samples",
    ),
]
