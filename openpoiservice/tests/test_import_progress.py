# openpoiservice/server/tests/test_import_progress.py
import logging
import os
import re
import tempfile
import unittest
from unittest import mock

from base import BaseTestCase
from openpoiservice.server import db
from openpoiservice.server.db_import import parser, staging
from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.db_import.progress import Progress, format_duration, format_size

test_file = os.path.join(os.getcwd() + '/osm', 'bremen-tests.osm.pbf')


class TestImportProgress(BaseTestCase):

    def setUp(self):
        super().setUp()
        handle, self.logfile = tempfile.mkstemp(suffix='.json')
        os.close(handle)

    def tearDown(self):
        os.remove(self.logfile)
        super().tearDown()

    def run_update(self, import_log=None):
        with self.assertLogs(parser.logger, 'INFO') as logs:
            parser.run_import_new([test_file], import_log or {}, self.logfile, db)
        return [record.getMessage() for record in logs.records], logs.records

    def test_logs_position_size_and_outcome_of_every_file(self):
        messages, _ = self.run_update()

        self.assertEqual(messages[0], 'Importing 1 of 1 files (0 unchanged since the last import), in update mode')
        self.assertEqual(messages[1], '[1/1] osm/bremen-tests.osm.pbf (75.2 kB)')
        # setUp imports with the deprecated parser, which drops some ways; the current parser finds them
        self.assertIn('[1/1] 6 POIs added, 0 changed and 0 removed; 9 category and 10 tag rows changed', messages)
        self.assertTrue(any(message.startswith('Tables vacuumed and analysed after ') for message in messages))
        # the merge and the vacuum may take a second
        self.assertTrue(any(re.fullmatch(r'\[1/1\] succeeded after 0:00:0\d \(0:00:0\d since start\)', message)
                            for message in messages))
        self.assertRegex(messages[-1], r'^Import finished after 0:00:0\d: 1 succeeded, 0 failed, 0 unchanged$')

    def test_counts_unchanged_files_without_a_line_for_each(self):
        messages, _ = self.run_update({test_file: os.path.getmtime(test_file)})

        self.assertEqual(messages, ['Importing 0 of 1 files (1 unchanged since the last import), in update mode',
                                    'Import finished after 0:00:00: 0 succeeded, 0 failed, 1 unchanged'])

    def test_logs_failed_files_as_warnings(self):
        with mock.patch.object(parser, 'parse_file_new', return_value=1):
            messages, records = self.run_update()

        failed = [record for record in records if record.getMessage().startswith('[1/1] failed after')]
        self.assertEqual(failed[0].levelname, 'WARNING')
        self.assertIn('[1/1] import failed, keeping the POIs from the previous import of this file', messages)
        self.assertEqual(messages[-1], 'Import finished after 0:00:00: 0 succeeded, 1 failed, 0 unchanged')

    def test_logs_numbered_passes_of_a_file(self):
        # parse_file_new normally runs in a forked process, whose log records assertLogs doesn't see
        staging.create()
        with self.assertLogs(parser.logger, 'INFO') as logs:
            parser.parse_file_new.__wrapped__(test_file, label='[2/5]')
        staging.drop()
        messages = [record.getMessage() for record in logs.records]

        for number in range(1, 6):
            self.assertTrue(any(message.startswith(f'[2/5] pass {number}/5: ') for message in messages))
            self.assertTrue(any(message.startswith(f'[2/5] pass {number}/5 done after 0:00:00: ')
                                for message in messages))
        self.assertIn('[2/5] pass 1/5 done after 0:00:00: 38 POIs from nodes', messages)
        self.assertEqual(messages[-1], '[2/5] 44 POIs stored in total')


class TestImporterProgress(unittest.TestCase):

    def test_reports_scanned_nodes(self):
        importer = OsmImporter(label='[1/2]')
        importer.coords_progress.step = 2

        with self.assertLogs('openpoiservice.server.db_import.parse_osm', 'INFO') as logs:
            importer.parse_coords_and_store([(1, 8.0, 53.0), (2, 8.1, 53.1), (3, 8.2, 53.2)])

        self.assertEqual([record.getMessage() for record in logs.records], ['[1/2]   3 nodes scanned'])

    def test_reports_scanned_ways(self):
        importer = OsmImporter(label='[1/2]')
        importer.ways_progress.step = 1

        with self.assertLogs('openpoiservice.server.db_import.parse_osm', 'INFO') as logs:
            importer.parse_ways_first([(10, {}, [1, 2])])

        self.assertEqual([record.getMessage() for record in logs.records], ['[1/2]   1 ways scanned'])


class TestProgress(unittest.TestCase):

    def setUp(self):
        self.logger = logging.getLogger('test_progress')

    def test_logs_each_time_the_count_passes_a_step(self):
        progress = Progress(self.logger, '[3/12]', 'POIs stored', 100)

        with self.assertLogs(self.logger, 'INFO') as logs:
            for _ in range(250):
                progress.add()

        self.assertEqual([record.getMessage() for record in logs.records],
                         ['[3/12]   100 POIs stored', '[3/12]   200 POIs stored'])

    def test_logs_once_for_a_batch_passing_several_steps(self):
        progress = Progress(self.logger, '[3/12]', 'nodes scanned', 1_000_000)
        progress.add(999_999)

        with self.assertLogs(self.logger, 'INFO') as logs:
            progress.add(2_500_000)

        self.assertEqual([record.getMessage() for record in logs.records], ['[3/12]   3,499,999 nodes scanned'])


class TestFormatting(unittest.TestCase):

    def test_format_duration(self):
        self.assertEqual(format_duration(0.4), '0:00:00')
        self.assertEqual(format_duration(3725.6), '1:02:06')

    def test_format_size(self):
        self.assertEqual(format_size(512), '512 B')
        self.assertEqual(format_size(75_212), '75.2 kB')
        self.assertEqual(format_size(4_321_000_000), '4.3 GB')
        self.assertEqual(format_size(7_940_736_249), '7.9 GB')
        self.assertEqual(format_size(12_500_000), '12.5 MB')


if __name__ == '__main__':
    unittest.main()
