from sqlalchemy import select
from uuid import uuid4
from app.core.agent_security import (
    hash_agent_secret,
    parse_agent_token,
)
from app.models.station import Station
from datetime import datetime, timezone
import pytest
from starlette.websockets import (
    WebSocketDisconnect,
)
from app.services.usage_session_service import (
    start_guest_session,
    start_registered_customer_session,
)
from unittest.mock import MagicMock

from app.services.station_presence import (
    StationPresenceRegistry,
    station_presence_registry,
)

def _create_station(
    db_session,
    *,
    code: str = "PC-01",
    status: str = "AVAILABLE",
):
    station = Station(
        code=code,
        status=status,
    )

    db_session.add(station)
    db_session.commit()
    db_session.refresh(station)

    return station


def _create_agent_token(
    client,
    station,
    user_factory,
    auth_headers,
) -> str:
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        (
            f"/admin/stations/{station.id}/"
            "agent-credential"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    return response.json()["agent_token"]


def test_admin_can_generate_agent_credential(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session
    )

    response = client.post(
        (
            f"/admin/stations/"
            f"{station.id}/"
            "agent-credential"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["station_id"]
        == str(station.id)
    )

    assert (
        data["station_code"]
        == station.code
    )

    token = data["agent_token"]

    parsed = parse_agent_token(
        token
    )

    assert parsed is not None

    key_id, secret = parsed

    db_session.expire_all()

    stored_station = (
        db_session.get(
            Station,
            station.id,
        )
    )

    assert stored_station is not None

    assert (
        stored_station.agent_key_id
        == key_id
    )

    assert (
        stored_station.agent_secret_hash
        == hash_agent_secret(secret)
    )

    assert (
        secret
        not in stored_station.agent_secret_hash
    )


def test_agent_token_identifies_station(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session
    )

    credential_response = (
        client.post(
            (
                f"/admin/stations/"
                f"{station.id}/"
                "agent-credential"
            ),
            headers=auth_headers(
                admin
            ),
        )
    )

    token = (
        credential_response.json()[
            "agent_token"
        ]
    )

    response = client.get(
        "/agent/station",
        headers={
            "Authorization":
                f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["id"]
        == str(station.id)
    )

    assert data["code"] == "PC-01"
    assert data["status"] == "AVAILABLE"


def test_invalid_agent_token_returns_401(
    client,
):
    response = client.get(
        "/agent/station",
        headers={
            "Authorization":
                "Bearer invalid-token",
        },
    )

    assert response.status_code == 401


def test_rotating_agent_credential_invalidates_old_token(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session
    )

    first = client.post(
        (
            f"/admin/stations/"
            f"{station.id}/"
            "agent-credential"
        ),
        headers=auth_headers(admin),
    )

    old_token = (
        first.json()[
            "agent_token"
        ]
    )

    second = client.post(
        (
            f"/admin/stations/"
            f"{station.id}/"
            "agent-credential"
        ),
        headers=auth_headers(admin),
    )

    new_token = (
        second.json()[
            "agent_token"
        ]
    )

    assert old_token != new_token

    old_response = client.get(
        "/agent/station",
        headers={
            "Authorization":
                f"Bearer {old_token}",
        },
    )

    assert (
        old_response.status_code
        == 401
    )

    new_response = client.get(
        "/agent/station",
        headers={
            "Authorization":
                f"Bearer {new_token}",
        },
    )

    assert (
        new_response.status_code
        == 200
    )


def test_admin_can_revoke_agent_credential(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(db_session)

    credential_response = client.post(
        f"/admin/stations/{station.id}/agent-credential",
        headers=auth_headers(admin),
    )

    assert credential_response.status_code == 200

    token = credential_response.json()["agent_token"]

    revoke_response = client.delete(
        f"/admin/stations/{station.id}/agent-credential",
        headers=auth_headers(admin),
    )

    assert revoke_response.status_code == 204
    assert revoke_response.content == b""

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.agent_key_id is None
    assert stored_station.agent_secret_hash is None

    agent_response = client.get(
        "/agent/station",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert agent_response.status_code == 401


def test_revoking_unknown_station_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.delete(
        f"/admin/stations/{uuid4()}/agent-credential",
        headers=auth_headers(admin),
    )

    assert response.status_code == 404


def test_agent_heartbeat_updates_last_seen_without_changing_status(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session,
        status="MAINTENANCE",
    )

    credential_response = (
        client.post(
            (
                f"/admin/stations/"
                f"{station.id}/"
                "agent-credential"
            ),
            headers=auth_headers(
                admin
            ),
        )
    )

    token = (
        credential_response.json()[
            "agent_token"
        ]
    )

    response = client.post(
        "/agent/heartbeat",
        headers={
            "Authorization":
                f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["status"]
        == "MAINTENANCE"
    )

    assert (
        data["last_seen_at"]
        is not None
    )

    db_session.expire_all()

    stored_station = (
        db_session.get(
            Station,
            station.id,
        )
    )

    assert stored_station is not None

    assert (
        stored_station.status
        == "MAINTENANCE"
    )

    assert (
        stored_station.last_seen_at
        is not None
    )


def test_user_jwt_cannot_authenticate_as_station_agent(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    headers = auth_headers(
        admin
    )

    response = client.get(
        "/agent/station",
        headers=headers,
    )

    assert response.status_code == 401


def test_agent_websocket_requires_authentication(
    client,
):
    with pytest.raises(
        WebSocketDisconnect
    ) as exception:
        with client.websocket_connect(
            "/agent/ws"
        ):
            pass

    assert exception.value.code == 1008


def test_user_jwt_cannot_authenticate_websocket(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    with pytest.raises(
        WebSocketDisconnect
    ) as exception:
        with client.websocket_connect(
            "/agent/ws",
            headers=auth_headers(admin),
        ):
            pass

    assert exception.value.code == 1008


def test_agent_websocket_accepts_heartbeat(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    station = _create_station(
        db_session,
        status="MAINTENANCE",
    )

    token = _create_agent_token(
        client,
        station,
        user_factory,
        auth_headers,
    )

    event_id = uuid4()

    with client.websocket_connect(
        "/agent/ws",
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
        },
    ) as websocket:
        connected = (
            websocket.receive_json()
        )

        assert (
            connected["type"]
            == "CONNECTED"
        )

        assert connected["version"] == 1

        assert (
            connected["data"]["station_id"]
            == str(station.id)
        )

        websocket.send_json(
            {
                "version": 1,
                "type": "HEARTBEAT",
                "event_id": str(event_id),
                "correlation_id": None,
                "sent_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }
        )

        acknowledgement = (
            websocket.receive_json()
        )

        assert (
            acknowledgement["type"]
            == "HEARTBEAT_ACK"
        )

        assert (
            acknowledgement[
                "correlation_id"
            ]
            == str(event_id)
        )

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None

    assert (
        stored_station.status
        == "MAINTENANCE"
    )

    assert (
        stored_station.last_seen_at
        is not None
    )


def test_agent_websocket_rejects_unknown_version(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    station = _create_station(
        db_session
    )

    token = _create_agent_token(
        client,
        station,
        user_factory,
        auth_headers,
    )

    with client.websocket_connect(
        "/agent/ws",
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
        },
    ) as websocket:
        websocket.receive_json()

        websocket.send_json(
            {
                "version": 999,
                "type": "HEARTBEAT",
                "event_id": str(
                    uuid4()
                ),
                "sent_at": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
            }
        )

        response = (
            websocket.receive_json()
        )

        assert response["type"] == "ERROR"

        assert (
            response["data"]["code"]
            == "INVALID_MESSAGE"
        )

def test_agent_websocket_tracks_station_presence(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    station = _create_station(
        db_session
    )

    token = _create_agent_token(
        client,
        station,
        user_factory,
        auth_headers,
    )

    before = (
        station_presence_registry
        .get_presence(station.id)
    )

    assert (
        before.connection_status
        == "OFFLINE"
    )

    with client.websocket_connect(
        "/agent/ws",
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
        },
    ) as websocket:
        websocket.receive_json()

        connected = (
            station_presence_registry
            .get_presence(station.id)
        )

        assert (
            connected.connection_status
            == "CONNECTED"
        )

        assert (
            connected.connected_at
            is not None
        )

        assert (
            connected.last_heartbeat_at
            is not None
        )

    disconnected = (
        station_presence_registry
        .get_presence(station.id)
    )

    assert (
        disconnected.connection_status
        == "OFFLINE"
    )


def test_station_presence_records_heartbeat():
    registry = StationPresenceRegistry()

    station_id = uuid4()
    websocket = MagicMock()

    connection, _ = registry.register(
        station_id,
        websocket,
    )

    initial = registry.get_presence(
        station_id
    )

    heartbeat_at = (
        registry.record_heartbeat(
            station_id,
            connection.connection_id,
        )
    )

    updated = registry.get_presence(
        station_id
    )

    assert heartbeat_at is not None

    assert (
        updated.connection_status
        == "CONNECTED"
    )

    assert (
        updated.last_heartbeat_at
        == heartbeat_at
    )

    assert (
        updated.last_heartbeat_at
        >= initial.last_heartbeat_at
    )


def test_old_connection_cannot_unregister_new_connection():
    registry = StationPresenceRegistry()

    station_id = uuid4()

    first_websocket = MagicMock()
    second_websocket = MagicMock()

    first_connection, _ = (
        registry.register(
            station_id,
            first_websocket,
        )
    )

    second_connection, previous = (
        registry.register(
            station_id,
            second_websocket,
        )
    )

    assert previous is first_websocket

    registry.unregister(
        station_id,
        first_connection.connection_id,
    )

    presence = registry.get_presence(
        station_id
    )

    assert (
        presence.connection_status
        == "CONNECTED"
    )

    assert (
        presence.connected_at
        == second_connection.connected_at
    )

    assert (
        registry.record_heartbeat(
            station_id,
            first_connection.connection_id,
        )
        is None
    )

    registry.unregister(
        station_id,
        second_connection.connection_id,
    )

    presence = registry.get_presence(
        station_id
    )

    assert (
        presence.connection_status
        == "OFFLINE"
    )


def test_agent_connected_reports_no_active_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    station = _create_station(
        db_session
    )

    token = _create_agent_token(
        client,
        station,
        user_factory,
        auth_headers,
    )

    with client.websocket_connect(
        "/agent/ws",
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
        },
    ) as websocket:
        connected = (
            websocket.receive_json()
        )

        assert (
            connected["type"]
            == "CONNECTED"
        )

        assert (
            connected["data"][
                "active_session"
            ]
            is None
        )

def test_agent_connected_reports_registered_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=7200,
    )

    station = _create_station(
        db_session
    )

    credential_response = client.post(
        (
            f"/admin/stations/"
            f"{station.id}/"
            "agent-credential"
        ),
        headers=auth_headers(admin),
    )

    assert (
        credential_response.status_code
        == 200
    )

    token = (
        credential_response.json()[
            "agent_token"
        ]
    )

    session = (
        start_registered_customer_session(
            db_session,
            station_id=station.id,
            customer_id=customer.id,
            authorized_seconds=3600,
            actor_user_id=admin.id,
        )
    )

    with client.websocket_connect(
        "/agent/ws",
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
        },
    ) as websocket:
        connected = (
            websocket.receive_json()
        )

        active_session = (
            connected["data"][
                "active_session"
            ]
        )

        assert active_session is not None

        assert (
            active_session["session_id"]
            == str(session.session_id)
        )

        assert (
            active_session["session_type"]
            == "REGISTERED"
        )

        assert (
            active_session[
                "authorized_seconds"
            ]
            == 3600
        )

        assert (
            active_session[
                "elapsed_seconds"
            ]
            >= 0
        )

        assert (
            0
            <= active_session[
                "remaining_seconds"
            ]
            <= 3600
        )

        assert (
            active_session["time_state"]
            == "RUNNING"
        )

        assert (
            active_session["started_at"]
            is not None
        )

        assert (
            active_session["server_now"]
            is not None
        )

def test_agent_connected_reports_guest_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    station = _create_station(
        db_session
    )

    token = _create_agent_token(
        client,
        station,
        user_factory,
        auth_headers,
    )

    session = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    with client.websocket_connect(
        "/agent/ws",
        headers={
            "Authorization": (
                f"Bearer {token}"
            ),
        },
    ) as websocket:
        connected = (
            websocket.receive_json()
        )

        active_session = (
            connected["data"][
                "active_session"
            ]
        )

        assert active_session is not None

        assert (
            active_session["session_id"]
            == str(session.session_id)
        )

        assert (
            active_session["session_type"]
            == "GUEST"
        )

        assert (
            active_session[
                "authorized_seconds"
            ]
            == 1800
        )

        assert (
            active_session[
                "elapsed_seconds"
            ]
            >= 0
        )

        assert (
            0
            <= active_session[
                "remaining_seconds"
            ]
            <= 1800
        )

        assert (
            active_session["time_state"]
            == "RUNNING"
        )

        assert (
            active_session["started_at"]
            is not None
        )

        assert (
            active_session["server_now"]
            is not None
        )


