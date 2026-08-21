from sqlalchemy import select
from uuid import uuid4
from app.core.agent_security import (
    hash_agent_secret,
    parse_agent_token,
)
from app.models.station import Station


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