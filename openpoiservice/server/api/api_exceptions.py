class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        """
        INVALID_JSON_FORMAT = 400
        MISSING_PARAMETER = 401
        INVALID_PARAMETER_FORMAT = 402
        INVALID_PARAMETER_VALUE = 403
        PARAMETER_VALUE_EXCEEDS_MAXIMUM = 404
        UNKNOWN = 499

        :param message: custom message
        :type message: string

        :param status_code: the HTTP status code
        :type status_code: integer

        :param payload: the optional payload
        :type payload: string
        """

        # type: (object, object, object) -> object
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

