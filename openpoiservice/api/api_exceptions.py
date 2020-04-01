error_codes = {
    4000: 'Invalid JSON object in request',
    4001: 'Category or category group ids missing',
    4002: 'Geometry is missing',
    4003: 'Bounding box and or geojson not present in request',
    4004: 'Buffer is missing',
    4005: 'Geometry length does not meet the restrictions',
    4006: 'Unsupported HTTP method',
    4007: 'GeoJSON issue',
    4008: 'Geometry size does not meet the restrictions',
    4099: 'Unknown internal error'
}

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
        Exception.__init__(self)

        if status_code is not None:
            self.status_code = status_code

            if message is None:
                message = error_codes[error_code]
            else:
                message = message

            self._error = {
                "code": error_code,
                "message": message
            }

    def to_dict(self):
        rv = dict(self._error or ())
        return rv
