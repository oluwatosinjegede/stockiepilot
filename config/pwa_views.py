from django.http import FileResponse, HttpResponse
from django.conf import settings
from pathlib import Path
import json

BASE_DIR = Path(settings.BASE_DIR)

def manifest(request):
    manifest_data = {
        "name": "StockiePilot",
        "short_name": "StockiePilot",
        "description": "Inventory, sales tracking, analytics, and POS in one secure platform.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#1d4ed8",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            },
            {
                "src": "/static/icons/maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable"
            }
        ]
    }
    return HttpResponse(
        json.dumps(manifest_data),
        content_type="application/manifest+json"
    )

def service_worker(request):
    sw_path = BASE_DIR / "static" / "js" / "sw.js"
    return FileResponse(open(sw_path, "rb"), content_type="application/javascript")