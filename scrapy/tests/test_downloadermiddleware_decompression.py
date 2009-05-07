import os
from unittest import TestCase, main
from scrapy.http import Response, XmlResponse
from scrapy.contrib_exp.downloadermiddleware.decompression import DecompressionMiddleware

def setUp():
    datadir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'sample_data', 'compressed')
    formats = ['tar', 'xml.bz2', 'xml.gz', 'zip']

    uncompressed_fd = open(os.path.join(datadir, 'feed-sample1.xml'), 'r')
    uncompressed_body = uncompressed_fd.read()
    uncompressed_fd.close()

    test_responses = {}
    for format in formats:
        fd = open(os.path.join(datadir, 'feed-sample1.' + format), 'r')
        body = fd.read()
        fd.close()
        test_responses[format] = Response('http://foo.com/bar', body=body)
    return uncompressed_body, test_responses

class ScrapyDecompressionTest(TestCase):
    uncompressed_body, test_responses = setUp()
    middleware = DecompressionMiddleware()

    def test_tar(self):
        response, format = self.middleware.extract(self.test_responses['tar'])
        assert isinstance(response, XmlResponse)
        self.assertEqual(response.body, self.uncompressed_body)

    def test_zip(self):
        response, format = self.middleware.extract(self.test_responses['zip'])
        assert isinstance(response, XmlResponse)
        self.assertEqual(response.body, self.uncompressed_body)

    def test_gz(self):
        response, format = self.middleware.extract(self.test_responses['xml.gz'])
        assert isinstance(response, XmlResponse)
        self.assertEqual(response.body, self.uncompressed_body)

    def test_bz2(self):
        response, format = self.middleware.extract(self.test_responses['xml.bz2'])
        assert isinstance(response, XmlResponse)
        self.assertEqual(response.body, self.uncompressed_body)

if __name__ == '__main__':
    main()