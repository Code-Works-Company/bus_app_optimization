from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


def create_data_model(
    distance_matrix,
    start_index,
    end_index,
    vehicle_capacities,
    forced_bus_overflow,
    demands,
):
    data = {}
    data["distance_matrix"] = distance_matrix
    data["vehicle_capacities"] = []

    # sort vehicle capacities and get total number of vehicles
    vehicle_capacities = sorted(vehicle_capacities)
    total_student = sum(demands)
    while forced_bus_overflow > 0:
        if len(vehicle_capacities) < forced_bus_overflow:
            total_student = vehicle_capacities[-1]
            forced_bus_overflow -= len(vehicle_capacities)
        else:
            total_student += vehicle_capacities[forced_bus_overflow - 1]
            forced_bus_overflow = 0

    while True:
        # find vehicle capacity where total_student is greater than vehicle capacity
        size = 0
        for i in range(len(vehicle_capacities)):
            if total_student > vehicle_capacities[i]:
                size = vehicle_capacities[i]
            else:
                continue
        if size == 0:
            # it should be handled by the forced_bus_overflow so don't increment
            break
        else:
            data["vehicle_capacities"].append(size)
            total_student -= size

    data["num_vehicles"] = len(data["vehicle_capacities"])
    data["start"] = [start_index] * data["num_vehicles"]
    data["end"] = [end_index] * data["num_vehicles"]
    data["demands"] = demands
    # specific end point

    # attempted patch fix
    # increment vehicle capacities by one
    data["vehicle_capacities"] = [i + 1 for i in data["vehicle_capacities"]]

    return data


def get_routes(routing, manager, solution):
    """Extracts the routes from the solution and returns them as a 2D array."""
    # Number of vehicles in the problem.
    num_vehicles = routing.vehicles()
    # Initialize the 2D array to store the routes.
    routes = []

    for vehicle_id in range(num_vehicles):
        # Initialize the route for the current vehicle.
        route = []
        # Get the index of the start node for the current vehicle.
        index = routing.Start(vehicle_id)
        # While the current index is not the end node for the current vehicle.
        while not routing.IsEnd(index):
            # Convert the index to the node index in the data model.
            node_index = manager.IndexToNode(index)
            # Add the node index to the route.
            route.append(node_index)
            # Get the next index in the route.
            # TODO: Crashes here sometimes, no idea the conditions
            index = solution.Value(routing.NextVar(index))
        # Convert the end index to the node index in the data model.
        node_index = manager.IndexToNode(index)
        # Add the end node index to the route.
        route.append(node_index)
        # Add the route to the routes list.
        routes.append(route)

    return routes


def solve_vrp(
    distance_matrix,
    start_index,
    end_index,
    vehicle_capacities,
    demands,
    forced_bus_overflow=1,
):
    data = create_data_model(
        distance_matrix,
        start_index,
        end_index,
        vehicle_capacities,
        forced_bus_overflow,
        demands,
    )
    # print(data, flush=True)
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["start"], data["end"]
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # capacity constraint and variable end/start point
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index, 0, data["vehicle_capacities"], True, "Capacity"
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 15

    solution = routing.SolveWithParameters(search_parameters)

    # recursive function until solution is found
    # TODO: time condition
    if solution is None:
        solve_vrp(
            distance_matrix,
            start_index,
            end_index,
            vehicle_capacities,
            demands,
            forced_bus_overflow + 1,
        )

    return get_routes(routing, manager, solution)
