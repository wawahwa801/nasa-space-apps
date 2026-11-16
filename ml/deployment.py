"""Published model and illustrative room API served by the container."""
from dashboard_simulation import build_app

app = build_app()
app.config["MAX_CONTENT_LENGTH"] = 16000
