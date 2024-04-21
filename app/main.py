from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel
from typing import List
from process import get_geocode, get_distance_matrix
from optimization import solve_vrp
from mangum import Mangum
from dotenv import load_dotenv
import numpy as np
import os


class Location(BaseModel):
    name: str
    uuid: int
    # coord array or string address
    address: List


class Locations(BaseModel):
    locations: List[Location]
    max_sizes: List[int]
    startIndex: int
    endIndex: int
    token: str


app = FastAPI()
handler = Mangum(app)
load_dotenv()


@app.post("/route-optimization/")
async def cluster_locations(response: Response, locations: Locations):
    # check if token is valid
    if locations.token != os.getenv("API_KEY"):
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"error": "Invalid token"}

    # temporarily convert coordinates to string for numpy processing
    addresses = []
    for location in locations.locations:
        if len(location.address) == 2:
            addresses.append(
                ",".join(str(coord) for coord in location.address) + "coord"
            )
        else:
            addresses.append(location.address[0])
    # convert location array into unique list with another list for frequency
    unique_locations, counts = np.unique(addresses, return_counts=True)
    unique_locations = unique_locations.tolist()
    counts = counts.tolist()
    # convert back to float array
    for i in range(len(unique_locations)):
        if "coord" in unique_locations[i]:
            # remove coord
            unique_locations[i] = unique_locations[i][:-5]
            unique_locations[i] = [
                float(coord) for coord in unique_locations[i].split(",")
            ]
        else:
            unique_locations[i] = [unique_locations[i]]

    # get geocode, list of locations using list comprehension
    geocodes = get_geocode(unique_locations)
    # if coordinates not found, return 500 with index of failed
    if None in geocodes["lon"]:  # type: ignore
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "error": "Geocode not found",
            "unique_locations": unique_locations,
            "geocodes": geocodes,
        }
    # get coord 2d array from geocode
    coords = [
        [geocodes["lat"][i], geocodes["lon"][i]]  # type: ignore
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
        locations.startIndex = len(distance_mat) - 1
        counts.append(0)
    if locations.endIndex == -1:
        distance_mat = np.insert(distance_mat, len(distance_mat), 0, axis=0)
        locations.endIndex = len(distance_mat) - 1
        counts.append(0)

    solution = solve_vrp(
        distance_mat.tolist(),  # type: ignore
        locations.startIndex,
        locations.endIndex,
        locations.max_sizes,
        counts,
    )

    return solution
