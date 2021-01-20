# USAGE: sudo scrapy runspider GeoFabrikSpider.py

import scrapy
import os
import subprocess
from time import sleep
from urllib import parse
from scrapy.selector import Selector


class GeoFabrikSpider(scrapy.Spider):

    name = "geofabrik_spider"
    start_urls = ['https://download.geofabrik.de/']
    wait_time = 30

    def parse(self, response):

        regions = ['Asia', 'Europe', 'North America']
        regions_files = ['asia-latest.osm.pbf', 'europe-latest.osm.pbf', 'north-america-latest.osm.pbf']

        # get regions with small enough files
        sel = Selector(response)
        sub_regions = sel.xpath("//a[contains(text(),'[.osm.pbf]')]/@href").extract()
        for sub_region in sub_regions:
            if sub_region not in regions_files:
                if os.path.exists(sub_region):
                    print('{} already downloaded'.format(sub_region))
                else:
                    print('Starting download of {}'.format(sub_region))
                    download_link = parse.urljoin(response.url, sub_region)
                    subprocess.call(["wget", "-q", download_link])
                    sleep(self.wait_time)

        # get sub regions where there is lots of data
        set_selector = '.subregion'
        for region in response.css(set_selector):
            name_selector = 'a ::text'
            subregion = region.css(name_selector).extract_first()
            if subregion in regions:
                link_selector = 'a::attr(href)'
                next_page = region.css(link_selector).extract_first(),
                yield scrapy.Request(
                    parse.urljoin(response.url, next_page[0]),
                    callback=self.fetch_sub_regions
                )

    def fetch_sub_regions(self, response):

        sel = Selector(response)
        sub_regions = sel.xpath("//a[contains(text(),'[.osm.pbf]')]/@href").extract()
        exclude_subregions = ["alps-latest.osm.pbf", "britain-and-ireland-latest.osm.pbf", "dach-latest.osm.pbf", "us-latest.osm.pbf"]
        for sub_region in sub_regions:
            head, tail = os.path.split(sub_region)
            if tail in exclude_subregions:
                continue

            if os.path.exists(f"{head}/{tail}"):
                print('{} already downloaded'.format(tail))
            else:
                print('Starting download of {}'.format(tail))
                download_link = parse.urljoin(response.url, sub_region)
                subprocess.call(["wget", "-q", f"-P{head}", download_link])
                sleep(self.wait_time)

                yield {
                   "subregion_link": download_link,
                }
