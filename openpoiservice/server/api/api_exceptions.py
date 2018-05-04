from openpoiservice.server.api import error_codes


class InvalidUsage(Exception):

    def __init__(self, status_code=500, error_code=None, message=None):
        """
        :param message: custom message
        :type message: string

        :param status_code: the HTTP status code
        :type status_code: integer

        :param payload: the optional payload
        :type payload: string
        """

        # type: (object, object, object) -> object
        Exception.__init__(self)

        if status_code is not None:
            self.status_code = status_code

            if message is None:
                message = error_codes[error_code]
            else:
                message = message

            self.error = {
                "code": error_code,
                "message": message
            }

    def to_dict(self):
        rv = dict(self.error or ())
        return rv
