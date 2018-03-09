# openpoiservice/server/parse_osm.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools, ops_settings
from openpoiservice.server.db_import.models import Pois, Tags
from openpoiservice.server.db_import.objects import PoiObject, TagsObject
from openpoiservice.server.utils.decorators import get_size
import shapely as shapely
from shapely.geometry import Point, Polygon, LineString, MultiPoint
import logging
import uuid
import sys
from timeit import Timer

logger = logging.getLogger(__name__)


class WayObject(object):
    """ Class that creates a way object. """

    def __init__(self, osm_id, osm_type, tags, refs, cat_id, n_refs):
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
        self.cat_id = cat_id
        self.sum_lat = 0.0
        self.sum_lng = 0.0
        self.n_refs = n_refs


class OsmImporter(object):
    """ Class that handles the parsed OSM data. """

    def __init__(self):
        """ Initializes pbf importer class with necessary counters."""

        self.relations_cnt = 0
        self.ways_cnt = 0
        self.nodes_cnt = 0
        self.pois_cnt = 0
        self.tags_cnt = 0
        self.relation_ways = {}
        self.nodes = {}
        self.process_ways = []
        self.poi_objects = []
        self.tags_objects = []
        self.ways_temp = []
        self.ways_obj = None
        self.tags_object = None
        self.poi_object = None

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

            for tag, value in tags.iteritems():

                if tag == "type" and value == "multipolygon":
                    skip_relation = False

                    break

            if not skip_relation:
                category_id = categories_tools.get_category(tags)

                if category_id > 0:

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
            category_id = categories_tools.get_category(tags)
            # from way
            osm_type = 2

            if category_id == 0:

                if osmid in self.relation_ways:
                    tags = self.relation_ways[osmid]

                    # substitute current way for the outer ring of a relation
                    if len(refs) < 100:
                        # rel_id = osmid

                        # for tag_name, tag_value in tags_from_relations.iteritems():

                        #    if tag_name == 'relation_id':

                        #        rel_id = tag_value
                        #        break
                        category_id = categories_tools.get_category(tags)
                        # from relation
                        osm_type = 3

            if category_id > 0:

                if len(refs) < 1000:

                    self.ways_cnt += 1

                    if self.ways_cnt % 50000 == 0:
                        logger.info('Ways found: {} '.format(self.ways_cnt))

                    # Make unique as duplicates may be inside
                    refs = list(set(refs))
                    refs.sort(key=int)

                    self.ways_obj = WayObject(osmid, osm_type, tags, refs, category_id, len(refs))

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
            category=poi_object.category,
            geom=poi_object.geom
        ))

        if self.pois_cnt % 1000 == 0:
            logger.info('Pois: {}, tags: {}'.format(self.pois_cnt, self.tags_cnt))
            db.session.add_all(self.poi_objects)
            db.session.add_all(self.tags_objects)
            db.session.commit()
            self.poi_objects = []
            self.tags_objects = []

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

    def create_poi(self, tags, osmid, lat_lng, osm_type, category=0):
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

        :param category: category id
        :type category: int

        """
        if category == 0:
            category = categories_tools.get_category(tags)

        if category > 0:

            # random id used as primary key
            my_uuid = uuid.uuid4().bytes

            # create dynamically from settings yml
            for tag, value in tags.iteritems():

                if tag in ops_settings['column_mappings']:
                    self.tags_object = TagsObject(my_uuid, osmid, tag, value)
                    self.store_tags(self.tags_object)

            self.poi_object = PoiObject(my_uuid, category, osmid, lat_lng, osm_type)
            self.store_poi(self.poi_object)

    def parse_coords_for_ways(self, coords):
        """
        Callback function called by imposm while coordinates are parsed. Saves coordinates to nodes dictionary for
        way nodes that so far don't comprise coordinates.

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
                    way = self.process_ways.pop(0)

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

                        self.create_poi(way.tags, way.osm_id, centroid, way.osm_type, way.cat_id)

                    # way not completely seen yet, append to ways temp
                    else:

                        self.ways_temp.append(way)

                # break out of while if first ref osmid doesnt match current osmid
                else:

                    break

            # if ways_temp length greater 0 add to process ways and resort
            if len(self.ways_temp) > 0:
                self.process_ways = self.process_ways + self.ways_temp
                self.ways_temp = []
                self.process_ways.sort(key=lambda x: x.refs[0])

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
        db.session.commit()
