def test_customer_cannot_register_customer(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.post(
        "/auth/register",
        headers=auth_headers(customer),
        json={
            "username": "cliente02",
            "display_name": "Cliente Dos",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Admin privileges required"
    }


def test_register_without_token_returns_401(
    client,
):
    response = client.post(
        "/auth/register",
        json={
            "username": "cliente02",
            "display_name": "Cliente Dos",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 401


def test_register_with_invalid_token_returns_401(
    client,
):
    response = client.post(
        "/auth/register",
        headers={
            "Authorization": "Bearer token-invalido"
        },
        json={
            "username": "cliente02",
            "display_name": "Cliente Dos",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }


def test_inactive_admin_with_existing_token_returns_401(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin",
        role="ADMIN",
    )

    headers = auth_headers(admin)

    admin.is_active = False
    db_session.commit()

    response = client.post(
        "/auth/register",
        headers=headers,
        json={
            "username": "cliente02",
            "display_name": "Cliente Dos",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 401


def test_admin_loses_access_after_role_change(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin",
        role="ADMIN",
    )

    headers = auth_headers(admin)

    admin.role = "CUSTOMER"
    db_session.commit()

    response = client.post(
        "/auth/register",
        headers=headers,
        json={
            "username": "cliente02",
            "display_name": "Cliente Dos",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Admin privileges required"
    }