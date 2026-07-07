import requests
from django.conf import settings
import sentry_sdk

from payplan.requests import nomba_request
from transactions.exceptions import NombaConnectionError