# coding: utf-8

import sys
import socket
import selectors
import datetime
import time
import html

DEFAULT_ERROR_MESSAGE = """\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
        "http://www.w3.org/TR/html4/strict.dtd">
<html>
    <head>
        <meta http-equiv="Content-Type" content="text/html;charset=utf-8">
        <title>Error</title>
    </head>
    <body>
        <h1>Error response</h1>
        <p>Error code: %(code)d</p>
        <p>Message: %(message)s.</p>
        <p>Error code explanation: %(code)s - %(explain)s.</p>
    </body>
</html>
"""


class HTTPServer(object):
    def __init__(self, server_address, RequestHandlerClass):
        self.server_address = server_address
        self.RequestHandlerClass = RequestHandlerClass
        self.request_queue_size = 5
        self.__shutdown_request = False

        # create TCP Socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # bind socket
            self.server_bind()
            # listen to port
            self.server_activate()
        except:
            # close socket
            self.server_close()
            raise

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

    def server_activate(self):
        self.socket.listen(self.request_queue_size)

    def server_close(self):
        self.socket.close()

    def serve_forever(self, poll_interval=0.5):
        with selectors.SelectSelector() as selector:
            # get a ready readable handle based on select polling
            selector.register(self, selectors.EVENT_READ)
            while True:
                ready = selector.select(poll_interval)
                if ready:
                    # if there is a ready readable file handle, the link is established
                    self._handle_request_noblock()

    def fileno(self):
        """
        return socket fileno
        for select monitor file handle status
        """
        return self.socket.fileno()

    def _handle_request_noblock(self):
        try:
            request, client_address = self.get_request()
        except socket.error:
            return

        try:
            self.process_request(request, client_address)
        except:
            self.handle_error(client_address)
            self.shutdown_request(request)

    def get_request(self):
        return self.socket.accept()

    def process_request(self, request, client_address):
        self.handle_request(request, client_address)
        self.shutdown_request(request)

    def handle_request(self, request, client_address):
        self.RequestHandlerClass(request, client_address, self)  # self is HTTPServer itself

    def handle_error(self, client_address):
        print('-' * 40, file=sys.stderr)
        print('Exception occurred during processing of request from', client_address, file=sys.stderr)
        import traceback
        traceback.print_exc()
        print('-' * 40, file=sys.stderr)

    def shutdown_request(self, request):
        try:
            request.shutdown(socket.SHUT_WR)
        except socket.error:
            pass  # some platforms may raise ENOTCONN here
        request.close()


class HTTPRequestHandler(object):
    responses = {
        100: ('Continue', 'Request received, please continue'),
        101: ('Switching Protocols', 'Switching to new protocol; obey Upgrade header'),

        200: ('OK', 'Request fulfilled, document follows'),
        201: ('Created', 'Document created, URL follows'),
        202: ('Accepted', 'Request accepted, processing continues off-line'),
        203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
        204: ('No Content', 'Request fulfilled, nothing follows'),
        205: ('Reset Content', 'Clear input form for further input.'),
        206: ('Partial Content', 'Partial content follows.'),

        300: ('Multiple Choices', 'Object has several resources -- see URI list'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        302: ('Found', 'Object moved temporarily -- see URI list'),
        303: ('See Other', 'Object moved -- see Method and URL list'),
        304: ('Not Modified', 'Document has not changed since given time'),
        305: ('Use Proxy', 'You must use proxy specified in Location to access this resource.'),
        307: ('Temporary Redirect', 'Object moved temporarily -- see URI list'),

        400: ('Bad Request', 'Bad request syntax or unsupported method'),
        401: ('Unauthorized', 'No permission -- see authorization schemes'),
        402: ('Payment Required', 'No payment -- see charging schemes'),
        403: ('Forbidden', 'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed', 'Specified method is invalid for this resource.'),
        406: ('Not Acceptable', 'URI not available in preferred format.'),
        407: ('Proxy Authentication Required', 'You must authenticate with this proxy before proceeding.'),
        408: ('Request Timeout', 'Request timed out; try again later.'),
        409: ('Conflict', 'Request conflict.'),
        410: ('Gone', 'URI no longer exists and has been permanently removed.'),
        411: ('Length Required', 'Client must specify Content-Length.'),
        412: ('Precondition Failed', 'Precondition in headers is false.'),
        413: ('Request Entity Too Large', 'Entity is too large.'),
        414: ('Request-URI Too Long', 'URI is too long.'),
        415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
        416: ('Requested Range Not Satisfiable', 'Cannot satisfy request range.'),
        417: ('Expectation Failed', 'Expect condition could not be satisfied.'),

        500: ('Internal Server Error', 'Server got itself in trouble'),
        501: ('Not Implemented', 'Server does not support this operation'),
        502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
        503: ('Service Unavailable', 'The server cannot process the request due to a high load'),
        504: ('Gateway Timeout', 'The gateway server did not receive a timely response'),
        505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
    }

    def __init__(self, request, client_address, server):
        self.max_header_size = 65536
        self.request = request
        self.client_address = client_address
        self.server = server
        self.protocol_version = "HTTP/1.0"
        self.setup()
        try:
            self.handle()
        finally:
            self.finish()

    def setup(self):
        self.connection = self.request
        self.rfile = self.connection.makefile('rb', -1)  # buffering use the system default
        self.wfile = self.connection.makefile('wb', 0)  # 0 means unbuffered

    def log_message(self, format, *args):
        log_data_time_string = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        sys.stderr.write("%s - [%s] %s\n" % (self.client_address[0], log_data_time_string, format % args))

    def log_request(self, code='-', size='-'):
        self.log_message('"%s" %s %s', self.request_line, str(code), str(size))

    def log_error(self, format, *args):
        self.log_message(format, *args)

    def handle(self):
        try:
            self.raw_request_line = self.rfile.readline(self.max_header_size + 1)
            if len(self.raw_request_line) > self.max_header_size:
                self.request_line = ''
                self.request_version = ''
                self.command = ''
                self.send_error(414)
                return
            if not self.parse_request():
                return
            # specific method of processing the request do_method, such as: do_get, do_post
            mname = ('do_' + self.command).lower()
            if not hasattr(self, mname):
                self.send_error(501, "Unsupported method (%r)" % self.command)
                return
            method = getattr(self, mname)
            method()
            # return response
            self.wfile.flush()
        except socket.timeout as e:
            self.log_error("Request timed out: %r", e)
            return

    def finish(self):
        if not self.wfile.closed:
            try:
                self.wfile.flush()
            except socket.error:
                pass
        self.wfile.close()
        self.rfile.close()

    def parse_request(self):
        self.command = None  # set in case of error on the first line
        self.request_version = version = "HTTP/1.0"
        # request format：
        # """
        # {HTTP method} {PATH} {HTTP version}\r\n 66536
        # {header field name}:{field value}\r\n  65536
        # ...
        # \r\n
        # {request body}
        # """
        request_line = str(self.raw_request_line, 'iso-8859-1')
        request_line = request_line.rstrip('\r\n')
        self.request_line = request_line
        words = request_line.split()
        if len(words) == 3:
            # HTTP method, PATH, HTTP version
            command, path, version = words
            if version[:5] != 'HTTP/':
                self.send_error(400, "Bad request version (%r)" % version)
                return False
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
                if version_number >= (2, 0):
                    self.send_error(505, "Invalid HTTP Version (%s)" % base_version_number)
                    return False
            except (ValueError, IndexError):
                self.send_error(400, "Bad request version (%r)" % version)
                return False

        elif len(words) == 2:
            # if there is no HTTP version, use the default version ie: HTTP/1.0
            command, path = words
        elif not words:
            return False
        else:
            self.send_error(400, "Bad request syntax (%r)" % request_line)
            return False

        self.command, self.path, self.request_version = command, path, version

        self.headers = self.parse_headers()
        return True

    def parse_headers(self):
        headers = {}
        while True:
            line = self.rfile.readline()
            if line in (b'\r\n', b'\n', b''):
                break
            line_str = str(line, 'utf-8')
            key, value = line_str.split(': ')
            headers[key] = value.strip()
        return headers

    def send_error(self, code, message=None):
        try:
            short, long = self.responses[code]
        except KeyError:
            short, long = '???', '???'
        if message is None:
            message = short
        explain = long
        self.log_error("code %d, message %s", code, message)
        self.send_response_header(code, message)
        content = None
        if code > 200 and code not in (204, 205, 304):
            content = (DEFAULT_ERROR_MESSAGE % {
                'code': code,
                'message': html.escape(message),
                'explain': explain
            })
            self.send_header("Content-Type", "text/html;charset=utf-8")
        self.end_headers()
        body = content.encode('utf-8', errors='replace')  # unencodable unicode to ?
        if self.command != 'HEAD' and content:
            self.wfile.write(body)

    def send_response_header(self, code, message=None):
        self.log_request(code)
        if message is None:
            if code in self.responses:
                message = self.responses[code][0]
            else:
                message = ''
        # response format：
        # """
        # {HTTP version} {status code} {status phrase}\r\n
        # {header field name}:{field value}\r\n
        # ...
        # \r\n
        # {response body}
        # """

        self.wfile.write(("%s %d %s\r\n" % (self.protocol_version, code, message)).encode('latin-1', 'strict'))
        self.send_header('Server', "Python " + sys.version.split()[0])
        self.send_header('Date', self.date_time_string())

    def send_header(self, keyword, value):
        self.wfile.write(("%s: %s\r\n" % (keyword, value)).encode('latin-1', 'strict'))

    def end_headers(self):
        self.wfile.write(b"\r\n")

    @staticmethod
    def date_time_string(timestamp=None):
        weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        monthname = [None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        if timestamp is None:
            timestamp = time.time()
        year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
        s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
            weekdayname[wd],
            day, monthname[month],
            year, hh, mm, ss)
        return s


class RequestHandler(HTTPRequestHandler):
    def handle_index(self):
        page = '''
        <html>
        <body>
        <p>Hello, Web Server!</p>
        </body>
        </html>
        '''
        self.send_response_header(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))

    def handle_favicon(self):
        page = '''
        <html>
        <body>
        <p>Unknown</p>
        </body>
        </html>
        '''
        self.send_response_header(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page.encode('utf-8'))

    def do_get(self):
        if self.path == '/':
            self.handle_index()
        elif self.path.startswith('/favicon'):
            self.handle_favicon()
        else:
            self.send_error(404)


if __name__ == '__main__':
    server = HTTPServer(('', 8080), RequestHandler)
    server.serve_forever()
