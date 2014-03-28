import time

from dealfu.esutils import EsDealsQuery
from dealfu.utils import haversine
from django.core.management.base import BaseCommand

import requests

class Command(BaseCommand):
    """
    Checks the collected addresses against the free service
    """

    API_ENDPOINT = "http://www.datasciencetoolkit.org/maps/api/geocode/json"
    TRESHOLD = 0.4
    TRESHOLD_06 = 0.6
    TRESHOLD_08 = 0.8
    TRESHOLD_1 = 1

    def handle(self, *args, **options):
        """
        check all of the deals that have geo data
        """
        cur_page = 0
        fetched = 100

        stats = []

        query = EsDealsQuery()
        query = query.filter_by_enabled()
        query = query.filter_page(page=0, per_page=100)

        result = query.fetch()
        tmp_stats = self._check_addresses(result)
        stats.extend(tmp_stats)

        fetched += 100
        total = query.total
        #print "TOTAL: ",query.total

        while len(result) != 0:
            print "NEXT_BATCH ",len(result)
            cur_page += 1
            query.filter_page(cur_page, per_page=100)
            result = query.fetch()
            fetched += 100

            print "------- FETCHED %{} --------- ".format(self._get_percentage(total, fetched))

            tmp_stats = self._check_addresses(result)
            stats.extend(tmp_stats)

            good_addr_04 = [s for s in stats if s <= self.TRESHOLD]
            good_addr_06 = [s for s in stats if s <= self.TRESHOLD_06]
            good_addr_08 = [s for s in stats if s <= self.TRESHOLD_08]
            good_addr_1 = [s for s in stats if s <= self.TRESHOLD_1]

            allstat = len(stats)


            print "Threshhold {} - %{} percentage".format(self.TRESHOLD,
                                                          self._get_percentage(allstat,
                                                                               len(good_addr_04)))
            print "Threshhold {} - %{} percentage".format(self.TRESHOLD_06,
                                                          self._get_percentage(allstat,
                                                                               len(good_addr_06)))
            print "Threshhold {} - %{} percentage".format(self.TRESHOLD_08,
                                                          self._get_percentage(allstat,
                                                                               len(good_addr_08)))
            print "Threshhold {} - %{} percentage".format(self.TRESHOLD_1,
                                                          self._get_percentage(allstat,
                                                                               len(good_addr_1)))

        #print len(stats)
        #print len(good_addr)


    def _get_percentage(self, allstat, goodstat):
        return 100 * goodstat / allstat

    def _check_addresses(self, results):

        stats = []
        for r in results:
            addresses = r["_source"]["merchant"]["addresses"]
            for a in addresses:
                geo_info = a["geo_location"]
                lon = geo_info["lon"]
                lat = geo_info["lat"]

                #make a request to free address
                payload = {"address":a["address"],
                  "sensor":"false",
                }

                print "CHECK : ",a
                r = requests.get(self.API_ENDPOINT,
                                 params=payload)

                result = r.json()
                if result["status"] != "OK":
                    print "RESULT not Ok ",result
                    #log something here and start waiting
                    time.sleep(5)
                    continue

                geo = result["results"][0]["geometry"]["location"]
                free_geo = {
                    "lat":geo["lat"],
                    "lon":geo["lng"]
                }

                distance = haversine(lon, lat,
                                     free_geo["lon"], free_geo["lat"])

                stats.append(distance)
                time.sleep(1)


        return stats