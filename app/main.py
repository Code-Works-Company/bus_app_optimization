import os
from typing import List

import numpy as np
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.optimization import solve_vrp
from app.process import (
    get_distance_matrix,
    get_geocode,
    get_polyline_route,
    get_unique_locations,
)


class Student(BaseModel):
    name: str
    uuid: int
    # coord array or string address
    address: List


class Locations(BaseModel):
    locations: List[Student]
    max_sizes: List[int]
    startIndex: int
    endIndex: int


app = FastAPI()
load_dotenv()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.post("/route-optimization")
async def cluster_locations(response: Response, locations: Locations):
    unique_locations, counts = get_unique_locations(locations)
    # get geocode, list of locations using list comprehension
    geocodes = get_geocode(unique_locations)

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
    distance_mat = get_distance_matrix(coords)
    # solve vrp
    if locations.startIndex == -1 and locations.endIndex == -1:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "error": "Need to specify either/both start and end index",
        }

    if locations.startIndex == -1:
        distance_mat = np.insert(distance_mat, len(distance_mat), 0, axis=0)
        startIndex = len(distance_mat) - 1
        endIndex = locations.endIndex
        counts.append(0)
    if locations.endIndex == -1:
        distance_mat = np.insert(distance_mat, len(distance_mat), 0, axis=0)
        endIndex = len(distance_mat) - 1
        startIndex = locations.startIndex
        counts.append(0)
    else:
        startIndex = locations.startIndex
        endIndex = locations.endIndex

    solution = solve_vrp(
        distance_mat.tolist(),  # type: ignore
        startIndex,
        endIndex,
        locations.max_sizes,
        counts,
    )
    # if start and end index was added remove the last location
    if locations.startIndex == -1 or locations.endIndex == -1:
        for i in range(len(solution)):
            solution[i].remove(len(solution[i]) - 1)

    # TODO polylines
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
            "polyline": get_polyline_route(route_coords),
            "numStudents": 0,
            "locations": [],
        }
        prevLocation = None
        busIndex += 1

        order = 1
        print(geocodes, flush=True)
        # TODO: test if order works correctly
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
            print(location, flush=True)
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

    print(r_dict)
    return r_dict


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
