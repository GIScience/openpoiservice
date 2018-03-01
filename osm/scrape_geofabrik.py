import scrapy
import urlparse
from scrapy.selector import Selector
import subprocess


class GeoFabrikSpider(scrapy.Spider):
    name = "geofabrik_spider"
    start_urls = ['https://download.geofabrik.de/']

    def parse(self, response):

        set_selector = '.subregion'
        for region in response.css(set_selector):
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
            download_link = urlparse.urljoin(response.url, sub_region)

            subprocess.call(['wget', download_link])

            yield {
                "subregion_link": download_link,
            }
