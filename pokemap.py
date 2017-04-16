import requests
from math import radians, cos, sin, asin, sqrt
from datetime import datetime
import os


geocode_api_key = os.environ["GOOGLE_GEOCODE_API"]

# Pokemon index to lookup pokemon name
with open('pokemon.json', 'r') as f:
    pokedex = f.read().split('\n')

# Pokemons you want to look out for
with open('want.txt', 'r') as f:
    want_pk = f.read().split('\n')

want_pk_ids = [pokedex.index(i) + 1 for i in want_pk]
mons_list = str(want_pk_ids)[1:-1].replace(" ", "")

headers = {
    'accept-encoding': 'gzip, deflate, sdch, br',
    'x-requested-with': 'XMLHttpRequest',
    'accept-language': 'en-US,en;q=0.8',
    'accept': '*/*',
    'referer': 'https://sgpokemap.com/',
    'authority': 'sgpokemap.com',
}


def haversine(poke1_latlon, poke2_latlon):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lat1, lon1 = poke1_latlon
    lat2, lon2 = poke2_latlon
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    km = 6367 * c
    return km


def get_latlong(pokemon):
    lat = float(pokemon['lat'])
    lon = float(pokemon['lng'])
    return lat, lon


def get_location(address):
    # Get lat long of current location
    if len(address) == 11:
        ekey = requests.get("https://plus.codes/api?encryptkey=" + geocode_api_key).json()['key']
        geocode = requests.get("https://plus.codes/api?address=" + address.replace(
            "+", "%2B") + "&ekey=" + ekey).json()['plus_code']
        formatted_address = geocode["best_street_address"]
        location = geocode["geometry"]["location"]
        geocode_latlon = (location["lat"], location["lng"])
        # print "Location set as: {}".format(formatted_address)

    else:
        request_address = address.replace(" ", "+")
        geocode_params = (
            ('address', request_address),
            ('key', geocode_api_key)
        )

        geocode = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json', params=geocode_params
        ).json()["results"][0]
        location = geocode["geometry"]["location"]
        geocode_latlon = (location["lat"], location["lng"])
        formatted_address = geocode["formatted_address"]
        # print "Location set as: {}".format(formatted_address)

    return geocode_latlon, formatted_address


def get_pokemons(geocode_latlon, radius_in_km, filter_iv=None, since=None):
    if since:
        params = (
            ('since', since),
            ('mons', mons_list),
        )
    else:
        params = (
            ('since', '0'),
            ('mons', mons_list),
        )

    results = requests.get(
        'https://sgpokemap.com/query2.php',
        headers=headers, params=params).json()

    pokemons = results['pokemons']
    since = results['meta']

    # Set radius in km
    pokemon_within_radius = []

    # Filter for pokemons within radius
    for pokemon in pokemons:
        poke_latlon = get_latlong(pokemon)
        pokemon['km_from_location'] = haversine(geocode_latlon, poke_latlon)
        if pokemon['km_from_location'] < radius_in_km:
            # Get pokemon name
            pokemon['name'] = pokedex[int(pokemon['pokemon_id']) - 1]
            # Get time left before despawn
            time_left = datetime.fromtimestamp(int(pokemon["despawn"])) - datetime.now()
            minutes, seconds = divmod(time_left.seconds, 60)
            pokemon['time_left_secs'] = "{:<2} mins {:<2} sec".format(minutes, seconds)
            # Get pokemon IV percentage
            stats = ["attack", "defence", "stamina"]
            pokemon['iv'] = int(sum([int(pokemon[stat]) for stat in stats]) / 45.0 * 100)

            pokemon_within_radius += [pokemon]

    # Filter for pokemons greater than filtered IV
    if filter_iv:
        pokemons_filtered = []
        for pokemon in pokemon_within_radius:
            if pokemon['iv'] >= int(filter_iv):
                pokemons_filtered += [pokemon]
    else:
        pokemons_filtered = pokemon_within_radius

    # Sort by distance from location
    sorted_pokemon_within_radius = sorted(pokemons_filtered, key=lambda k: k['km_from_location']) 

    return sorted_pokemon_within_radius, since["inserted"]


if __name__ == "__main__":
    address = "farrer park mrt"
    radius_in_km = 2
    geocode_latlon, formatted_address = get_location(address)
    # address = "6PH58V74+G3"
    sorted_pokemon_within_radius, since = get_pokemon_within_radius(
        geocode_latlon, radius_in_km, filter_iv=70)
