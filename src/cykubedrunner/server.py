import datetime
import email.utils
import os
import socketserver
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from time import time, sleep

import httpx
from httpx import RemoteProtocolError
from loguru import logger

from cykubedrunner.common.exceptions import BuildFailedException
from cykubedrunner.common.schemas import Project
from cykubedrunner.settings import settings
from cykubedrunner.utils import runcmd


class ServerThread(threading.Thread):
    """
    Trivial thread using a specific Single Page App handler (as we always want to return the index file if
    the path isn't a real file)
    """
    def __init__(self, project: Project):
        self.port = project.server_port or 0
        self.httpd = None
        self.server_cmd = project.server_cmd

    def run(self):
        if self.server_cmd:
            # run the command - blocks till completion
            try:
                runcmd(self.server_cmd, cmd=True)
            except BuildFailedException as ex:
                logger.error(f"Server command failed with status code {ex.status_code}")
                return
        else:
            try:
                with socketserver.TCPServer(("", self.port or 0), SPAHandler) as httpd:
                    self.httpd = httpd
                    self.port = httpd.server_address[1]
                    httpd.serve_forever()
            except Exception as ex:
                logger.exception("Unexpected exception in server: bailing out")
                return

    def stop(self):
        logger.info('Stopping server')
        self.httpd.shutdown()
        self.join()


# server: ServerThread = ServerThread()


class SPAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.root = os.path.join(settings.src_dir, 'dist')
        self.index_file = None
        for index in "index.html", "index.htm":
            index = os.path.join(self.root, index)
            if os.path.exists(index):
                self.index_file = index
                break

        if not self.index_file:
            raise BuildFailedException("No index.html file found in distribution?")
        super().__init__(*args, directory=self.root, **kwargs)

    def send_head(self):
        """Common code for GET and HEAD commands - mostly copied from the base class to implement the try_files
        logic
        We'll either be returning an asses or the index file
        """
        path = self.translate_path(self.path)

        f = None
        if os.path.isdir(path):
            path = self.index_file

        try:
            f = open(path, 'rb')
        except OSError:
            # return index
            path = self.index_file
            f = open(path, 'rb')

        ctype = self.guess_type(path)
        try:
            fs = os.fstat(f.fileno())
            # Use browser cache if possible
            if ("If-Modified-Since" in self.headers
                    and "If-None-Match" not in self.headers):
                # compare If-Modified-Since and time of last file modification
                try:
                    ims = email.utils.parsedate_to_datetime(
                        self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    # ignore ill-formed values
                    pass
                else:
                    if ims.tzinfo is None:
                        # obsolete format with no timezone, cf.
                        # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        # compare to UTC datetime of last modification
                        last_modif = datetime.datetime.fromtimestamp(
                            fs.st_mtime, datetime.timezone.utc)
                        # remove microseconds, like in If-Modified-Since
                        last_modif = last_modif.replace(microsecond=0)

                        if last_modif <= ims:
                            self.send_response(HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            f.close()
                            return None

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except:
            f.close()
            raise


def wait_for_server(port: int):
    endtime = time() + settings.SERVER_START_TIMEOUT
    sleep(1)
    logger.debug(f"Waiting for server to be ready on port {port}...")
    while True:
        ready = False
        try:
            r = httpx.get(f'http://localhost:{port}')
            if r.status_code == 200:
                ready = True
        except RemoteProtocolError as ex:
            logger.warning(f"...{ex}: keep waiting")
        except ConnectionRefusedError:
            logger.info("...connection refused to server")

        if ready:
            logger.debug('Server is ready')
            return

        if time() > endtime:
            raise BuildFailedException('Failed to start server')
        sleep(5)


def start_server(project: Project) -> ServerThread:
    """
    Start the server
    """
    server = ServerThread(project)
    server.start()
    sleep(1)

    # wait until it's ready
    while server.port == 0:
        logger.debug('Wait for server port to be allocated')
        sleep(2)

    wait_for_server(server.port)
