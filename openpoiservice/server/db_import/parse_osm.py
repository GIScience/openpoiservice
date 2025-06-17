# openpoiservice/server/parse_osm.py

import logging
from bisect import bisect_left
from collections import deque

import numpy as np
from cykhash.khashsets import Int64Set

from openpoiservice.server import categories_tools, ops_settings
from openpoiservice.server import db
from openpoiservice.server.db_import.models import POIs, Tags, Categories
from openpoiservice.server.db_import.node_store import NodeStore
from openpoiservice.server.db_import.objects import PoiObject, TagsObject

logger = logging.getLogger(__name__)


# deprecated, remove later
class WayObject(object):
    """ Class that creates a way object. """

    def __init__(self, osm_id, osm_type, tags, refs, categories, n_refs):
        """
        Initializes way object

        :param osm_id: the osm_id
        :type osm_id: int

        :param osm_type: the osm type (relation or way)
        :type osm_type: int

        :param tags: osm tags
        :type tags: list of objects

        :param refs: references to nodes in this way
        :type refs: list of strings

        :param categories: category derived
        :type categories: list of int
        """
        self.osm_id = osm_id
        self.osm_type = osm_type
        self.tags = tags
        self.refs = refs
        self.categories = categories
        self.sum_lat = 0.0
        self.sum_lng = 0.0
        self.n_refs = n_refs

    def __lt__(self, other):
        return self.refs[0] < other.refs[0]

    def __repr__(self):
        return 'WayObject_osmid({})'.format(self.osm_id)


class OsmImporter(object):
    """ Class that handles the parsed OSM data. """

    def __init__(self, osm_file_index, update_mode=False):
        """ Initializes pbf importer class with necessary counters."""
        self.relations_cnt = 0
        self.ways_cnt = 0
        self.nodes_cnt = 0
        self.pois_count = 0
        self.tags_cnt = 0
        self.categories_cnt = 0
        self.relation_ways = {}
        self.nodes_store = NodeStore()
        self.process_ways_set = Int64Set()
        self.poi_objects = []
        self.tags_objects = []
        self.categories_objects = []
        self.update_mode = update_mode
        self.osm_file_index = osm_file_index
        self.failed = False

        # deprecated, remove later
        self.nodes = {}
        self.process_ways = []
        self.ways_obj = None
        self.ways_temp = []


    def parse_nodes(self, osm_nodes):
        """
        Callback function called by imposm while nodes are parsed.
        :param osm_nodes: list of osm node objects
        """
        # from node
        osm_type = 1
        for osmid, tags, refs in osm_nodes:
            try:
                self.create_poi(osm_type, osmid, [refs[0], refs[1]], tags)
            except Exception as e:
                logger.debug(e)
                self.failed = True
                return


    def parse_relations(self, relations):
        """
        Callback function called by imposm while relations are parsed. The idea is to extract polygons which may
        contain poi tags of interest. For this we are currently using osm_type=multipolygon.
        The osm ids of the found objects are then used in parse_ways.

        :param relations: osm relations objects
        :type relations: list of osm relations
        """
        for osmid, tags, refs in relations:
            is_multipolygon = False
            for tag, value in tags.items():
                if tag == "type" and value == "multipolygon":
                    is_multipolygon = True
                    break

            if is_multipolygon:
                categories = categories_tools.get_category(tags)
                if len(categories) > 0 and len(refs) > 0:
                    rel_member = refs[0]
                    # consider only outer rings
                    if rel_member[2] == "outer":
                        osmid_rel_member = rel_member[0]
                        self.relation_ways[osmid_rel_member] = tags
                        self.relation_ways[osmid_rel_member].update({"relation_id": osmid})
                        self.relations_cnt += 1


    # deprecated, remove later
    def parse_ways(self, ways):
        """
        Callback function called by imposm while ways are parsed. If a category can't be found it may likely
        be that the osmid of this way can be found in self.relation_ways which will contain additional tags
        and therefore eventually a category. A way object is added to a list process_ways which at this point
        is lacking coordinates -> next step.

        :param ways: osm way objects
        :type ways: list of osm ways
        """
        for osmid, tags, refs in ways:
            categories = categories_tools.get_category(tags)
            # from way
            osm_type = 2

            if len(categories) == 0 and osmid in self.relation_ways:
                # current way is the outer ring of a relation which was marked as having a category
                tags = self.relation_ways[osmid]
                if len(refs) < 100:
                    categories = categories_tools.get_category(tags)
                    # from relation
                    osm_type = 3

            if len(categories) > 0 and len(refs) < 1000:
                self.ways_cnt += 1

                # Make unique as duplicates may be inside
                refs = list(set(refs))
                refs.sort(key=int)

                self.ways_obj = WayObject(osmid, osm_type, tags, refs, categories, len(refs))
                self.process_ways.append(self.ways_obj)


    # deprecated, remove later
    def parse_coords_for_ways(self, coords):
        """
        Callback function called by imposm while coordinates are parsed. Due due ordering we can use coords
        on the fly for the ways to be processed. When the coordinates for the ways ref are found, the coordinates
        are summed up and the way ref is then popped out of the way. The popped way is inserted back into process_ways
        to be processed for when th next coordinate hits the way ref id.

        :param coords: osm coordinate objects
        :type coords: list of osm coordinates
        """
        for osmid, lat, lng in coords:

            # nothing to do, all ways processed
            if len(self.process_ways) == 0:
                break

            # current osmid is smaller then ordered ref osmids of way in process_ways
            if osmid < self.process_ways[0].refs[0]:
                continue

            # two ways could have the same ref as current osmid
            while len(self.process_ways) != 0:

                # if the first osm id matches
                if self.process_ways[0].refs[0] == osmid:

                    # pop the way from process_ways
                    way = self.process_ways.popleft()

                    # remove first osm id from way as it is found
                    way.refs.pop(0)

                    # sum up coordinates
                    way.sum_lat += lat
                    way.sum_lng += lng

                    # way has all its coordinates, create centroid and store in db
                    if len(way.refs) == 0:

                        centroid_lat = way.sum_lat / way.n_refs
                        centroid_lng = way.sum_lng / way.n_refs
                        try:
                            self.create_poi(way.osm_type, way.osm_id, [centroid_lat, centroid_lng], way.tags,
                                            way.categories)
                        except Exception as e:
                            logger.debug(e)
                            self.failed = True
                            return

                    # way not completely seen yet, append to ways temp
                    else:
                        self.ways_temp.append(way)

                # break out of while if first ref osmid doesnt match current osmid
                else:
                    break

            # if no process_ways are left, append the ways_temp list to process_ways
            if len(self.process_ways) == 0:
                self.ways_temp.sort(key=lambda x: x.refs[0])
                self.process_ways = deque(self.ways_temp)

            # else sort the ways_temp in reverse order by first way ref id and
            # insert it back to process_ways. The likelihood is high that the way ref id is
            # smaller or equal than the first way ref id of the first way in process_ways
            # which is why this is checked first. If not insert finding the index binary search
            else:
                self.ways_temp.sort(key=lambda x: x.refs[0], reverse=True)
                for t_way in self.ways_temp:
                    if t_way.refs[0] <= self.process_ways[0].refs[0]:
                        self.process_ways.insert(0, t_way)
                    else:
                        self.process_ways.insert(bisect_left(self.process_ways, t_way), t_way)

            self.ways_temp = []


    def parse_ways_first(self, ways):
        """
        Callback function called by imposm while ways are parsed. If a category can't be found it may likely
        be that the osmid of this way can be found in self.relation_ways which will contain additional tags
        and therefore eventually a category. A way object is added to a list process_ways which at this point
        is lacking coordinates -> next step.

        :param ways: osm way objects
        :type ways: list of osm ways
        """
        for osmid, tags, refs in ways:
            if len(refs) >= 1000:
                continue

            categories = categories_tools.get_category(tags)

            if len(categories) == 0 and osmid in self.relation_ways:
                tags = self.relation_ways[osmid]
                categories = categories_tools.get_category(tags)

            if len(categories) > 0:
                self.ways_cnt += 1
                for ref in refs:
                    self.nodes_store.append(ref, (None, None))
                    self.process_ways_set.add(osmid)


    def parse_coords_and_store(self, coords):
        for osmid, lat, lng in coords:
            if osmid in self.nodes_store:
                self.nodes_store.set(osmid, (lat, lng))


    def parse_ways_second(self, ways):
        """
        Callback function called by imposm while ways are parsed. If a category can't be found it may likely
        be that the osmid of this way can be found in self.relation_ways which will contain additional tags
        and therefore eventually a category. A way object is added to a list process_ways which at this point
        is lacking coordinates -> next step.

        :param ways: osm way objects
        :type ways: list of osm ways
        """
        for osmid, tags, refs in ways:
            if osmid not in self.process_ways_set:
                continue
            categories = categories_tools.get_category(tags)
            # from way
            osm_type = 2

            if len(categories) == 0 and osmid in self.relation_ways:
                # current way is the outer ring of a relation which was marked as having a category
                tags = self.relation_ways[osmid]
                categories = categories_tools.get_category(tags)
                # from relation
                osm_type = 3

            # Calculate centroid of way
            refs = set(refs)
            sum_lat = 0
            sum_lng = 0
            way_valid = True
            for ref in refs:
                if ref not in self.nodes_store: # should never ha
                    way_valid = False
                    break
                lat, lng = self.nodes_store.get(ref)
                if lat is None or lng is None or np.isnan(lat) or np.isnan(lng):
                    way_valid = False
                    break
                sum_lat += lat
                sum_lng += lng
            if not way_valid:
                continue

            self.process_ways_set.remove(osmid)
            centroid_lat = sum_lat / len(refs)
            centroid_lng = sum_lng / len(refs)
            try:
                self.create_poi(osm_type, osmid, [centroid_lat, centroid_lng], tags, categories)
            except Exception as e:
                logger.debug(e)
                self.failed = True
                return


    def create_poi(self, osm_type, osm_id, lat_lng, tags, categories=None):
        """
        Creates a poi entity if a category is found. Stored afterwards.

        :param tags: osm tags of poi
        :type tags: list of objects
        :param osm_id: osmid
        :type osm_id: int
        :param lat_lng: coordinates
        :type lat_lng: list
        :param osm_type: 1 for node, 2 for way, 3 for way from relation
        :type osm_type: int
        :param categories: category list
        :type categories: list
        """
        if categories is None:
            categories = categories_tools.get_category(tags)

        if len(categories) > 0:
            # create dynamically from settings yml
            for key, value in tags.items():
                if key in ops_settings["column_mappings"]:
                    self.store_tags(TagsObject(osm_type, osm_id, key, value))

            for category in categories:
                self.store_categories(osm_type, osm_id, category)

            if osm_type == 1:
                self.nodes_cnt += 1

            self.store_poi(PoiObject(osm_type, osm_id, lat_lng, categories))


    def store_poi(self, poi_object):
        """
        Appends poi storage objects to buffer for bulk storage to database.
        """
        self.pois_count += 1
        self.poi_objects.append(POIs(
            osm_type=poi_object.osmtype,
            osm_id=poi_object.osmid,
            geom=poi_object.geom,
            src_index=self.osm_file_index,
            delflag=False
        ))
        if self.pois_count % 1000 == 0:
            logger.debug(f"Pois: {self.pois_count}, tags: {self.tags_cnt}, categories: {self.categories_cnt}")
            self.save_buffer()


    def store_tags(self, tags_object):
        """
        Appends tags storage objects to buffer for bulk storage to database.
        """
        self.tags_cnt += 1
        self.tags_objects.append(Tags(
            osm_type=tags_object.osmtype,
            osm_id=tags_object.osmid,
            key=tags_object.key,
            value=tags_object.value
        ))


    def store_categories(self, osmtype, osmid, category):
        """
        Appends category storage objects to buffer for bulk storage to database.
        """
        self.categories_cnt += 1
        self.categories_objects.append(Categories(
            osm_type=osmtype,
            osm_id=osmid,
            category=category
        ))


    def save_buffer(self):
        """
        Save POIs, tags and categories to database and clear buffer.
        If running in update mode, delete all POIs with IDs in buffer first. Foreign key constraints in the database
        handle deletion of related tags/categories.
        """

        if not self.update_mode:
            for poi in self.poi_objects:
                if len(db.session.query(POIs).filter_by(osm_type=poi.osm_type, osm_id=poi.osm_id).all()) > 0:
                    self.update_mode = True

        if self.update_mode:
            for poi in self.poi_objects:
                db.session.query(POIs).filter_by(osm_type=poi.osm_type, osm_id=poi.osm_id).delete()
            db.session.commit()

        db.session.bulk_save_objects(self.poi_objects)
        db.session.bulk_save_objects(self.tags_objects)
        db.session.bulk_save_objects(self.categories_objects)
        db.session.commit()
        self.poi_objects = []
        self.tags_objects = []
        self.categories_objects = []
