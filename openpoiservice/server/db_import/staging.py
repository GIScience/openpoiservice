# openpoiservice/server/db_import/staging.py
"""
Imports an osm file through staging tables. The parser copies the file's POIs into unlogged tables without indexes,
then merge() applies only the differences to the live tables in one transaction. Rows that didn't change aren't
written, and a failed import leaves the live tables as they were.

The staging tables have fixed names, so only one import may run at a time.
"""
import io
import logging
from collections import namedtuple

from sqlalchemy import text

from openpoiservice.server import db
from openpoiservice.server.db_import.models import POIs, Categories, Tags

logger = logging.getLogger(__name__)

POIS = POIs.__tablename__
CATEGORIES = Categories.__tablename__
TAGS = Tags.__tablename__

STAGED_POIS = POIS + "_staging"
STAGED_CATEGORIES = CATEGORIES + "_staging"
STAGED_TAGS = TAGS + "_staging"

# for the hash joins of the merge and the index builds of the vacuum
MERGE_WORK_MEM = "256MB"
VACUUM_MAINTENANCE_WORK_MEM = "1GB"

COPY_ESCAPES = str.maketrans({"\\": "\\\\", "\t": "\\t", "\n": "\\n", "\r": "\\r"})

MergeCounts = namedtuple("MergeCounts", "pois_added pois_changed pois_removed category_rows tag_rows")

# the statements of a merge, in order; each counts the rows it touched
REMOVE_POIS = f"""
    DELETE FROM {POIS} p WHERE p.src_index = :src_index
    AND NOT EXISTS (SELECT FROM {STAGED_POIS} s WHERE s.osm_type = p.osm_type AND s.osm_id = p.osm_id)"""

# a POI also changes when another file imported it before, e.g. where extracts overlap: the last file imported owns it
CHANGE_POIS = f"""
    UPDATE {POIS} p SET geom = s.geom, src_index = :src_index FROM {STAGED_POIS} s
    WHERE p.osm_type = s.osm_type AND p.osm_id = s.osm_id
    AND (p.src_index IS DISTINCT FROM :src_index OR ST_AsBinary(p.geom) <> ST_AsBinary(s.geom))"""

ADD_POIS = f"""
    INSERT INTO {POIS} (osm_type, osm_id, geom, src_index)
    SELECT s.osm_type, s.osm_id, s.geom, :src_index FROM {STAGED_POIS} s
    WHERE NOT EXISTS (SELECT FROM {POIS} p WHERE p.osm_type = s.osm_type AND p.osm_id = s.osm_id)"""

REMOVE_CATEGORIES = f"""
    DELETE FROM {CATEGORIES} c USING {STAGED_POIS} s
    WHERE c.osm_type = s.osm_type AND c.osm_id = s.osm_id
    AND NOT EXISTS (SELECT FROM {STAGED_CATEGORIES} sc
                    WHERE sc.osm_type = c.osm_type AND sc.osm_id = c.osm_id AND sc.category = c.category)"""

ADD_CATEGORIES = f"""
    INSERT INTO {CATEGORIES} (osm_type, osm_id, category)
    SELECT sc.osm_type, sc.osm_id, sc.category FROM {STAGED_CATEGORIES} sc
    WHERE NOT EXISTS (SELECT FROM {CATEGORIES} c
                      WHERE c.osm_type = sc.osm_type AND c.osm_id = sc.osm_id AND c.category = sc.category)"""

REMOVE_TAGS = f"""
    DELETE FROM {TAGS} t USING {STAGED_POIS} s
    WHERE t.osm_type = s.osm_type AND t.osm_id = s.osm_id
    AND NOT EXISTS (SELECT FROM {STAGED_TAGS} st
                    WHERE st.osm_type = t.osm_type AND st.osm_id = t.osm_id AND st.key = t.key)"""

CHANGE_TAGS = f"""
    UPDATE {TAGS} t SET value = st.value FROM {STAGED_TAGS} st
    WHERE t.osm_type = st.osm_type AND t.osm_id = st.osm_id AND t.key = st.key
    AND t.value IS DISTINCT FROM st.value"""

ADD_TAGS = f"""
    INSERT INTO {TAGS} (osm_type, osm_id, key, value)
    SELECT st.osm_type, st.osm_id, st.key, st.value FROM {STAGED_TAGS} st
    WHERE NOT EXISTS (SELECT FROM {TAGS} t WHERE t.osm_type = st.osm_type AND t.osm_id = st.osm_id AND t.key = st.key)"""


def create():
    """
    Creates empty staging tables, replacing those a crashed import may have left behind.
    """
    drop()
    db.session.execute(text(f"""
        CREATE UNLOGGED TABLE {STAGED_POIS} (
            osm_type integer NOT NULL, osm_id bigint NOT NULL, geom geography(Point, 4326) NOT NULL)"""))
    db.session.execute(text(f"""
        CREATE UNLOGGED TABLE {STAGED_CATEGORIES} (
            osm_type integer NOT NULL, osm_id bigint NOT NULL, category integer NOT NULL)"""))
    db.session.execute(text(f"""
        CREATE UNLOGGED TABLE {STAGED_TAGS} (
            osm_type integer NOT NULL, osm_id bigint NOT NULL, key text NOT NULL, value text)"""))
    db.session.commit()


def drop():
    db.session.execute(text(f"DROP TABLE IF EXISTS {STAGED_POIS}, {STAGED_CATEGORIES}, {STAGED_TAGS}"))
    db.session.commit()


def copy(pois, categories, tags):
    """
    Appends rows to the staging tables with COPY.

    :param pois: (osm_type, osm_id, geometry as EWKT) tuples
    :param categories: (osm_type, osm_id, category) tuples
    :param tags: (osm_type, osm_id, key, value) tuples
    """
    cursor = db.session.connection().connection.cursor()
    for table, rows in ((STAGED_POIS, pois), (STAGED_CATEGORIES, categories), (STAGED_TAGS, tags)):
        if rows:
            cursor.copy_expert(f"COPY {table} FROM STDIN", io.StringIO(copy_text(rows)))
    db.session.commit()


def copy_text(rows):
    """
    Formats rows in COPY's text format: tab-separated, one row per line, None as NULL.
    """
    return "".join("\t".join(copy_field(value) for value in row) + "\n" for row in rows)


def copy_field(value):
    return "\\N" if value is None else str(value).translate(COPY_ESCAPES)


def merge(src_index):
    """
    Makes the live tables match the staged POIs of the file with this index: removes the file's POIs that are no
    longer staged, then updates and adds, in one transaction.

    :return: MergeCounts, the category and tag rows counted together over removals, changes and additions
    """
    db.session.execute(text(f"SET LOCAL work_mem = '{MERGE_WORK_MEM}'"))
    # the staging tables are new, so without statistics the planner would guess their sizes
    for table in (STAGED_POIS, STAGED_CATEGORIES, STAGED_TAGS):
        db.session.execute(text(f"ANALYZE {table}"))

    def run(statement):
        return db.session.execute(text(statement), {"src_index": src_index}).rowcount

    # the statements run in the order of these arguments: removals first, so updates and additions scan fewer rows
    counts = MergeCounts(
        pois_removed=run(REMOVE_POIS),
        pois_changed=run(CHANGE_POIS),
        pois_added=run(ADD_POIS),
        category_rows=run(REMOVE_CATEGORIES) + run(ADD_CATEGORIES),
        tag_rows=run(REMOVE_TAGS) + run(CHANGE_TAGS) + run(ADD_TAGS),
    )
    db.session.commit()
    return counts


def vacuum():
    """
    Vacuums and analyses the live tables. A merge leaves dead rows behind and changes the statistics.
    """
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text(f"SET maintenance_work_mem = '{VACUUM_MAINTENANCE_WORK_MEM}'"))
        for table in (POIS, CATEGORIES, TAGS):
            connection.execute(text(f"VACUUM (ANALYZE) {table}"))
        connection.execute(text("RESET maintenance_work_mem"))
