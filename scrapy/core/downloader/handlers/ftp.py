"""
An asynchronous FTP file download handler for scrapy which somehow emulates an http response.

FTP connection parameters are passed using the request meta field:
- ftp_user (required)
- ftp_password (required)
- ftp_passive (by default, enabled) sets FTP connection passive mode
- ftp_local_filename
        - If not given, file data will come in the response.body, as a normal scrapy Response,
        which will imply that the entire file will be on memory.
        - if given, file data will be saved in a local file with the given name
        This helps when downloading very big files to avoid memory issues. In addition, for
        convenience the local file name will also be given in the response body.

The status of the built html response will be, by default
- 200 in case of success
- 404 in case specified file was not found in the server (ftp code 550)

or raise corresponding ftp exception otherwise

The matching from server ftp command return codes to html response codes is defined in the
CODE_MAPPING attribute of the handler class. The key 'default' is used for any code
that is not explicitly present among the map keys. You may need to overwrite this
mapping if want a different behaviour than default.

In case of status 200 request, response.headers will come with two keys:
    'Local Filename' - with the value of the local filename if given
    'Size' - with size of the downloaded data
"""

import re
from io import BytesIO
from six.moves.urllib.parse import urlparse, unquote

from twisted.internet import reactor
from twisted.protocols.ftp import FTPClient, FTPFileListProtocol, CommandFailed
from twisted.internet.protocol import Protocol, ClientCreator

from scrapy.http import Response
from scrapy.http.response.ftplist import FTPListResponse
from scrapy.responsetypes import responsetypes

class ListDataProtocol(FTPFileListProtocol):
    pass

class ReceivedDataProtocol(Protocol):
    def __init__(self, filename=None):
        self.__filename = filename
        self.body = open(filename, "w") if filename else BytesIO()
        self.size = 0

    def dataReceived(self, data):
        self.body.write(data)
        self.size += len(data)

    @property
    def filename(self):
        return self.__filename

    def close(self):
        self.body.close() if self.filename else self.body.seek(0)

_CODE_RE = re.compile("\d+")
class FTPDownloadHandler(object):

    CODE_MAPPING = {
        "550": 404,
        "default": 503,
    }

    def __init__(self, setting):
        pass

    def download_request(self, request, spider):
        parsed_url = urlparse(request.url)
        creator = ClientCreator(reactor, FTPClient, request.meta["ftp_user"],
                                    request.meta["ftp_password"],
                                    passive=request.meta.get("ftp_passive", 1))
        return creator.connectTCP(parsed_url.hostname, parsed_url.port or 21).addCallback(self.gotClient,
                                request, unquote(parsed_url.path))

    def gotClient(self, client, request, filepath):
        self.client = client
        if filepath.endswith('/'):
            protocol = ListDataProtocol()
            return client.list(filepath, protocol)\
                .addCallbacks(callback=self._build_list_response,
                        callbackArgs=(request, protocol),
                        errback=self._failed,
                        errbackArgs=(request,))
        else:
            protocol = ReceivedDataProtocol(request.meta.get("ftp_local_filename"))
            return client.retrieveFile(filepath, protocol)\
                .addCallbacks(callback=self._build_file_response,
                        callbackArgs=(request, protocol),
                        errback=self._failed,
                        errbackArgs=(request,))

    def _build_list_response(self, result, request, protocol):
        self.result = result
        body = ""
        headers = {"size": "%d" % len(protocol.files)}
        return FTPListResponse(url=request.url, status=200, body=body,
                               headers=headers, files=protocol.files)

    def _build_file_response(self, result, request, protocol):
        self.result = result
        respcls = responsetypes.from_args(url=request.url)
        protocol.close()
        body = protocol.filename or protocol.body.read()
        headers = {"local filename": protocol.filename or '', "size": protocol.size}
        return respcls(url=request.url, status=200, body=body, headers=headers)

    def _failed(self, result, request):
        message = result.getErrorMessage()
        if result.type == CommandFailed:
            m = _CODE_RE.search(message)
            if m:
                ftpcode = m.group()
                httpcode = self.CODE_MAPPING.get(ftpcode, self.CODE_MAPPING["default"])
                return Response(url=request.url, status=httpcode, body=message)
        raise result.type(result.value)

