"""Integration tests — full stack against a real MySQL test database."""

import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
class TestVehicles:
    def test_create_vehicle(self, client):
        resp = client.post("/vehicles", json={
            "type": "SEDAN",
            "capacity": 4,
            "plate_number": "ABC-123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "SEDAN"
        assert data["status"] == "AVAILABLE"


@pytest.mark.integration
class TestAvailability:
    def _create_vehicle(self, client, plate="V-001", capacity=4, type_="SEDAN"):
        return client.post("/vehicles", json={
            "type": type_,
            "capacity": capacity,
            "plate_number": plate,
        }).json()

    def _create_transfer(self, client, vehicle_id, pickup_time, pax_count=2):
        return client.post("/transfers", json={
            "vehicle_id": vehicle_id,
            "passenger_name": "Test",
            "flight_number": "AA100",
            "pickup_time": pickup_time.isoformat(),
            "pickup_location": "Airport",
            "dropoff_location": "Hotel",
            "pax_count": pax_count,
        }).json()

    def test_vehicle_available_no_transfers(self, client):
        v = self._create_vehicle(client)
        resp = client.get("/availability", params={"date": "2026-06-15", "pax_count": 2})
        assert resp.status_code == 200
        ids = [x["id"] for x in resp.json()]
        assert v["id"] in ids

    def test_vehicle_unavailable_when_confirmed_overlap(self, client):
        v = self._create_vehicle(client)
        pickup = datetime(2026, 6, 15, 10, 0)
        t = self._create_transfer(client, v["id"], pickup)
        # Confirm the transfer
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})

        # Check availability at same time
        resp = client.get("/availability", params={
            "date": "2026-06-15",
            "pax_count": 2,
            "pickup_time": pickup.isoformat(),
        })
        ids = [x["id"] for x in resp.json()]
        assert v["id"] not in ids

    def test_vehicle_available_when_pending_only(self, client):
        """PENDING transfers don't block availability."""
        v = self._create_vehicle(client)
        pickup = datetime(2026, 6, 15, 10, 0)
        self._create_transfer(client, v["id"], pickup)  # stays PENDING

        resp = client.get("/availability", params={
            "date": "2026-06-15",
            "pax_count": 2,
            "pickup_time": pickup.isoformat(),
        })
        ids = [x["id"] for x in resp.json()]
        assert v["id"] in ids

    def test_filters_by_capacity(self, client):
        self._create_vehicle(client, plate="SMALL", capacity=2)
        resp = client.get("/availability", params={"date": "2026-06-15", "pax_count": 5})
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_vehicle_available_outside_2h_window(self, client):
        v = self._create_vehicle(client)
        pickup = datetime(2026, 6, 15, 8, 0)
        t = self._create_transfer(client, v["id"], pickup)
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})

        # 3 hours later — outside window
        resp = client.get("/availability", params={
            "date": "2026-06-15",
            "pax_count": 2,
            "pickup_time": datetime(2026, 6, 15, 14, 0).isoformat(),
        })
        ids = [x["id"] for x in resp.json()]
        assert v["id"] in ids


@pytest.mark.integration
class TestTransferStatusTransitions:
    def _setup(self, client):
        v = client.post("/vehicles", json={
            "type": "VAN", "capacity": 8, "plate_number": "T-001",
        }).json()
        t = client.post("/transfers", json={
            "vehicle_id": v["id"],
            "passenger_name": "Jane Doe",
            "flight_number": "KL601",
            "pickup_time": "2026-06-20T14:00:00",
            "pickup_location": "Airport",
            "dropoff_location": "Resort",
            "pax_count": 4,
        }).json()
        return t

    def test_full_lifecycle(self, client):
        t = self._setup(client)
        assert t["status"] == "PENDING"

        # PENDING -> CONFIRMED
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "CONFIRMED"

        # CONFIRMED -> IN_PROGRESS (requires driver_name)
        resp = client.patch(f"/transfers/{t['id']}/status", json={
            "status": "IN_PROGRESS",
            "driver_name": "Carlos",
        })
        assert resp.status_code == 200
        assert resp.json()["driver_name"] == "Carlos"

        # IN_PROGRESS -> COMPLETED
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "COMPLETED"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    def test_cancel_from_pending(self, client):
        t = self._setup(client)
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CANCELLED"})
        assert resp.status_code == 200

    def test_cancel_from_confirmed(self, client):
        t = self._setup(client)
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CANCELLED"})
        assert resp.status_code == 200

    def test_cannot_cancel_in_progress(self, client):
        t = self._setup(client)
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        client.patch(f"/transfers/{t['id']}/status", json={
            "status": "IN_PROGRESS", "driver_name": "Carlos",
        })
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CANCELLED"})
        assert resp.status_code == 409

    def test_cannot_cancel_completed(self, client):
        t = self._setup(client)
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        client.patch(f"/transfers/{t['id']}/status", json={
            "status": "IN_PROGRESS", "driver_name": "Carlos",
        })
        client.patch(f"/transfers/{t['id']}/status", json={"status": "COMPLETED"})
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CANCELLED"})
        assert resp.status_code == 409

    def test_in_progress_requires_driver_name(self, client):
        t = self._setup(client)
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "IN_PROGRESS"})
        assert resp.status_code == 422

    def test_status_history_recorded(self, client):
        t = self._setup(client)
        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})

        resp = client.get(f"/transfers/{t['id']}")
        assert resp.status_code == 200
        history = resp.json()["status_history"]
        assert len(history) == 2  # PENDING (creation) + CONFIRMED
        assert history[0]["new_status"] == "PENDING"
        assert history[1]["old_status"] == "PENDING"
        assert history[1]["new_status"] == "CONFIRMED"


@pytest.mark.integration
class TestTransferList:
    def test_list_by_date(self, client):
        v = client.post("/vehicles", json={
            "type": "BUS", "capacity": 20, "plate_number": "L-001",
        }).json()
        client.post("/transfers", json={
            "vehicle_id": v["id"],
            "passenger_name": "Alice",
            "flight_number": "BA200",
            "pickup_time": "2026-07-01T09:00:00",
            "pickup_location": "Airport",
            "dropoff_location": "Hotel",
            "pax_count": 10,
        })
        # Different date
        client.post("/transfers", json={
            "vehicle_id": v["id"],
            "passenger_name": "Bob",
            "flight_number": "BA201",
            "pickup_time": "2026-07-02T09:00:00",
            "pickup_location": "Airport",
            "dropoff_location": "Hotel",
            "pax_count": 5,
        })

        resp = client.get("/transfers", params={"date": "2026-07-01"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["passenger_name"] == "Alice"


@pytest.mark.integration
class TestSchemaMigration:
    """Verify the Part 2 migration fields work correctly."""

    def test_driver_fields_populated_on_in_progress(self, client):
        v = client.post("/vehicles", json={
            "type": "SEDAN", "capacity": 4, "plate_number": "M-001",
        }).json()
        t = client.post("/transfers", json={
            "vehicle_id": v["id"],
            "passenger_name": "Test",
            "flight_number": "XX99",
            "pickup_time": "2026-08-01T12:00:00",
            "pickup_location": "A",
            "dropoff_location": "B",
            "pax_count": 2,
        }).json()

        client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        resp = client.patch(f"/transfers/{t['id']}/status", json={
            "status": "IN_PROGRESS",
            "driver_name": "Miguel",
            "estimated_duration_minutes": 45,
            "notes": "Passenger has wheelchair",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["driver_name"] == "Miguel"
        assert data["estimated_duration_minutes"] == 45
        assert data["notes"] == "Passenger has wheelchair"

    def test_other_transitions_work_without_driver_name(self, client):
        """Backward compatibility: transitions other than IN_PROGRESS don't require driver_name."""
        v = client.post("/vehicles", json={
            "type": "SEDAN", "capacity": 4, "plate_number": "M-002",
        }).json()
        t = client.post("/transfers", json={
            "vehicle_id": v["id"],
            "passenger_name": "Compat",
            "flight_number": "XX100",
            "pickup_time": "2026-08-02T12:00:00",
            "pickup_location": "A",
            "dropoff_location": "B",
            "pax_count": 1,
        }).json()

        # PENDING -> CONFIRMED (no driver_name) — must still work
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CONFIRMED"})
        assert resp.status_code == 200

        # CONFIRMED -> CANCELLED (no driver_name) — must still work
        resp = client.patch(f"/transfers/{t['id']}/status", json={"status": "CANCELLED"})
        assert resp.status_code == 200
