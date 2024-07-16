from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from valhalla import Actor, get_config, get_help
from urllib import parse
from app.route import Route
import requests
import numpy as np
import os


class Student(BaseModel):
    name: str
    uuid: int
    # coord array or string address
    address: list


class Locations(BaseModel):
    locations: list[Student]
    max_sizes: list[int]
    startIndex: int
    endIndex: int


class ProcessData:
    _config = get_config(
        os.environ.get("VALHALLA_DIR", "./custom_files/valhalla_tiles.tar")
    )
    _actor = Actor(config=_config)
    _photon_url = "http://localhost:2322/api/?q="

    def __init__(self):
        self.router = APIRouter()
        self.router.add_api_route(
            "/route-optimization", self.process_data, methods=["POST"]
        )

    def process_data(self, response: Response, locations: Locations):
        # print into json for debug
        print(locations.model_dump_json())
        # Process the data
        # convert into unique location and counts
        if locations.startIndex == -1 and locations.endIndex == -1:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                "error": "Need to specify either/both start and end index",
            }

        unique_locations, counts = self.get_unique_locations(
            locations.locations, locations.startIndex, locations.endIndex
        )

        # get geocode
        geocodes = self.get_geocodes(unique_locations)
        # if coordinates not found, return 206 with index of failed
        if None in geocodes["lon"]:  # type: ignore
            response.status_code = status.HTTP_206_PARTIAL_CONTENT
            return {
                "error": "Geocode not found",
                "unique_locations": unique_locations,
                "geocodes": geocodes,
            }
        # get coord 2d array from geocode
        coords = [
            (geocodes["lat"][i], geocodes["lon"][i])  # type: ignore
            for i in range(len(geocodes["lon"]))  # type: ignore
        ]
        # get distance matrix
        distance_matrix = self.get_distance_matrix(coords)

        arbitraryEndpoint = False
        arbitraryStartpoint = False
        if locations.startIndex == -1:
            # place zeros to make it a square matrix
            distance_matrix = np.pad(distance_matrix, ((0, 1), (0, 1)), "constant")
            locations.startIndex = len(distance_matrix) - 1
            counts.append(0)
            arbitraryEndpoint = True
        elif locations.endIndex == -1:
            distance_matrix = np.pad(distance_matrix, ((0, 1), (0, 1)), "constant")
            locations.endIndex = len(distance_matrix) - 1
            counts.append(0)
            arbitraryStartpoint = True

        route = Route(
            distance_matrix=distance_matrix,
            start_index=locations.startIndex,
            end_index=locations.endIndex,
            available_vehicle_sizes=locations.max_sizes,
            forced_bus_overflow=1,
            demands=counts,
        )
        routes = route.solve_vrp()
        # TODO: 99% sure the error is here
        # only when end point so likely caused by popping the wrong thing
        if arbitraryStartpoint:
            for i in range(len(routes)):
                routes[i].pop()
        elif arbitraryEndpoint:
            for i in range(len(routes)):
                routes[i].pop(0)
        response_dict = self.construct_response(
            routes,
            geocodes,
            counts,
            distance_matrix,  # type: ignore
        )
        return response_dict

    def construct_response(
        self,
        solution: list,
        geocodes: dict,
        counts: list,
        distance_mat: np.ndarray,
    ):
        # return format
        r_dict = {
            "buses": [],
        }
        busIndex = 1
        for locationOrder in solution:
            # build dict with lat and long key for get_polyline_route
            route_coords = []
            for i in locationOrder:
                route_coords.append(
                    {
                        "lat": geocodes["lat"][i],  # type: ignore
                        "lon": geocodes["lon"][i],  # type: ignore
                    }
                )  # type: ignore
            bus = {
                "number": busIndex,
                "polyline": self.get_polyline_route(route_coords),
                "numStudents": 0,
                "locations": [],
            }
            prevLocation = None
            busIndex += 1

            order = 1
            for location in locationOrder:
                bus["numStudents"] += counts[location]
                # find estTime, if its the first location, its 0
                if prevLocation is None:
                    estTime = 0
                    prevLocation = location
                else:
                    estTime = int(distance_mat[prevLocation][location])
                    order += 1
                    prevLocation = location
                bus["locations"].append(
                    {
                        "address": geocodes["display_name"][location],  # type: ignore
                        "osm_id": geocodes["osm_id"][location],  # type: ignore
                        "coords": {
                            "lat": geocodes["lat"][location],  # type: ignore
                            "lon": geocodes["lon"][location],  # type: ignore
                        },
                        # "students": [],  # TODO
                        "estTime": estTime,
                        "order": order,
                    }
                )
            r_dict["buses"].append(bus)
        return r_dict

    def get_polyline_route(self, coords: list) -> str:
        request_dict = {
            "locations": [
                {"lat": coord["lat"], "lon": coord["lon"], "type": "through"}
                for coord in coords
            ],
            "costing": "bus",
        }
        # replace first and last locations with "break"
        request_dict["locations"][0]["type"] = "break"
        request_dict["locations"][-1]["type"] = "break"
        # TODO: not very coordinated with route optim
        route = self._actor.route(request_dict)
        return route["trip"]["legs"][0]["shape"]  # type: ignore

    def get_distance_matrix(self, coords: list[tuple[float, float]]):
        # table distance matrix using duration
        request_dict = {
            "sources": [{"lat": coord[0], "lon": coord[1]} for coord in coords],
            "targets": [{"lat": coord[0], "lon": coord[1]} for coord in coords],
            "costing": "bus",
        }
        response_dict = self._actor.matrix(request_dict)
        # build distance matrix from "source_to_target" key, which has "time" key
        distance_matrix = []
        for source in response_dict["sources_to_targets"]:
            row = []
            for target in source:
                row.append(target["time"])
            distance_matrix.append(row)
        return distance_matrix  # type: ignore

    def get_geocodes(self, addresses: list[str]):
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
            response = requests.get(
                self._photon_url + parse.quote(i[0]) + "&limit=1"
            ).json()
            # lon, lat, osm_id, display_name
            # if no result found, append None, try first
            try:
                r_dict["lon"].append(
                    response["features"][0]["geometry"]["coordinates"][0]
                )
                r_dict["lat"].append(
                    response["features"][0]["geometry"]["coordinates"][1]
                )
                r_dict["osm_id"].append(response["features"][0]["properties"]["osm_id"])
                r_dict["display_name"].append(
                    response["features"][0]["properties"]["name"]
                )
            except IndexError:
                r_dict["lon"].append(None)
                r_dict["lat"].append(None)
                r_dict["osm_id"].append(None)
                r_dict["display_name"].append(None)
        return r_dict  # type: ignore

    def get_unique_locations(
        self, locations: list[Student], startIndex: int, endIndex: int
    ):
        addresses = []
        for location in locations:
            if len(location.address) == 2:
                addresses.append([location.address[0], location.address[1], 0])
            else:
                addresses.append([location.address[0], 0, 1])
        unique_locations, counts = np.unique(addresses, return_counts=True, axis=0)
        unique_locations = unique_locations.tolist()
        counts = counts.tolist()
        for i in range(len(unique_locations)):
            if unique_locations[i][2] == "0":
                unique_locations[i] = [unique_locations[i][0], unique_locations[i][1]]
            else:
                unique_locations[i] = [unique_locations[i][0]]
            # find and decrement start and end index by 1
            if startIndex != -1:
                if unique_locations[i] == [
                    str(i) for i in locations[startIndex].address
                ]:
                    counts[i] -= 1
            if endIndex != -1:
                if unique_locations[i] == [
                    str(i) for i in locations[startIndex].address
                ]:
                    counts[i] -= 1
        return unique_locations, counts
