from math import radians, cos, sin, asin, sqrt

#taken from : http://stackoverflow.com/questions/15736995/how-can-i-quickly-estimate-the-distance-between-two-latitude-longitude-points
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6367 * c
    return km


def find_nearest_address(lon, lat, addresses):
    """
    Scans the address list and gets back the one with minimum distance
    """

    def _extract_lat_lon_from_addr(addr):
        geo_loc = addr.get("geo_location")
        if not geo_loc:
            return None, None

        return geo_loc["lon"], geo_loc["lat"]

    min_distance = float("inf")
    index = 0

    for i, a in enumerate(addresses):
        a_lon, a_lot = _extract_lat_lon_from_addr(a)
        if not a_lot or not a_lon:
            continue

        tmp_distance = haversine(lon, lat, a_lon, a_lot)
        if tmp_distance < min_distance:
            index = i
            min_distance = tmp_distance

    #get back the closest one
    return addresses[index]