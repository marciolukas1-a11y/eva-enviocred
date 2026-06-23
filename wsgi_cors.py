"""
WSGI middleware que injeta CORS headers em todas as respostas.
Usado como wrapper do Flask app para resolver CORS sem flask-cors.
"""
from main import app as flask_app

class CORSMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def cors_start_response(status, headers, exc_info=None):
            headers = list(headers)
            headers.append(('Access-Control-Allow-Origin', '*'))
            headers.append(('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'))
            headers.append(('Access-Control-Allow-Headers', 'Content-Type'))
            return start_response(status, headers, exc_info)

        if environ.get('REQUEST_METHOD') == 'OPTIONS':
            cors_start_response('204 No Content', [('Content-Length', '0')])
            return [b'']

        return self.app(environ, cors_start_response)

app = CORSMiddleware(flask_app)
