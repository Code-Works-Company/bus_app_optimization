from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp


class Route:
    def __init__(
        self,
        distance_matrix,
        start_index,
        end_index,
        available_vehicle_sizes,
        forced_bus_overflow,
        demands,
    ):
        self.distance_matrix = distance_matrix
        self.demands = demands
        self.available_vehicle_sizes = available_vehicle_sizes
        self.forced_bus_overflow = forced_bus_overflow
        self.vehicle_capacities = self.calculate_vehicle_capacity(
            available_vehicle_sizes, forced_bus_overflow
        )
        self.num_vehicles = len(self.vehicle_capacities)
        self.start = [start_index] * self.num_vehicles
        self.end = [end_index] * self.num_vehicles
        self.manager = pywrapcp.RoutingIndexManager(
            len(self.distance_matrix), self.num_vehicles, self.start, self.end
        )
        self.routing = pywrapcp.RoutingModel(self.manager)
        self.transit_callback_index = self.routing.RegisterTransitCallback(
            self.distance_callback
        )
        self.routing.SetArcCostEvaluatorOfAllVehicles(self.transit_callback_index)
        self.demand_callback_index = self.routing.RegisterUnaryTransitCallback(
            self.demand_callback
        )
        self.routing.AddDimensionWithVehicleCapacity(
            self.demand_callback_index,
            0,  # null capacity slack
            self.vehicle_capacities,  # vehicle maximum capacities
            True,  # start cumul to zero
            "Capacity",
        )
        self.search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        self.search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        self.search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        self.search_parameters.time_limit.seconds = 5

    def calculate_vehicle_capacity(self, vehicle_capacities, forced_bus_overflow):
        # sort vehicle capacities and get total number of vehicles
        data = []
        vehicle_capacities = sorted(vehicle_capacities)
        total_student = sum(self.demands)
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
                data.append(size)
                total_student -= size
        return data

    def distance_callback(self, from_index, to_index):
        from_node = self.manager.IndexToNode(from_index)
        to_node = self.manager.IndexToNode(to_index)
        return self.distance_matrix[from_node][to_node]

    def demand_callback(self, from_index):
        from_node = self.manager.IndexToNode(from_index)
        return self.demands[from_node]

    def process_solution(self, solution) -> list:
        """
        process the solution into a 2d array of routes
        each array representing a bus
        """
        routes = []
        for vehicle_id in range(self.num_vehicles):
            index = self.routing.Start(vehicle_id)
            route = []
            while not self.routing.IsEnd(index):
                node_index = self.manager.IndexToNode(index)
                route.append(node_index)
                index = solution.Value(self.routing.NextVar(index))
            node_index = self.manager.IndexToNode(index)
            route.append(node_index)
            routes.append(route)
        return routes

    def solve_vrp(self) -> list:
        solution = self.routing.SolveWithParameters(self.search_parameters)
        if solution:
            return self.process_solution(solution)
        else:
            # recall constructor with incremented forced_bus_overflow and retry
            self = Route(
                self.distance_matrix,
                self.start,
                self.end,
                self.available_vehicle_sizes,
                self.forced_bus_overflow + 1,
                self.demands,
            )
            return self.solve_vrp()
