from openpoiservice.server.db_import.osm_reader import OsmReader

r = OsmReader()
r.apply_file('/home/nilsnolde/dev/python/openpoiservice/osm/bremen-tests.osm.pbf', locations=True, idx='sparse_mmap_array')

print(r.areas)
print(r.areas_from_line)