"""Installed central entrypoint. Do not serve app.main directly in deployments."""
import os
from app.main import app as workspace
from app.entry_boundary import LocalOnly

app=LocalOnly(workspace,os.environ.get('MAZANDASHT_DESKTOP_TOKEN'))
