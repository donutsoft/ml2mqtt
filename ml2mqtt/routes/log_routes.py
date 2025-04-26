from flask import Blueprint, render_template
from io import StringIO

log_bp = Blueprint('log', __name__)

def init_log_routes(log_stream: StringIO):
    @log_bp.route("/logs")
    def logs() -> str:
        return render_template("logs.html", logs=logs, active_page="logs")

    @log_bp.route("/logs/raw")
    def logsRaw() -> str:
        logLines = log_stream.getvalue().splitlines()
        return render_template("logs_raw.html", logs=logLines)

    return log_bp 