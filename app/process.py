from typing import List
import numpy as np
from valhalla import Actor, get_config, get_help
import requests
from urllib import parse

config = get_config(tile_extract='/custom_files/valhalla_tiles.tar', verbose=True)
actor = Actor(config)
photon_url = "http://localhost:2322/api/?q="

def get_routes_as_2d_array(routing, solution):
    """Returns the routes as a 2D array, where each array represents a bus."""
    num_vehicles = routing.vehicles()

    routes = []

    for vehicle_id in range(num_vehicles):
        route = []

        index = routing.Start(vehicle_id)

        while not routing.IsEnd(index):
            node_index = routing.IndexToNode(index)
            route.append(node_index)

            index = solution.Value(routing.NextVar(index))

        routes.append(route)

    return routes


# take string array
def get_geocode(addresses: List) -> List:
    r_dict = {
        "lon": [],
        "lat": [],
        "osm_id": [],
        "display_name": [],
    }
    for i in addresses:
        # call photon api
        # if type is a list its a coordinate so no need to process
        if len(i) == 2:
            r_dict["lon"].append(i[1])
            r_dict["lat"].append(i[0])
            r_dict["osm_id"].append(None)
            r_dict["display_name"].append(None)
            continue
        response = requests.get(photon_url + parse.quote(i[0]) + "&limit=1").json()
        # lon, lat, osm_id, display_name
        # if no result found, append None, try first
        try:
            r_dict["lon"].append(response["features"][0]["geometry"]["coordinates"][0])
            r_dict["lat"].append(response["features"][0]["geometry"]["coordinates"][1])
            r_dict["osm_id"].append(response["features"][0]["properties"]["osm_id"])
            r_dict["display_name"].append(response["features"][0]["properties"]["name"])
        except:
            r_dict["lon"].append(None)
            r_dict["lat"].append(None)
            r_dict["osm_id"].append(None)
            r_dict["display_name"].append(None)
    return r_dict  # type: ignore


def get_distance_matrix(coords: List) -> List:
    # osrm
    # table distance matrix using duration
    request_dict = {
        "sources": [ {"lat": coord[0], "lon": coord[1]} for coord in coords],
        "targets": [ {"lat": coord[0], "lon": coord[1]} for coord in coords],
        "costing": "bus",
    }
    response_dict = actor.matrix(request_dict)
    print(response_dict, flush=True)
    # build distance matrix from "source_to_target" key, which has "time" key
    distance_matrix = []
    for source in response_dict["sources_to_targets"]:
        row = []
        for target in source:
            row.append(target["time"])
        distance_matrix.append(row)
    return distance_matrix  # type: ignore
    

def get_polyline_route(coords: List) -> str:
    request_dict = {
        "locations": [{"lat": coord["lat"], "lon": coord["lon"]} for coord in coords],
        "costing": "bus"
    }

    route = actor.route(request_dict)
    print(route, flush=True)
    return route["trip"]["legs"][0]["shape"]  # type: ignore
