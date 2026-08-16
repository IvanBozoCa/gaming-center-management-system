import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.station import Station


def test_admin_can_create_station(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/stations",
        json={
            "code": "PC-01",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["code"] == "PC-01"
    assert data["status"] == "AVAILABLE"
    assert data["id"]
    assert data["created_at"]
    assert data["updated_at"]


def test_station_code_is_normalized(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/stations",
        json={
            "code": "  pc-vip-01  ",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201
    assert response.json()["code"] == "PC-VIP-01"


def test_new_station_always_starts_available(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/stations",
        json={
            "code": "PC-01",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "AVAILABLE"


def test_station_creation_rejects_status_from_client(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/stations",
        json={
            "code": "PC-01",
            "status": "IN_USE",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_duplicate_station_code_returns_409(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    first_response = client.post(
        "/admin/stations",
        json={
            "code": "PC-01",
        },
        headers=auth_headers(admin),
    )

    second_response = client.post(
        "/admin/stations",
        json={
            "code": " pc-01 ",
        },
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    assert second_response.json() == {
        "detail": "Station code already exists"
    }


@pytest.mark.parametrize(
    "code",
    [
        "",
        "   ",
        "A" * 51,
    ],
)
def test_invalid_station_code_returns_422(
    client,
    user_factory,
    auth_headers,
    code,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/stations",
        json={
            "code": code,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_customer_cannot_create_station(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.post(
        "/admin/stations",
        json={
            "code": "PC-01",
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Admin privileges required"
    }


def test_customer_cannot_list_stations(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        "/admin/stations",
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/admin/stations"),
        ("POST", "/admin/stations"),
    ],
)
def test_station_endpoints_require_authentication(
    client,
    method,
    url,
):
    if method == "POST":
        response = client.post(
            url,
            json={
                "code": "PC-01",
            },
        )
    else:
        response = client.get(url)

    assert response.status_code == 401


def test_admin_can_list_stations_ordered_by_code(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    headers = auth_headers(admin)

    for code in [
        "PC-03",
        "pc-01",
        "PC-02",
    ]:
        response = client.post(
            "/admin/stations",
            json={
                "code": code,
            },
            headers=headers,
        )

        assert response.status_code == 201

    response = client.get(
        "/admin/stations",
        headers=headers,
    )

    assert response.status_code == 200

    stations = response.json()

    assert [
        station["code"]
        for station in stations
    ] == [
        "PC-01",
        "PC-02",
        "PC-03",
    ]


def test_station_list_response_is_safe_for_admin_ui(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    headers = auth_headers(admin)

    create_response = client.post(
        "/admin/stations",
        json={
            "code": "PC-01",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        "/admin/stations",
        headers=headers,
    )

    assert response.status_code == 200

    stations = response.json()

    assert len(stations) == 1

    station = stations[0]

    assert set(station.keys()) == {
        "id",
        "code",
        "status",
        "created_at",
        "updated_at",
    }


@pytest.mark.parametrize(
    "station_status",
    [
        "AVAILABLE",
        "IN_USE",
        "MAINTENANCE",
        "OFFLINE",
    ],
)
def test_database_accepts_supported_station_statuses(
    db_session,
    station_status,
):
    station = Station(
        code=f"PC-{station_status}",
        status=station_status,
    )

    db_session.add(station)
    db_session.commit()

    stored_station = db_session.scalar(
        select(Station).where(
            Station.id == station.id
        )
    )

    assert stored_station is not None
    assert stored_station.status == station_status


def test_database_rejects_unknown_station_status(
    db_session,
):
    station = Station(
        code="PC-01",
        status="BROKEN",
    )

    db_session.add(station)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    stored_station = db_session.scalar(
        select(Station).where(
            Station.code == "PC-01"
        )
    )

    assert stored_station is None