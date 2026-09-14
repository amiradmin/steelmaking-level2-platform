from __future__ import annotations

from django.urls import path

from . import views
from .access_control import roles as access_roles
from .access_control import user_detail as access_user_detail
from .access_control import users as access_users
from .ccm_dashboard import ccm_dashboard
from .eaf_dashboard import eaf_dashboard
from .heat_timeline import heat_timeline
from .lf_dashboard import lf_dashboard
from .materials_dashboard import materials_dashboard
from .overview_live import overview_live
from .plc_packets import plc_packets
from .plc_sources import plc_sources
from .production_flow import production_flow
from .system_map import live_system_map

urlpatterns = [
    path("auth/me", views.current_user, name="current-user"),
    path("access/roles", access_roles, name="access-roles"),
    path("access/users", access_users, name="access-users"),
    path("access/users/<int:user_id>", access_user_detail, name="access-user-detail"),
    path("meta", views.api_meta, name="api-meta"),
    path("overview-live", overview_live, name="overview-live"),
    path("eaf/dashboard", eaf_dashboard, name="eaf-dashboard"),
    path("lf/dashboard", lf_dashboard, name="lf-dashboard"),
    path("ccm/dashboard", ccm_dashboard, name="ccm-dashboard"),
    path("materials/dashboard", materials_dashboard, name="materials-dashboard"),
    path("production-flow", production_flow, name="production-flow"),
    path("plc-sources", plc_sources, name="plc-sources"),
    path("plc-packets", plc_packets, name="plc-packets"),
    path("system-map", live_system_map, name="live-system-map"),
    path("heats", views.list_heats, name="heat-list"),
    path("heats/<str:heat_no>", views.heat_detail, name="heat-detail"),
    path("heats/<str:heat_no>/overview", views.heat_overview, name="heat-overview"),
    path("heats/<str:heat_no>/timeline", heat_timeline, name="heat-timeline"),
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
