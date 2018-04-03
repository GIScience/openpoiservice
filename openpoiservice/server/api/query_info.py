# openpoiservice/server/query_info.py
import time
import logging

logger = logging.getLogger(__name__)


class QueryInfo(object):
    """ Class that creates the query."""

    def __init__(self, payload):
        """
        Initializes the query builder.

        :param payload: processed GET or POST parameters
        :type payload: dict
        """

        self.attribution = "openrouteservice.org | OpenStreetMap contributors"
        self.version = "0.1"
        self.timestamp = int(time.time())
        self.query = payload





