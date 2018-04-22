"""`Simulation` represents an airport simulation of a day on the given
parameters. `SimulationDelegate` is designed to be an immutable delegate of a
simultion that can be used for other objects to observe the simulation states.
"""
import time
import logging
import traceback
import importlib

from copy import deepcopy
from collections import deque
from clock import Clock, ClockException
from airport import AirportFactory
from scenario import ScenarioFactory
from routing_expert import RoutingExpert
from analyst import Analyst
from utils import get_seconds_after
from uncertainty import Uncertainty
from config import Config
from state_logger import StateLogger
from itinerary import CompletedItinerary


"""Simulation represents a simulation day, holds both static and dynamic states
of the current airport, and implements `tick()` and `quiet_tick()` functions
for the caller to simulation to the next state.
"""
class Simulation:

    def __init__(self):

        params = Config.params

        # Setups the logger
        self.logger = logging.getLogger(__name__)

        # Setups the clock
        self.clock = Clock()

        # Sets up the airport
        airport_name = params["airport"]
        self.airport = AirportFactory.create(airport_name)

        # Sets up the scenario
        self.scenario = ScenarioFactory.create(
            airport_name, self.airport.surface)

        # Sets up the routing expert monitoring the airport surface
        self.routing_expert = RoutingExpert(self.airport.surface.links,
                                            self.airport.surface.nodes,
                                            params["simulation"]["cache"])

        # Sets up the uncertainty module
        self.uncertainty = (Uncertainty(params["uncertainty"]["prob_hold"])
                            if params["uncertainty"]["enabled"] else (None))

        # Loads the requested scheduler
        self.scheduler = get_scheduler()

        if not params["simulator"]["test_mode"]:

            # Sets up the analyst
            self.analyst = Analyst(self)

            # Sets up the state logger
            self.state_logger = StateLogger()

        # Sets up a delegate of this simulation
        self.delegate = SimulationDelegate(self)

        # Initializes the previous schedule time
        self.last_schedule_time = None

        # Initializes the last execution time for rescheduling to None
        self.last_schedule_exec_time = None

        # Initializes the completed itinerary array
        self.completed_itineraries = []

        self.__print_stats()

    def tick(self):

        self.logger.debug("\nCurrent Time: %s" % self.now)

        try:
            # Reschedule happens before the tick
            if self.__is_time_to_reschedule():
                self.logger.info("Time to reschedule")
                start = time.time()
                self.__reschedule()
                self.last_schedule_exec_time = time.time() - start  # seconds
                self.last_schedule_time = self.now
                self.logger.info("Last schedule time is updated to %s" %
                                 self.last_schedule_time)

            # Injects uncertainties
            if self.uncertainty:
                self.uncertainty.inject(self)

            # Tick
            self.__add_aircrafts()
            self.airport.tick()
            if not Config.params["simulator"]["test_mode"]:
                self.state_logger.log_on_tick(self.delegate)
            self.__remove_aircrafts()
            self.clock.tick()

            # Abort on conflict
            if len(self.airport.conflicts) > 0:
                raise SimulationException("Conflict found")

            # Observe
            if not Config.params["simulator"]["test_mode"]:
                self.analyst.observe_on_tick(self.delegate)

        except ClockException as e:
            # Finishes
            if not Config.params["simulator"]["test_mode"]:
                self.analyst.save()
                self.state_logger.save()
            raise e
        except SimulationException as e:
            raise e
        except Exception as e:
            self.logger.error(traceback.format_exc())
            raise e

    def quiet_tick(self):
        """
        Turn off the logger, reschedule, and analyst.
        """
        self.logger.debug("\nPredicted Time: %s" % self.now)
        self.__add_aircrafts()
        self.airport.tick()
        self.__remove_aircrafts()
        try:
            self.clock.tick()
        except ClockException as e:
            raise e

    def __is_time_to_reschedule(self):
        reschedule_cycle = Config.params["simulation"]["reschedule_cycle"]
        last_time = self.last_schedule_time
        next_time = (get_seconds_after(last_time, reschedule_cycle)
                     if last_time is not None else None)
        return last_time is None or next_time <= self.now

    def __reschedule(self):
        schedule = self.scheduler.schedule(self.delegate)
        self.airport.apply_schedule(schedule)
        if not Config.params["simulator"]["test_mode"]:
            self.analyst.observe_on_reschedule(schedule, self.delegate)

    def __add_aircrafts(self):
        self.__add_aircrafts_from_queue()
        self.__add_aircrafts_from_scenario()

    def __add_aircrafts_from_queue(self):

        for gate, queue in self.airport.gate_queue.items():

            if self.airport.is_occupied_at(gate) or len(queue) == 0:
                continue

            # Put the first aircraft in queue into the airport
            aircraft = queue.popleft()
            aircraft.set_location(gate)
            self.airport.add_aircraft(aircraft)

    def __add_aircrafts_from_scenario(self):

        # NOTE: we will only focus on departures now
        next_tick_time = get_seconds_after(self.now, self.clock.sim_time)

        # For all departure flights
        for flight in self.scenario.departures:

            # Only if the scheduled appear time is between now and next tick
            if not (self.now <= flight.appear_time and
                    flight.appear_time < next_tick_time):
                continue

            gate, aircraft = flight.from_gate, flight.aircraft

            if self.airport.is_occupied_at(gate):
                # Adds the flight to queue
                queue = self.airport.gate_queue.get(gate, deque())
                queue.append(aircraft)
                self.airport.gate_queue[gate] = queue
                self.logger.info("Adds %s into gate queue" % flight)

            else:
                # Adds the flight to the airport
                aircraft.set_location(gate)
                self.airport.add_aircraft(aircraft)
                self.logger.info("Adds %s into the airport" % flight)

    def __remove_aircrafts(self):
        """
        Removes departure aircrafts if they've moved to the runway.
        """
        # TODO: removal for arrival aircrafts

        to_remove_aircrafts = []

        for aircraft in self.airport.aircrafts:
            flight = self.scenario.get_flight(aircraft)
            # Deletion shouldn't be done in the fly
            if aircraft.location.is_close_to(flight.runway.start):
                to_remove_aircrafts.append(aircraft)

        for aircraft in to_remove_aircrafts:
            self.logger.info("Removes %s from the airport" % aircraft)
            self.completed_itineraries.append(
                CompletedItinerary(
                    self.scenario.get_flight(aircraft).appear_time,
                    self.now, aircraft.itinerary)
            )
            self.airport.remove_aircraft(aircraft)

    @property
    def now(self):
        return self.clock.now

    def __print_stats(self):
        self.scenario.print_stats()
        self.airport.print_stats()

    def __getstate__(self):
        __dict = dict(self.__dict__)
        del __dict["logger"]
        __dict["uncertainty"] = None
        return __dict

    def __setstate__(self, new_dict):
        self.__dict__.update(new_dict)

    def set_quiet(self, logger):
        self.logger = logger
        self.airport.set_quiet(logger)
        self.scenario.set_quiet(logger)
        self.routing_expert.set_quiet(logger)


class SimulationDelegate:
    """
    SimulationDelegate is used for scheduler to access simulation state without
    breaking on-going things or creating deadlocks.
    """

    def __init__(self, simulation):
        self.simulation = simulation

    @property
    def now(self):
        return self.simulation.now

    @property
    def airport(self):
        # TODO: should make it immutable before returning the airport state
        return self.simulation.airport

    @property
    def scenario(self):
        return self.simulation.scenario

    @property
    def routing_expert(self):
        return self.simulation.routing_expert

    @property
    def last_schedule_exec_time(self):
        return self.simulation.last_schedule_exec_time

    @property
    def completed_itineraries(self):
        return self.simulation.completed_itineraries

    @property
    def copy(self, uncertainty=None):

        # Gets a snapshot of current simulation state
        simulation_copy = deepcopy(self.simulation)

        # Replace the uncertainty module by the given one
        simulation_copy.uncertainty = uncertainty

        # Sets the simulation to quiet mode
        simulation_copy.set_quiet(logging.getLogger("QUIET_MODE"))

        return simulation_copy


class PredictSimulation():

    def __init__(self, simulation, uncertainty):
        pass


def get_scheduler():
    # Loads the requested scheduler
    scheduler_name = Config.params["scheduler"]["name"]
    return importlib.import_module("scheduler." + scheduler_name).Scheduler()


class SimulationException(Exception):
    pass
