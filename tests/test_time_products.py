import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.time_product import TimeProduct


def test_admin_can_create_time_product(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/time-products",
        json={
            "name": "1 hora",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "1 hora"
    assert data["duration_seconds"] == 3600
    assert data["price_clp"] == 2500
    assert data["is_active"] is True
    assert data["id"]
    assert data["created_at"]
    assert data["updated_at"]


def test_time_product_name_is_normalized(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/time-products",
        json={
            "name": "  Pack   1 Hora  ",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Pack 1 Hora"


def test_duplicate_time_product_returns_409(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )
    headers = auth_headers(admin)

    payload = {
        "name": "30 minutos",
        "duration_seconds": 1800,
        "price_clp": 1500,
    }

    first_response = client.post(
        "/admin/time-products",
        json=payload,
        headers=headers,
    )

    second_response = client.post(
        "/admin/time-products",
        json={
            **payload,
            "name": "  30   minutos  ",
        },
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Time product name already exists"
    }


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "",
            "duration_seconds": 1800,
            "price_clp": 1500,
        },
        {
            "name": "Inválido",
            "duration_seconds": 0,
            "price_clp": 1500,
        },
        {
            "name": "Inválido",
            "duration_seconds": -1,
            "price_clp": 1500,
        },
        {
            "name": "Inválido",
            "duration_seconds": 1800,
            "price_clp": -1,
        },
    ],
)
def test_invalid_time_product_creation_returns_422(
    client,
    user_factory,
    auth_headers,
    payload,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/time-products",
        json=payload,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_customer_cannot_create_time_product(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.post(
        "/admin/time-products",
        json={
            "name": "1 hora",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Admin privileges required"
    }


def test_time_product_endpoints_require_authentication(
    client,
):
    response = client.get(
        "/admin/time-products"
    )

    assert response.status_code == 401


def test_admin_can_list_time_products_ordered_by_name(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )
    headers = auth_headers(admin)

    products = [
        {
            "name": "2 horas",
            "duration_seconds": 7200,
            "price_clp": 4500,
        },
        {
            "name": "1 hora",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        {
            "name": "30 minutos",
            "duration_seconds": 1800,
            "price_clp": 1500,
        },
    ]

    for product in products:
        response = client.post(
            "/admin/time-products",
            json=product,
            headers=headers,
        )

        assert response.status_code == 201

    response = client.get(
        "/admin/time-products",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert [
        product["name"]
        for product in data
    ] == [
        "1 hora",
        "2 horas",
        "30 minutos",
    ]


def test_admin_can_get_time_product_detail(
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
        "/admin/time-products",
        json={
            "name": "1 hora",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        headers=headers,
    )

    product_id = create_response.json()["id"]

    response = client.get(
        f"/admin/time-products/{product_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == product_id
    assert response.json()["name"] == "1 hora"


def test_unknown_time_product_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        (
            "/admin/time-products/"
            "00000000-0000-0000-0000-000000000000"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Time product not found"
    }


def test_admin_can_update_time_product(
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
        "/admin/time-products",
        json={
            "name": "1 hora",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        headers=headers,
    )

    product_id = create_response.json()["id"]

    response = client.patch(
        f"/admin/time-products/{product_id}",
        json={
            "name": "Pack 1 Hora",
            "duration_seconds": 3900,
            "price_clp": 3000,
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Pack 1 Hora"
    assert data["duration_seconds"] == 3900
    assert data["price_clp"] == 3000


def test_admin_can_deactivate_time_product_and_filter(
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
        "/admin/time-products",
        json={
            "name": "Promoción",
            "duration_seconds": 1800,
            "price_clp": 1000,
        },
        headers=headers,
    )

    product_id = create_response.json()["id"]

    update_response = client.patch(
        f"/admin/time-products/{product_id}",
        json={
            "is_active": False,
        },
        headers=headers,
    )

    assert update_response.status_code == 200
    assert update_response.json()["is_active"] is False

    active_response = client.get(
        "/admin/time-products?is_active=true",
        headers=headers,
    )

    inactive_response = client.get(
        "/admin/time-products?is_active=false",
        headers=headers,
    )

    assert active_response.status_code == 200
    assert inactive_response.status_code == 200

    assert all(
        product["id"] != product_id
        for product in active_response.json()
    )

    assert any(
        product["id"] == product_id
        for product in inactive_response.json()
    )


def test_empty_time_product_patch_returns_422(
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
        "/admin/time-products",
        json={
            "name": "1 hora",
            "duration_seconds": 3600,
            "price_clp": 2500,
        },
        headers=headers,
    )

    product_id = create_response.json()["id"]

    response = client.patch(
        f"/admin/time-products/{product_id}",
        json={},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "product_data",
    [
        {
            "name": "Duración inválida",
            "duration_seconds": 0,
            "price_clp": 1000,
        },
        {
            "name": "Precio inválido",
            "duration_seconds": 1800,
            "price_clp": -1,
        },
    ],
)
def test_database_rejects_invalid_time_product_values(
    db_session,
    product_data,
):
    product = TimeProduct(
        **product_data,
    )

    db_session.add(product)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    stored_product = db_session.scalar(
        select(TimeProduct).where(
            TimeProduct.name
            == product_data["name"]
        )
    )

    assert stored_product is None