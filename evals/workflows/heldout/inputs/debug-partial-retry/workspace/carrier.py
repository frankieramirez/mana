"""Deterministic carrier double used by the local checks.

Each create_label call consumes the next scheduled outcome: "ok" returns a
label, "timeout" raises TransientCarrierError, "reject" raises
CarrierRejected. A call beyond the end of the schedule is an error in the
caller, so it raises instead of inventing an outcome.
"""
from shipping import CarrierRejected, TransientCarrierError


class ScheduledCarrier:
    def __init__(self, schedule):
        self.schedule = list(schedule)
        self.calls = []

    def create_label(self, order_id):
        self.calls.append(order_id)
        if not self.schedule:
            raise AssertionError("carrier called more often than scheduled")
        outcome = self.schedule.pop(0)
        if outcome == "timeout":
            raise TransientCarrierError(order_id)
        if outcome == "reject":
            raise CarrierRejected(order_id)
        if outcome != "ok":
            raise AssertionError("unknown scheduled outcome " + outcome)
        return "LBL-" + order_id + "-" + str(len(self.calls))
