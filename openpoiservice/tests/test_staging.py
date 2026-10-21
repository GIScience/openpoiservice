# openpoiservice/server/tests/test_staging.py
import os
import unittest
from unittest import mock

from sqlalchemy import inspect, text

from base import BaseTestCase
from openpoiservice.server import db
from openpoiservice.server.db_import import parser, staging
from openpoiservice.server.db_import.models import POIs, Categories, Tags
from openpoiservice.server.db_import.staging import MergeCounts

test_file = os.path.join(os.getcwd() + '/osm', 'bremen-tests.osm.pbf')


def execute(statement, **params):
    result = db.session.execute(text(statement), params)
    db.session.commit()
    return result


def stage_live_pois(exclude=()):
    """
    Stages the live POIs, as if their file was imported again unchanged.
    """
    for staged, live, columns in ((staging.STAGED_POIS, staging.POIS, "geom"),
                                  (staging.STAGED_CATEGORIES, staging.CATEGORIES, "category"),
                                  (staging.STAGED_TAGS, staging.TAGS, "key, value")):
        execute(f"INSERT INTO {staged} SELECT osm_type, osm_id, {columns} FROM {live} WHERE osm_id <> ALL(:exclude)",
                exclude=list(exclude))


def unstage_children(osm_id):
    execute(f"DELETE FROM {staging.STAGED_CATEGORIES} WHERE osm_id = :osm_id", osm_id=osm_id)
    execute(f"DELETE FROM {staging.STAGED_TAGS} WHERE osm_id = :osm_id", osm_id=osm_id)


def live_poi_ids(**filters):
    """
    :return: the sorted osm ids of the live POIs, nodes only unless filtered otherwise
    """
    filters.setdefault("osm_type", 1)
    return [osm_id for (osm_id,) in db.session.query(POIs.osm_id).filter_by(**filters).order_by(POIs.osm_id)]


class TestMerge(BaseTestCase):

    def setUp(self):
        super().setUp()
        staging.create()

    def tearDown(self):
        db.session.rollback()
        staging.drop()
        super().tearDown()

    def test_merging_unchanged_pois_writes_nothing(self):
        stage_live_pois()

        self.assertEqual(staging.merge(0), MergeCounts(0, 0, 0, 0, 0))

    def test_merge_applies_added_changed_and_removed_pois(self):
        changed, removed = live_poi_ids()[:2]
        stage_live_pois(exclude=[removed])
        execute(f"UPDATE {staging.STAGED_POIS} SET geom = 'SRID=4326;POINT(8 53)' WHERE osm_id = :osm_id",
                osm_id=changed)
        unstage_children(changed)
        staging.copy(pois=[(1, 1, 'SRID=4326;POINT(9 54)')],
                     categories=[(1, changed, 999), (1, 1, 999)],
                     tags=[(1, changed, 'name', 'Neu')])

        counts = staging.merge(0)

        self.assertEqual((counts.pois_added, counts.pois_changed, counts.pois_removed), (1, 1, 1))
        self.assertEqual(db.session.scalar(text(f"SELECT ST_AsText(geom) FROM {staging.POIS} WHERE osm_id = :id"),
                                           {"id": changed}), 'POINT(8 53)')
        self.assertEqual([c.category for c in db.session.query(Categories).filter_by(osm_id=changed)], [999])
        self.assertEqual([(t.key, t.value) for t in db.session.query(Tags).filter_by(osm_id=changed)],
                         [('name', 'Neu')])
        self.assertEqual(db.session.query(Categories).filter_by(osm_id=removed).count(), 0)
        self.assertEqual(db.session.query(Tags).filter_by(osm_id=removed).count(), 0)
        self.assertEqual(live_poi_ids(osm_id=1), [1])

    def test_merge_changes_tag_values(self):
        tag = db.session.query(Tags).first()
        stage_live_pois()
        execute(f"UPDATE {staging.STAGED_TAGS} SET value = 'umbenannt' WHERE osm_id = :osm_id AND key = :key",
                osm_id=tag.osm_id, key=tag.key)

        self.assertEqual(staging.merge(0), MergeCounts(0, 0, 0, 0, 1))
        self.assertEqual(db.session.query(Tags.value).filter_by(osm_id=tag.osm_id, key=tag.key).scalar(),
                         'umbenannt')

    def test_merge_claims_pois_of_another_file_and_keeps_its_others(self):
        claimed_1, claimed_2, kept = live_poi_ids()[:3]
        execute(f"UPDATE {staging.POIS} SET src_index = 1 WHERE osm_id = ANY(:ids)", ids=[claimed_1, claimed_2, kept])
        stage_live_pois(exclude=[kept])

        self.assertEqual(staging.merge(0), MergeCounts(0, 2, 0, 0, 0))
        self.assertEqual(live_poi_ids(src_index=1), [kept])

    def test_copy_keeps_special_characters(self):
        value = 'tab\tbackslash\\newline\nreturn\r'
        staging.copy(pois=[], categories=[], tags=[(1, 1, 'name', value), (1, 1, 'note', None)])

        rows = execute(f"SELECT key, value FROM {staging.STAGED_TAGS} ORDER BY key").all()
        self.assertEqual([tuple(row) for row in rows], [('name', value), ('note', None)])

    def test_failed_merge_keeps_pois_and_drops_staging(self):
        pois_before = live_poi_ids()

        def stage_duplicate_poi(*args, **kwargs):
            staging.copy(pois=[(1, 1, 'SRID=4326;POINT(9 54)')] * 2, categories=[], tags=[])
            return 0

        with mock.patch.object(parser, 'parse_file_new', side_effect=stage_duplicate_poi):
            self.assertFalse(parser.import_file(test_file, 0, db))

        self.assertEqual(live_poi_ids(), pois_before)
        self.assertFalse(inspect(db.engine).has_table(staging.STAGED_POIS))


class TestCopyText(unittest.TestCase):

    def test_escapes_separators_and_writes_none_as_null(self):
        self.assertEqual(staging.copy_text([(1, 'a\tb\\c\nd\re', None), (2, 'x', 'y')]),
                         '1\ta\\tb\\\\c\\nd\\re\t\\N\n2\tx\ty\n')


if __name__ == '__main__':
    unittest.main()
