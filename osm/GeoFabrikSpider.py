#sudo scrapy runspider GeoFabrikSpider.py

import scrapy
import os
import urlparse
from scrapy.selector import Selector
import subprocess
from time import sleep


class GeoFabrikSpider(scrapy.Spider):

    name = "geofabrik_spider"
    start_urls = ['https://download.geofabrik.de/']

    def parse(self, response):

        set_selector = '.subregion'
        for region in response.css(set_selector):

            name_selector = 'a ::text'
            subregion = region.css(name_selector).extract_first()

            regions = ['Europe']
            #regions = ['Asia', 'Europe', 'North America']


            if subregion in regions:
                link_selector = 'a::attr(href)'

                next_page = region.css(link_selector).extract_first(),

                yield scrapy.Request(
                    urlparse.urljoin(response.url, next_page[0]),
                    callback=self.fetch_sub_regions
                )

    def fetch_sub_regions(self, response):

        sel = Selector(response)
        sub_regions = sel.xpath("//a[contains(text(),'[.osm.pbf]')]/@href").extract()

        for sub_region in sub_regions:

            head, tail = os.path.split(sub_region)

            print(head, tail)
            print('does it exist?', tail)

            if os.path.exists(tail):
                print('{} already downloaded'.format(tail))
            else:
                print('Starting download of {}'.format(tail))

                download_link = urlparse.urljoin(response.url, sub_region)
                subprocess.call(['wget', download_link])
                sleep(120)  # few minutes

                yield {
                   "subregion_link": download_link,
                }
