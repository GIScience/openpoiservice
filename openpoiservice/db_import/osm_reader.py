import osmium
from shapely import wkb as wkblib
import logging
import uuid
from copy import deepcopy

from openpoiservice import categories_tools, ops_settings, db
from openpoiservice.db_import.models import Pois, Tags, Categories

logger = logging.getLogger(__name__)

wkb_fac = osmium.geom.WKBFactory()
wkt_fac = osmium.geom.WKTFactory()


# TODO: Use logic to pick best memory option based on
class OsmReader(osmium.SimpleHandler):
    """Let's see where this leads.."""

    def __init__(self, filename):
        """
        This is osmium's parser class.

        :param filename: The OSM file's name.
        :type filename: str
        """
        super().__init__()
        self._poi_objects = list()
        self._tag_objects = list()
        self._cat_objects = list()

        # Counters
        self.poi_count = 0

        self.filename = filename

    @staticmethod
    def extract_tags(tags):
        """
        Takes a :class:`osmium.osm.TagList` object and returns as dict

        :param tags: The tags returned from osmium.
        :type tags: osmium.osm.TagList

        :rtype: dict
        """
        return {tag.k: tag.v for tag in tags}

    def node(self, obj_node):
        """
        Call back for :class:`osmium.osm.Node` parser.

        :param obj_node: The node currently processed.
        :type obj_node: osmium.osm.Node
        """
        cat_included = categories_tools.get_category(obj_node.tags)
        if cat_included:
            osmid = deepcopy(obj_node.id)
            tags = self.extract_tags(obj_node.tags)
            location = wkt_fac.create_point(obj_node.location)

            self.store_objects(
                osmid=osmid,
                tags=tags,
                location=location,
                osm_type=1,
                categories=cat_included
            )

    def area(self, obj_area):
        """
        Callback for :class:`osmium.osm.Area` parser

        :param obj_area: The current area being processed.
        :type obj_area: osmium.osm.Area
        """
        cat_included = categories_tools.get_category(obj_area.tags)
        if cat_included:
            if obj_area.from_way():
                osm_type = 2
            else:
                osm_type = 3

            osmid = deepcopy(obj_area.id)
            tags = self.extract_tags(obj_area.tags)
            # Determine centroid
            # TODO: import whole polygons, maybe simplified
            wkb_area = wkb_fac.create_multipolygon(obj_area)
            geom_multipolygon = wkblib.loads(wkb_area, hex=True)

            for poly in geom_multipolygon:
                self.store_objects(
                    osmid=osmid,
                    tags=tags,
                    location=poly.centroid.wkt,
                    osm_type=osm_type,
                    categories=cat_included
                )

        pass

    def store_objects(self, osmid, tags, location, osm_type, categories):
        """
        Creates the model objects and saves them periodically.

        :type osmid: int
        :type tags: dict
        :type location: list|tuple[int]
        :type osm_type: int

        :param categories: The valid categories for each POI
        :type categories: list
        """
        self.poi_count += 1
        # TODO: get rid of uuid, seems pointless as PK (which is not even true other than the OSM object table)
        # random id used as primary key
        uid = uuid.uuid4().bytes

        # Create and store tags dynamically from settings yml
        # TODO: since tags table is 1:1 with OSM objects, this doesn't have to be its own table
        # consider putting it in a JSON column instead in the OSM object table
        for tag_key, tag_value in tags.items():
            if tag_key in ops_settings['column_mappings']:
                self._tag_objects.append(Tags(
                    uuid=uid,
                    osm_id=osmid,
                    key=tag_key,
                    value=tag_value
                ))

        # Create POI object
        self._poi_objects.append(Pois(
            uuid=uid,
            osm_id=osmid,
            osm_type=osm_type,
            geom=location
        ))

        # Create categories
        # TODO: Categories should only be stored once. Now it's creating a quadrillion useless copies
        for category in categories:
            self._cat_objects.append(Categories(
                uuid=uid,
                category=category
            ))

        # periodically dump the objects in the DB
        if len(self._poi_objects) % 10000 == 0:
            logger.info(f"{self.filename}: {self.poi_count} POIs")
            self.save_objects()

    def save_objects(self):
        """
        Saves the objects in the DB.
        """
        db.session.add_all(self._poi_objects)
        db.session.add_all(self._cat_objects)
        db.session.add_all(self._tag_objects)
        db.session.commit()
        self._poi_objects.clear()
        self._tag_objects.clear()
        self._cat_objects.clear()
