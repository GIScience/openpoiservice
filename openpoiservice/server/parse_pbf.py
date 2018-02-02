# openpoiservice/server/parse_pbf.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools
from openpoiservice.server.models import Pois
from openpoiservice.server.poi_entity import PoiEntity


class LatLng(object):
    """ Class that creates a latlng object. """

    def __init__(self, lat, lng):
        """
        Initializes latlng object
        :param lat: latitude of coordinate
        :param lng: longitude of coordinate
        """
        self.lat = lat
        self.lng = lng


class WayObject(object):
    """ Class that creates a way object. """

    def __init__(self, osm_id, tags, refs, cat_id):
        """
        Initializes way object
        :param osm_id: osmid
        :param tags: osm tags
        :param refs: references to nodes in this way
        :param cat_id: category derived
        """
        self.osm_id = osm_id
        self.tags = tags
        self.refs = refs
        self.cat_id = cat_id


class PbfImporter(object):
    """ Class that handles the parsed OSM data. """

    def __init__(self):
        """
        Initializes pbf importer class with necessary counters
        :param categories_file: this is the parsed yml file containing categories
        """
        self.relations_cnt = 0
        self.entity_cnt = 0
        self.ways_cnt = 0
        self.nodes_cnt = 0
        self.global_cnt = 0
        self.pois_cnt = 0
        self.relation_ways = {}
        self.nodes = {}
        self.process_ways = []
        self.poi_objects = []

    def parse_relations(self, relations):
        """
        Callback function called by imposm after relations are parsed. The idea is to extract polygons which may
        contain poi tags of interested. For this we are currently using osm_type=multipolygon.
        The osm ids of the found objects are then used in parse_ways.
        :param relations: osm relations objects
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
                            osmid_rel = rel_member[0]
                            self.relation_ways[osmid_rel] = tags
                            self.relation_ways[osmid_rel].update({'relation_id': osmid})
                            self.relations_cnt += 1

                            if self.relations_cnt % 10000 == 0:
                                print 'Relations found: {} '.format(self.relations_cnt)

            self.entity_cnt += 1

    def parse_ways(self, ways):
        """
        Callback function called by imposm after ways are parsed. If a category can't be found it may likely
        be that the osmid of this way can be found in self.relation_ways which will contain additional tags
        and therefor eventually a category. A way object is added to a list process_ways which at this point
        is lacking coordinates -> next step.
        :param ways: osm way objects
        """
        for osmid, tags, refs in ways:
            category_id = categories_tools.get_category(tags)

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

            if category_id > 0:

                if len(refs) < 1000:

                    for node in refs:
                        self.nodes[node] = None
                    self.ways_cnt += 1

                    if self.ways_cnt % 50000 == 0:
                        print 'Ways found: {} '.format(self.ways_cnt)

                    ways_obj = WayObject(osmid, tags, refs, category_id)
                    self.process_ways.append(ways_obj)

    def store_poi(self, poi_entity):
        """
        Appends poi object to storage objects which are bulk saved to database.
        :param poi_entity: poi object
        """
        self.pois_cnt += 1
        self.poi_objects.append(Pois(osm_id=poi_entity.osmid,
                                     osm_type=poi_entity.type,
                                     category=poi_entity.category,
                                     name=poi_entity.name,
                                     website=poi_entity.website,
                                     phone=poi_entity.phone,
                                     opening_hours=poi_entity.opening_hours,
                                     wheelchair=poi_entity.wheelchair_access,
                                     smoking=poi_entity.smoking,
                                     fee=poi_entity.fee,
                                     address=poi_entity.address,
                                     geom='SRID={};POINT({} {})'.format(4326, str(poi_entity.latitude),
                                                                        str(poi_entity.longitude)),
                                     location='SRID={};POINT({} {})'.format(4326, str(poi_entity.latitude),
                                                                            str(poi_entity.longitude))
                                     ))

        if self.pois_cnt % 1000 == 0:
            print 'bulk: {}'.format(self.pois_cnt)
            db.session.bulk_save_objects(self.poi_objects)
            db.session.commit()
            self.poi_objects = []

        if self.pois_cnt % 50000 == 0:
            print 'POIs found: {} ({} % parsed, type= {}'.format(self.pois_cnt,
                                                                 self.global_cnt * 100 / self.entity_cnt, 1)

    def create_poi(self, tags, osmid, lat_lng, osm_type, category=0):
        """
        Creates a poi entity if a category is found. Stored afterwards
        :param tags: osm tags of poi
        :param osmid: osmid
        :param lat_lng: coordinates
        :param osm_type: 1 for node, 2 for way
        :param category: category id
        """
        if category == 0:
            category = self.categories_tools.get_category(tags)

        if category > 0:
            self.nodes[osmid] = lat_lng

            poi_entity = PoiEntity(category, osmid, tags, lat_lng, osm_type)
            self.store_poi(poi_entity)

    def parse_coords(self, coords):
        """
        Callback function called by imposm after coordinates are parsed. Saves coordinates to nodes dictionary for
        way nodes that so far don't comprise coordinates.
        :param coords: osm coordinate objects
        """
        for osmid, lat, lng in coords:

            # populate missing coords of ways, will be used later
            if osmid in self.nodes and self.nodes[osmid] is None:
                self.nodes[osmid] = LatLng(lat, lng)

    def parse_nodes(self, osm_nodes):
        """
        Callback function called by imposm after nodes are parsed.
        :param osm_nodes: osm node objects
        """
        osm_type = 1

        for osmid, tags, refs in osm_nodes:
            self.global_cnt += 1
            lat_lng = LatLng(refs[1], refs[0])
            self.create_poi(tags, osmid, lat_lng, osm_type)

    def parse_nodes_of_ways(self):
        """
        Loops through list process_ways. Each way in this list has a tag which corresponds to a category.
        It tries to find coordinates of these nodes and creates a simple average position of these which is the
        poi. Saved to DB afterwards.
        """
        osm_type = 2
        for way in self.process_ways:

            way_length = len(way.refs)
            if way_length > 0:
                sum_lat = 0.0
                sum_lng = 0.0
                broken_way = False

                way_nodes = way.refs

                for osmid in way_nodes:

                    if osmid not in self.nodes:
                        broken_way = True
                        break

                    sum_lat += self.nodes[osmid].lat
                    sum_lng += self.nodes[osmid].lng

                if not broken_way:
                    lat = sum_lat / way_length
                    lng = sum_lng / way_length
                    lat_lng = LatLng(lat, lng)

                    self.create_poi(way.tags, way.osm_id, lat_lng, osm_type, way.cat_id)

        # save the remainder
        db.session.bulk_save_objects(self.poi_objects)
        db.session.commit()
