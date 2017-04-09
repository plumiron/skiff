"""
Skiff is a simple WSGI web-framework.
"""

__author__ = 'plumiron'
__version__ = '0.1.0'
__license__ = 'MIT'

from collections import defaultdict
from http.cookies import SimpleCookie
import re
import threading
import urllib


HTTP_CODES = {
    100: 'CONTINUE',
    101: 'SWITCHING PROTOCOLS',
    200: 'OK',
    201: 'CREATED',
    202: 'ACCEPTED',
    203: 'NON-AUTHORITATIVE INFORMATION',
    204: 'NO CONTENT',
    205: 'RESET CONTENT',
    206: 'PARTIAL CONTENT',
    300: 'MULTIPLE CHOICES',
    301: 'MOVED PERMANENTLY',
    302: 'FOUND',
    303: 'SEE OTHER',
    304: 'NOT MODIFIED',
    305: 'USE PROXY',
    306: 'RESERVED',
    307: 'TEMPORARY REDIRECT',
    400: 'BAD REQUEST',
    401: 'UNAUTHORIZED',
    402: 'PAYMENT REQUIRED',
    403: 'FORBIDDEN',
    404: 'NOT FOUND',
    405: 'METHOD NOT ALLOWED',
    406: 'NOT ACCEPTABLE',
    407: 'PROXY AUTHENTICATION REQUIRED',
    408: 'REQUEST TIMEOUT',
    409: 'CONFLICT',
    410: 'GONE',
    411: 'LENGTH REQUIRED',
    412: 'PRECONDITION FAILED',
    413: 'REQUEST ENTITY TOO LARGE',
    414: 'REQUEST-URI TOO LONG',
    415: 'UNSUPPORTED MEDIA TYPE',
    416: 'REQUESTED RANGE NOT SATISFIABLE',
    417: 'EXPECTATION FAILED',
    500: 'INTERNAL SERVER ERROR',
    501: 'NOT IMPLEMENTED',
    502: 'BAD GATEWAY',
    503: 'SERVICE UNAVAILABLE',
    504: 'GATEWAY TIMEOUT',
    505: 'HTTP VERSION NOT SUPPORTED',
}


# --------------------------------------------------
# error handling


class SkiffException(Exception):
    pass


class HttpError(SkiffException):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message

    def __str__(self):
        return "{} {}".format(self.status_code, self.message)


def _default_error_handler(exception):
    status_code = getattr(exception, 'status_code', 500)
    path = request.path
    content = 'Error on {}: {}'.format(path, exception)
    resonpse = make_response(content, status_code)
    return response


# --------------------------------------------------
# request and response


class Request(threading.local):
    def bind(self, environ):
        self._environ = environ
        self._cookie = None
        self._params = None

    @property
    def content_length(self):
        return self._environ.get('CONTENT_LENGTH', 0)

    @property
    def content_type(self):
        return self._environ.get('CONTENT_TYPE', 'text/html')

    @property
    def cookie(self):
        if not cookie:
            self._cookie = SimpleCookie(self._environ.get('HTTP_COOKIE', ''))
        return self._cookie

    @property
    def method(self):
        return self._environ.get('REQUEST_METHOD', 'GET')

    @property
    def params(self):
        if not self._params:
            self._params = urllib.parse.parse_qs(self.query_string, keep_blank_values=True)
        return self._params

    @property
    def path(self):
        return self._environ.get('PATH_INFO', '/')

    @property
    def query_string(self):
        return self._environ.get('QUERY_STRING', '')

    @property
    def server_name(self):
        return self._environ.get('SERVER_NAME', '')

    @property
    def server_port(self):
        return self._environ.get('SERVER_PORT', 0)


class Response(threading.local):
    def bind(self):
        self._content = ''
        self._cookie = None
        self._status_code = 200
        self._headers = {
            'Content-type': 'text/html',
            'Content-Length': str(len(self._content)),
        }

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        self._content = value
        self._headers['Content-Length'] = str(len(self._content))

    @property
    def cookie(self):
        if not self._cookie:
            self._cookie = SimpleCookie()
        return self._cookie

    @property
    def headers(self):
        return self._headers

    def set_cookie(self, key, value, **kargs):
        if not self._cookie:
            self._cookie = SimpleCookie()
        self._cookie[key] = value
        for k, v in kargs.items():
            self._cookie[key][k] = v

    @property
    def status(self):
        return '{} {}'.format(self.status_code, HTTP_CODES[self.status_code])

    @property
    def status_code(self):
        return self._status_code

    @status_code.setter
    def status_code(self, value):
        if value not in HTTP_CODES:
            raise SkiffException('{} is an invalid status code'.format(value))
        self._status_code = value


def make_response(content='', status_code=200, headers={}):
    response.content = content
    response.status_code = status_code
    response.headers.update(headers)
    return response


request = Request()
response = Response()


# --------------------------------------------------
# path matching


def _replace_with_regex(match):
    if match.group('type') == 'int':
        return r'(?P<{}>[1-9]\d*)'.format(match.group('var'))
    else:
        return r'(?P<{}>\w+)'.format(match.group('var'))


# --------------------------------------------------
# application


class Skiff:
    def __init__(self, **kargs):
        self._kargs = kargs
        self._simple_routes = defaultdict(dict)
        self._regex_routes = defaultdict(dict)
        self._error_handlers = dict()

    def error_handler(self, status_code):
        def _error_handler(handler):
            if status_code in self._error_handlers:
                raise SkiffException('There is already a hanlder for error {}.'.format(status_code))
            self._error_handlers[status_code] = handler
            return handler
        return _error_handler

    def match_path(self, path, method):
        view_func = self._simple_routes[method].get(path, None)
        if view_func:
            return (view_func, dict())
        
        for regex, view_func in self._regex_routes[method].items():
            match = regex.match(path)
            if match:
                return (view_func, match.groupdict())
        
        raise HttpError(404, 'Page not found')

    def wsgi_app(self, environ, start_response):
        global request
        global response
        request.bind(environ)
        response.bind()
        
        try:
            view_func, kargs = self.match_path(request.path, request.method)
            data = view_func(**kargs)
        except Exception as e:
            status_code = getattr(e, 'status_code', 500)
            handler = self._error_handlers.get(status_code, _default_error_handler)
            data = handler(e)
        
        if isinstance(data, Response):
            response = data
        elif isinstance(data, (str, bytes)):
            response = make_response(data)
        elif isinstance(data, tuple):
            response = make_response(*data)
        else:
            raise SkiffException('Invalid data')
        
        if not isinstance(response.content, bytes):
            response.content = response.content.encode('utf-8')

        # TODO support cookie
        #for v in response.cookie.values():
        #    response.headers.add('Set-Cookie', c.OutputString())

        start_response(response.status, list(response.headers.items()))
        return [response.content]

    def route(self, path, methods=['GET']):
        def _route(view_func):
            if re.search(r'<[\w:]+>', path):
                regex = re.sub(r'<((?P<type>\w+):)?(?P<var>\w+)>', _replace_with_regex, path)
                regex = re.compile('^{}$'.format(regex))
                for method in methods:
                    if regex in self._regex_routes[method]:
                        raise SkiffException(
                            'Route ("{}", {}, {}) is already registered.'.format(
                                path, view_func.__name__, method
                            )
                        )
                    self._regex_routes[method][regex] = view_func
            else:
                for method in methods:
                    if path in self._simple_routes[method]:
                        raise SkiffException(
                            'Route ("{}", {}, {}) is already registered.'.format(
                                path, view_func.__name__, method
                            )
                        )
                    self._simple_routes[method][path] = view_func
            return view_func
        return _route

    def run(self, host='127.0.0.1', port=8080):
        from wsgiref.simple_server import make_server
        server = make_server(host, port, self.wsgi_app)
        server.serve_forever()

