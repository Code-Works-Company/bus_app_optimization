from typing import List
import nominatim.api as napi
import numpy as np
import asyncio
import osrm

py_osrm = osrm.OSRM("/osrm-data")


async def search(query):
    api = napi.NominatimAPIAsync(Path("."))
    return await api.search(query)


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
        response = asyncio.run(search(i[0] + ", Hanoi"))
        print(response, flush=True)
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

    table_params = osrm.TableParameters(
        coordinates=coords,
        annotations=["duration"],
    )
    response = py_osrm.Table(table_params)

    response_dict = response.json()
    if response_dict["code"] != "Ok":
        return []
    # get distance matrix
    distance_mat = np.array(response_dict["durations"])
    return distance_mat.tolist()
