# openpoiservice/server/parse_osm.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools, ops_settings
from openpoiservice.server.db_import.models import Pois, Tags, Categories
from openpoiservice.server.db_import.objects import PoiObject, TagsObject
from openpoiservice.server.utils.decorators import get_size
import shapely as shapely
from shapely.geometry import Point, Polygon, LineString, MultiPoint
import logging
import uuid
import time
import sys
from timeit import Timer
from bisect import bisect_left
from collections import deque

logger = logging.getLogger(__name__)


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

        :param cat_id: category derived
        :type cat_id: int
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

    def __init__(self):
        """ Initializes pbf importer class with necessary counters."""

        self.relations_cnt = 0
        self.ways_cnt = 0
        self.nodes_cnt = 0
        self.pois_cnt = 0
        self.tags_cnt = 0
        self.categories_cnt = 0
        self.relation_ways = {}
        self.nodes = {}
        self.process_ways = []
        self.poi_objects = []
        self.tags_objects = []
        self.categories_objects = []
        self.ways_temp = []
        self.ways_obj = None
        self.tags_object = None
        self.poi_object = None
        self.process_ways_length = None

    def parse_relations(self, relations):
        """
        Callback function called by imposm while relations are parsed. The idea is to extract polygons which may
        contain poi tags of interest. For this we are currently using osm_type=multipolygon.
        The osm ids of the found objects are then used in parse_ways.

        :param relations: osm relations objects
        :type relations: list of osm relations

        """
        for osmid, tags, refs in relations:
            skip_relation = True

            for tag, value in tags.items():

                if tag == "type" and value == "multipolygon":
                    skip_relation = False

                    break

            if not skip_relation:
                categories = categories_tools.get_category(tags)

                if len(categories) > 0:

                    if len(refs) > 0:
                        rel_member = refs[0]

                        # consider only outer rings
                        if rel_member[2] == 'outer':
                            osmid_rel_member = rel_member[0]
                            self.relation_ways[osmid_rel_member] = tags
                            self.relation_ways[osmid_rel_member].update({'relation_id': osmid})
                            self.relations_cnt += 1

                            if self.relations_cnt % 10000 == 0:
                                logger.info('Relations found: {} '.format(self.relations_cnt))

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

            if len(categories) == 0:

                if osmid in self.relation_ways:
                    tags = self.relation_ways[osmid]

                    # substitute current way for the outer ring of a relation
                    if len(refs) < 100:
                        # rel_id = osmid

                        # for tag_name, tag_value in tags_from_relations.iteritems():

                        #    if tag_name == 'relation_id':

                        #        rel_id = tag_value
                        #        break
                        categories = categories_tools.get_category(tags)
                        # from relation
                        osm_type = 3

            if len(categories) > 0:

                if len(refs) < 1000:

                    self.ways_cnt += 1

                    if self.ways_cnt % 50000 == 0:
                        logger.info('Ways found: {} '.format(self.ways_cnt))

                    # Make unique as duplicates may be inside
                    refs = list(set(refs))
                    refs.sort(key=int)

                    self.ways_obj = WayObject(osmid, osm_type, tags, refs, categories, len(refs))

                    self.process_ways.append(self.ways_obj)

    def store_poi(self, poi_object):
        """
        Appends poi object to storage objects which are bulk saved to database.

        :param poi_object: poi object
        :type poi_object: object
        """

        self.pois_cnt += 1
        self.poi_objects.append(Pois(
            uuid=poi_object.uuid,
            osm_id=poi_object.osmid,
            osm_type=poi_object.type,
            geom=poi_object.geom
        ))

        if self.pois_cnt % 1000 == 0:
            logger.info('Pois: {}, tags: {}, categories: {}'.format(self.pois_cnt, self.tags_cnt, self.categories_cnt))
            db.session.add_all(self.poi_objects)
            db.session.add_all(self.tags_objects)
            db.session.add_all(self.categories_objects)
            db.session.commit()
            self.poi_objects = []
            self.tags_objects = []
            self.categories_objects = []

    def store_tags(self, tags_object):
        """
        Appends tags object to storage objects which are bulk saved to database.

        :param tags_object: tags object
        :type tags_object: object
        """

        self.tags_cnt += 1

        self.tags_objects.append(Tags(
            uuid=tags_object.uuid,
            osm_id=tags_object.osmid,
            key=tags_object.key,
            value=tags_object.value
        ))

    def store_categories(self, uuid, category):
        """

        :param uuid:
        :param category:
        """
        self.categories_cnt += 1

        self.categories_objects.append(Categories(
            uuid=uuid,
            category=category
        ))

    def create_poi(self, tags, osmid, lat_lng, osm_type, categories=[]):
        """
        Creates a poi entity if a category is found. Stored afterwards.

        :param tags: osm tags of poi
        :type tags: list of objects

        :param osmid: osmid
        :type osmid: int

        :param lat_lng: coordinates
        :type lat_lng: list

        :param osm_type: 1 for node, 2 for way
        :type osm_type: int

        :param categories: category list
        :type categories: list

        """
        if len(categories) == 0:
            categories = categories_tools.get_category(tags)

        if len(categories) > 0:

            # random id used as primary key
            my_uuid = uuid.uuid4().bytes

            # create dynamically from settings yml
            for tag, value in tags.items():

                if tag in ops_settings['column_mappings']:
                    self.tags_object = TagsObject(my_uuid, osmid, tag, value)
                    self.store_tags(self.tags_object)

            self.poi_object = PoiObject(my_uuid, categories, osmid, lat_lng, osm_type)
            self.store_poi(self.poi_object)

            for category in categories:
                self.store_categories(my_uuid, category)

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

                        centroid = (centroid_lat, centroid_lng)

                        self.create_poi(way.tags, way.osm_id, centroid, way.osm_type, way.categories)

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

                        self.insert_temp_way(t_way)

            self.ways_temp = []

    def insert_temp_way(self, t_way):
        """
        Inserts a temp way to process_ways with binary search
        :param t_way:
        :type t_way: temp way
        """
        self.process_ways.insert(bisect_left(self.process_ways, t_way), t_way)

    def parse_coords_for_ways2(self, coords):
        """
        Callback function called by imposm while coordinates are parsed. Saves coordinates to nodes dictionary for
        way nodes that so far don't comprise coordinates.

        :param coords: osm coordinate objects
        :type coords: list of osm coordinates
        """
        for osmid, lat, lng in coords:

            # nothing to do, all ways processed
            if len(self.process_ways_length) == 0:
                break

            # current osmid is smaller then ordered ref osmids of way in process_ways
            if osmid < self.process_ways[0].refs[0]:
                continue

            p_index = 0
            # two ways could have the same ref as current osmid
            while len(self.process_ways_length) != 0:

                # if the first osm id matches
                if self.process_ways[p_index].refs[0] == osmid:

                    # pop the way from process_ways
                    way = self.process_ways[p_index]
                    p_index += 1

                    # remove first osm id from way as it is found
                    way.refs.pop(0)

                    # sum up coordinates
                    way.sum_lat += lat
                    way.sum_lng += lng

                    # way has all its coordinates, create centroid and store in db
                    if len(way.refs) == 0:

                        centroid_lat = way.sum_lat / way.n_refs
                        centroid_lng = way.sum_lng / way.n_refs

                        centroid = (centroid_lat, centroid_lng)

                        self.create_poi(way.tags, way.osm_id, centroid, way.osm_type, way.categories)

                    # way not completely seen yet, append to ways temp
                    else:

                        self.ways_temp.append(way)

                # break out of while if first ref osmid doesnt match current osmid
                else:

                    break

            # reorder process_ways.
            # process_ways is already ordered from >= p_index
            # every way before p_index needs to be checked and ordered again
            self.ways_temp.sort(key=lambda x: x.refs[0])

            t_index = 0

            # If way_temp first ref smaller equal than process_ways first ref then just replace old way
            while t_index < len(self.ways_temp) and self.ways_temp[t_index].refs[0] <= self.process_ways[p_index].refs[
                0]:
                self.process_ways[t_index] = self.ways_temp[t_index]  # replace way with temp_way in process_ways
                t_index += 1

            p_index2 = t_index

            while t_index < len(self.ways_temp) and p_index < self.process_ways_length:
                if self.ways_temp[t_index].refs[0] <= self.process_ways[p_index].refs[0]:
                    self.process_ways[p_index2] = self.ways_temp[t_index]
                    t_index += 1
                else:
                    self.process_ways[p_index2] = self.process_ways[p_index]
                    p_index += 1

                p_index2 += 1

            while t_index < len(self.ways_temp):
                # we have ways left in temp but process_ways is empty, so copy the remaining temp_ways
                # to process_ways beginning at position pIndex2
                # may be there is a better way to copy a bunch of elements from one array to another than
                # to just copy them way by way!
                self.process_ways[p_index2] = self.ways_temp[t_index]
                p_index2 += 1
                t_index += 1

            while p_index < self.process_ways_length:
                # we have ways left in process_ways and we need to SHIFT them to the left
                # maybe there is operator which is faster than just copy way by way!
                self.process_ways[p_index2] = self.process_ways[p_index]
                p_index2 += 1
                p_index += 1

            # new length of process_ways
            self.process_ways_length = p_index2
            self.ways_temp = []

    def parse_nodes(self, osm_nodes):
        """
        Callback function called by imposm while nodes are parsed.

        :param osm_nodes: osm node objects
        :type osm_nodes: list of osm nodes
        """

        # from node
        osm_type = 1

        for osmid, tags, refs in osm_nodes:
            lat_lng = (refs[0], refs[1])

            self.create_poi(tags, osmid, lat_lng, osm_type)

    def save_remainder(self):
        # save the remainder
        db.session.bulk_save_objects(self.poi_objects)
        db.session.bulk_save_objects(self.tags_objects)
        db.session.bulk_save_objects(self.categories_objects)
        db.session.commit()
