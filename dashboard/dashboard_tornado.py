from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from web import app
from tornado import autoreload
import logging
import sys

logging.getLogger('tornado').setLevel(logging.DEBUG)
logging.getLogger(__name__).setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)

logging.getLogger('tornado').addHandler(handler)
logging.getLogger(__name__).addHandler(handler)

http_server = HTTPServer(WSGIContainer(app))
http_server.bind(port=8000, address="0.0.0.0")
http_server.start(0)
ioloop = IOLoop.instance()
autoreload.start(ioloop)
ioloop.start()
