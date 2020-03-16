# openpoiservice/server/api/__init__.py

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
