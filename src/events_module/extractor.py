import subprocess
import json
from config import env_config as config


def read_event_logs():

    # Read the file from E2S
    # TODO: How would the script read this file?
    file = config.LOGS_FILE_PATH
    with open(file, "r") as logs:
        events = json.loads(logs.read())
    return events
