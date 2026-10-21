# openpoiservice/server/tests/test_import_failure.py
import json
import os
import tempfile
import time
import unittest
from multiprocessing import Process, Queue
from unittest import mock

from base import BaseTestCase
from openpoiservice.server import db
from openpoiservice.server.db_import import parser
from openpoiservice.server.db_import.models import POIs
from openpoiservice.server.db_import.parse_osm import OsmImporter
from openpoiservice.server.utils.decorators import processify, wait_for_result

test_file = os.path.join(os.getcwd() + '/osm', 'bremen-tests.osm.pbf')


@processify
def exit_without_result():
    os._exit(3)


def put_after_delay(q):
    time.sleep(0.3)
    q.put((0, None))


class TestImportFailure(BaseTestCase):

    def setUp(self):
        super().setUp()
        handle, self.logfile = tempfile.mkstemp(suffix='.json')
        os.close(handle)

    def tearDown(self):
        os.remove(self.logfile)
        super().tearDown()

    def run_update(self):
        import_log = {}
        parser.run_import_new([test_file], import_log, self.logfile, db)
        return import_log

    @staticmethod
    def count_pois(**filters):
        return db.session.query(POIs).filter_by(**filters).count()

    def test_failed_update_keeps_pois(self):
        pois_before = self.count_pois()
        self.assertGreater(pois_before, 0)

        with mock.patch.object(parser, 'parse_file_new', return_value=1):
            import_log = self.run_update()

        self.assertEqual(self.count_pois(), pois_before)
        self.assertEqual(self.count_pois(delflag=True), 0)
        self.assertEqual(import_log[test_file], 0)

    def test_crashed_update_keeps_pois(self):
        pois_before = self.count_pois()

        with mock.patch.object(parser, 'parse_file_new', side_effect=RuntimeError('process died')):
            import_log = self.run_update()

        self.assertEqual(self.count_pois(), pois_before)
        self.assertEqual(self.count_pois(delflag=True), 0)
        self.assertEqual(import_log[test_file], 0)

    def test_successful_update_deletes_only_pois_of_its_file(self):
        # pretend some POIs come from another file and were left flagged by an earlier, crashed run
        other_file_ids = [osm_id for (osm_id,) in db.session.query(POIs.osm_id).limit(5)]
        db.session.query(POIs).filter(POIs.osm_id.in_(other_file_ids)) \
            .update({POIs.src_index: 1, POIs.delflag: True})
        db.session.commit()

        # a parse that re-imports nothing: every POI of the file is gone from the OSM data
        with mock.patch.object(parser, 'parse_file_new', return_value=0):
            import_log = self.run_update()

        self.assertEqual(self.count_pois(src_index=0), 0)
        self.assertEqual(self.count_pois(src_index=1), len(other_file_ids))
        self.assertEqual(import_log[test_file], os.path.getmtime(test_file))

    def test_update_with_unchanged_data_keeps_pois(self):
        # setUp imports with the deprecated parser, which drops some ways; the current parser finds them
        pois_before = set(db.session.query(POIs.osm_type, POIs.osm_id))

        import_log = self.run_update()

        pois_after = set(db.session.query(POIs.osm_type, POIs.osm_id))
        self.assertTrue(pois_before.issubset(pois_after))
        self.assertEqual(self.count_pois(delflag=True), 0)
        self.assertEqual(import_log[test_file], os.path.getmtime(test_file))
        with open(self.logfile) as f:
            self.assertEqual(json.load(f), import_log)


    def test_initial_import_into_empty_table(self):
        db.session.query(POIs).delete()
        db.session.commit()

        import_log = self.run_update()

        self.assertGreater(self.count_pois(src_index=0), 0)
        self.assertEqual(self.count_pois(delflag=True), 0)
        self.assertEqual(import_log[test_file], os.path.getmtime(test_file))

    def test_parse_reports_failure_when_nodes_fail(self):
        with mock.patch.object(OsmImporter, 'create_poi', side_effect=Exception('database error')):
            self.assertEqual(parser.parse_file_new(test_file, 0, update_mode=True), 1)

    def test_parse_reports_failure_when_ways_fail(self):
        create_poi = OsmImporter.create_poi

        def fail_on_ways(importer, osm_type, *args, **kwargs):
            if osm_type != 1:
                raise Exception('database error')
            return create_poi(importer, osm_type, *args, **kwargs)

        with mock.patch.object(OsmImporter, 'create_poi', fail_on_ways):
            self.assertEqual(parser.parse_file_new(test_file, 0, update_mode=True), 1)


class TestImporterCallbacks(unittest.TestCase):

    def test_node_import_stops_after_first_failure(self):
        importer = OsmImporter(0)
        node = (1, {'amenity': 'cafe'}, (8.8, 53.07))

        with mock.patch.object(importer, 'create_poi', side_effect=Exception('database error')) as create_poi:
            importer.parse_nodes([node])
            importer.parse_nodes([node])

        self.assertTrue(importer.failed)
        self.assertEqual(create_poi.call_count, 1)

    def test_way_import_stops_after_first_failure(self):
        importer = OsmImporter(0)
        importer.nodes_store.append(1, (8.0, 53.0))
        importer.nodes_store.append(2, (9.0, 54.0))
        importer.process_ways_set.add(10)
        importer.process_ways_set.add(11)
        way_10 = (10, {'amenity': 'cafe'}, [1, 2])
        way_11 = (11, {'amenity': 'cafe'}, [1, 2])

        with mock.patch.object(importer, 'create_poi', side_effect=Exception('database error')) as create_poi:
            importer.parse_ways_second([way_10])
            importer.parse_ways_second([way_11])

        self.assertTrue(importer.failed)
        self.assertEqual(create_poi.call_count, 1)

    def test_way_centroid_averages_unique_nodes(self):
        importer = OsmImporter(0)
        importer.nodes_store.append(1, (8.0, 53.0))
        importer.nodes_store.append(2, (9.0, 54.0))

        self.assertEqual(importer.way_centroid([1, 2, 1]), [8.5, 53.5])

    def test_way_centroid_is_none_without_coordinates(self):
        importer = OsmImporter(0)
        importer.nodes_store.append(1, (8.0, 53.0))
        importer.nodes_store.append(2, (None, None))

        self.assertIsNone(importer.way_centroid([1, 2]))
        self.assertIsNone(importer.way_centroid([1, 3]))


class TestProcessify(unittest.TestCase):

    def test_process_dying_without_result_raises(self):
        with self.assertRaisesRegex(RuntimeError, 'exited with code 3'):
            exit_without_result()

    def test_waits_for_a_slow_process(self):
        q = Queue()
        p = Process(target=put_after_delay, args=[q])
        p.start()

        self.assertEqual(wait_for_result(q, p, put_after_delay, poll_seconds=0.05), (0, None))
        p.join()


if __name__ == '__main__':
    unittest.main()
