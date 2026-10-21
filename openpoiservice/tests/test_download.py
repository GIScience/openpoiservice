# openpoiservice/server/tests/test_download.py
import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from unittest import mock

from osmium.replication.utils import ReplicationHeader

spec = importlib.util.spec_from_file_location('download', os.path.join(os.getcwd(), 'osm', 'download.py'))
download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download)

url = 'https://download.geofabrik.de/europe/bremen-latest.osm.pbf'


class FakeResponse:

    def __init__(self, chunks, content_length=None, status_error=None):
        self.chunks = chunks
        self.status_error = status_error
        self.headers = {}
        if content_length is not None:
            self.headers['Content-Length'] = str(content_length)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def iter_content(self, chunk_size):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


class TestDownloadFile(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.directory.name, 'bremen-latest.osm.pbf')
        with open(self.file, 'wb') as f:
            f.write(b'old data')

    def tearDown(self):
        self.directory.cleanup()

    def download(self, response):
        with mock.patch.object(download.requests, 'get', return_value=response):
            return download.download_file(url, self.file)

    def assert_file_contains(self, content):
        with open(self.file, 'rb') as f:
            self.assertEqual(f.read(), content)
        self.assertFalse(os.path.exists(self.file + '.part'))

    def test_complete_download_replaces_file(self):
        self.assertTrue(self.download(FakeResponse([b'new ', b'', b'data'], content_length=8)))
        self.assert_file_contains(b'new data')

    def test_download_without_content_length_replaces_file(self):
        self.assertTrue(self.download(FakeResponse([b'new data'])))
        self.assert_file_contains(b'new data')

    def test_interrupted_download_keeps_old_file(self):
        self.assertFalse(self.download(FakeResponse([b'new ', ConnectionError('connection reset')])))
        self.assert_file_contains(b'old data')

    def test_short_download_keeps_old_file(self):
        self.assertFalse(self.download(FakeResponse([b'new '], content_length=8)))
        self.assert_file_contains(b'old data')

    def test_http_error_keeps_old_file(self):
        self.assertFalse(self.download(FakeResponse([], status_error=download.requests.HTTPError('404'))))
        self.assert_file_contains(b'old data')


class TestDownloadMain(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.previous_cwd = os.getcwd()
        os.chdir(self.directory.name)
        with open('pbf_list.txt', 'w') as f:
            f.write('asia/new-latest.osm.pbf\n\neurope/current-latest.osm.pbf\n')
        os.makedirs('europe')
        with open('europe/current-latest.osm.pbf', 'wb') as f:
            f.write(b'current data')

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.directory.cleanup()

    def run_main(self, updatable):
        with mock.patch.object(download, 'is_updatable', return_value=updatable), \
                mock.patch.object(download, 'update_file', return_value=True) as update_file, \
                mock.patch.object(download.requests, 'get', return_value=FakeResponse([b'new data'])) as get:
            download.main()
        return update_file, get

    def test_downloads_missing_and_updates_existing_files(self):
        update_file, get = self.run_main(updatable=True)

        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], 'https://download.geofabrik.de/asia/new-latest.osm.pbf')
        with open('asia/new-latest.osm.pbf', 'rb') as f:
            self.assertEqual(f.read(), b'new data')
        update_file.assert_called_once_with('europe/current-latest.osm.pbf')

    def test_downloads_existing_files_that_cannot_be_updated(self):
        update_file, get = self.run_main(updatable=False)

        self.assertEqual(get.call_count, 2)
        update_file.assert_not_called()
        with open('europe/current-latest.osm.pbf', 'rb') as f:
            self.assertEqual(f.read(), b'new data')


class TestIsUpdatable(unittest.TestCase):

    @staticmethod
    def header(url='https://download.geofabrik.de/europe/bremen-updates', sequence=4943, age_days=1):
        timestamp = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=age_days)
        return ReplicationHeader(url=url, sequence=sequence, timestamp=timestamp)

    def is_updatable(self, header):
        with mock.patch.object(download, 'get_replication_header', return_value=header):
            return download.is_updatable('bremen-latest.osm.pbf')

    def test_recent_file_with_replication_header(self):
        self.assertTrue(self.is_updatable(self.header()))

    def test_file_too_old_for_updates(self):
        self.assertFalse(self.is_updatable(self.header(age_days=86)))

    def test_file_without_replication_server(self):
        self.assertFalse(self.is_updatable(self.header(url=None)))
        self.assertFalse(self.is_updatable(self.header(sequence=None)))

    def test_pbf_without_replication_header(self):
        test_file = os.path.join(os.getcwd(), 'osm', 'bremen-tests.osm.pbf')
        self.assertFalse(download.is_updatable(test_file))

    def test_unreadable_file(self):
        with tempfile.NamedTemporaryFile(suffix='.osm.pbf') as f:
            f.write(b'not osm data')
            f.flush()
            self.assertFalse(download.is_updatable(f.name))


class TestUpdateFile(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.directory.name, 'bremen-latest.osm.pbf')
        with open(self.file, 'wb') as f:
            f.write(b'old data')

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def up_to_date_run(exit_code, content=None):
        """ Fakes one run of pyosmium-up-to-date: writes content to the -o file, if given, and returns exit_code. """
        def run(args):
            if content is not None:
                with open(args[args.index('-o') + 1], 'wb') as f:
                    f.write(content)
            return exit_code
        return run

    def update(self, *runs):
        runs = iter(runs)
        with mock.patch.object(download, 'pyosmium_up_to_date', side_effect=lambda args: next(runs)(args)) as tool:
            return download.update_file(self.file), tool

    def assert_file_contains(self, content):
        with open(self.file, 'rb') as f:
            self.assertEqual(f.read(), content)
        self.assertFalse(os.path.exists(self.file + '.part'))

    def test_applied_diffs_replace_file(self):
        updated, tool = self.update(self.up_to_date_run(0, b'new data'))

        self.assertTrue(updated)
        self.assert_file_contains(b'new data')
        self.assertEqual(tool.call_args.args[0],
                         ['--format', 'pbf', '--size', '8192', '-o', self.file + '.part', self.file])

    def test_file_already_up_to_date(self):
        updated, _ = self.update(self.up_to_date_run(0))

        self.assertTrue(updated)
        self.assert_file_contains(b'old data')

    def test_repeats_while_more_diffs_are_available(self):
        updated, tool = self.update(self.up_to_date_run(1, b'newer data'), self.up_to_date_run(0, b'newest data'))

        self.assertTrue(updated)
        self.assertEqual(tool.call_count, 2)
        self.assert_file_contains(b'newest data')

    def test_failed_update_keeps_file(self):
        updated, _ = self.update(self.up_to_date_run(3, b'partial data'))

        self.assertFalse(updated)
        self.assert_file_contains(b'old data')

    def test_stops_after_max_rounds(self):
        rounds = [self.up_to_date_run(1, b'newer data')] * download.max_update_rounds
        updated, tool = self.update(*rounds)

        self.assertFalse(updated)
        self.assertEqual(tool.call_count, download.max_update_rounds)
        self.assert_file_contains(b'newer data')


if __name__ == '__main__':
    unittest.main()
