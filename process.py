from typing import List
from OSMPythonTools.nominatim import Nominatim
import numpy as np
import requests

nominatim = Nominatim()

# osrm_url = "http://100.78.114.117:5000/table/v1/driving/"
# just for testing
osrm_url = "http://router.project-osrm.org/table/v1/driving/"


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
        # call nomantim api
        # if type is a list its a coordinate so no need to process
        if len(i) == 2:
            r_dict["lon"].append(i[1])
            r_dict["lat"].append(i[0])
            r_dict["osm_id"].append(None)
            r_dict["display_name"].append(None)
            continue
        print(i, flush=True)
        response = nominatim.query(i[0] + ", Hanoi")
        response_dict = response.toJSON()  # type: ignore
        if response_dict == []:
            r_dict["lon"].append(None)
            r_dict["lat"].append(None)
            r_dict["osm_id"].append(None)
            r_dict["display_name"].append(None)
        else:
            response_dict = response_dict[0]
            r_dict["lon"].append(response_dict["lon"])
            r_dict["lat"].append(response_dict["lat"])
            r_dict["osm_id"].append(response_dict["osm_id"])
            r_dict["display_name"].append(response_dict["display_name"])
    return r_dict  # type: ignore


def get_distance_matrix(coords: List) -> List:
    # osrm
    # table distance matrix using duration
    full_url = (
        osrm_url
        + ";".join([str(i[1]) + "," + str(i[0]) for i in coords])
        + "?annotations=duration"
    )
    response = requests.get(full_url)
    response_dict = response.json()
    if response_dict["code"] != "Ok":
        return []
    # get distance matrix
    distance_mat = np.array(response_dict["durations"])
    return distance_mat.tolist()
