from aircraft import Aircraft, State

class Flight:

    def __init__():
        self.aircraft = None

class ArrivalFlight(Flight):

    def __init__(self, callsign, model, from_airport, to_gate, spot, runway, 
                 arrival_time, appear_time):

        self.aircraft = Aircraft(callsign, model, State.scheduled, None)
        self.from_airport = from_airport
        self.to_gate = to_gate
        self.spot = spot
        self.runway = runway
        self.arrival_time = arrival_time
        self.appear_time = appear_time

    def __repr__(self):
        return "<Arrival:%s runway:%s spot:%s gate:%s time:%s appear:%s>"\
                % (self.aircraft.callsign, self.runway, self.spot, self.to_gate,
                   self.arrival_time, self.appear_time)

class DepartureFlight(Flight):

    def __init__(self, callsign, model, to_airport, from_gate, spot, runway,
                 departure_time, appear_time):
        self.aircraft = Aircraft(callsign, model, State.scheduled, None)
        self.to_airport = to_airport
        self.from_gate = from_gate
        self.spot = spot
        self.runway = runway
        self.departure_time = departure_time
        self.appear_time = appear_time

    def __repr__(self):
        return "<Departure:%s gate:%s spot:%s runway:%s time:%s appear:%s>"\
                % (self.aircraft.callsign, self.from_gate, self.spot,
                   self.runway, self.departure_time, self.appear_time)
