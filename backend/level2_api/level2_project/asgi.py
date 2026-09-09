from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "level2_project.settings")

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

from api.routing import websocket_urlpatterns  # noqa: E402


django_asgi_application = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
