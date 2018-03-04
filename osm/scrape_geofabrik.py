import scrapy
import urlparse
from scrapy.selector import Selector
import subprocess
from time import sleep

# while read p; do
#  wget $p
#  sleep 120
# done <gf_dl.txt

gf_file = open('gf_dl.txt', 'w+')


class GeoFabrikSpider(scrapy.Spider):

    name = "geofabrik_spider"
    start_urls = ['https://download.geofabrik.de/']

    def parse(self, response):

        set_selector = '.subregion'
        for region in response.css(set_selector):

            name_selector = 'a ::text'
            subregion = region.css(name_selector).extract_first()

            if subregion in ['Asia', 'Europe', 'North America']:
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

            self.gf_file.write(download_link + "\n")
            # subprocess.call(['wget', download_link])

            # sleep(120)  # few minutes

            yield {
                "subregion_link": download_link,
            }
