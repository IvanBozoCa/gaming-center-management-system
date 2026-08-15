def test_get_my_wallet_returns_current_customer_balance(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
        available_seconds=7200,
        reserved_seconds=1800,
    )

    response = client.get(
        "/me/wallet",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200

    assert response.json() == {
        "available_seconds": 7200,
        "reserved_seconds": 1800,
    }

    
def test_get_my_wallet_does_not_return_another_customer_wallet(
    client,
    user_factory,
    auth_headers,
):
    customer_one = user_factory(
        username="cliente01",
        available_seconds=3600,
        reserved_seconds=600,
    )

    user_factory(
        username="cliente02",
        available_seconds=20000,
        reserved_seconds=5000,
    )

    response = client.get(
        "/me/wallet",
        headers=auth_headers(customer_one),
    )

    assert response.status_code == 200

    assert response.json() == {
        "available_seconds": 3600,
        "reserved_seconds": 600,
    }

    
def test_get_my_wallet_does_not_expose_internal_fields(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        available_seconds=3600,
    )

    response = client.get(
        "/me/wallet",
        headers=auth_headers(customer),
    )

    assert response.status_code == 200

    data = response.json()

    assert set(data.keys()) == {
        "available_seconds",
        "reserved_seconds",
    }

    assert "id" not in data
    assert "user_id" not in data
    assert "updated_at" not in data

    
def test_get_my_wallet_without_token_returns_401(
    client,
):
    response = client.get(
        "/me/wallet"
    )

    assert response.status_code == 401

    
def test_get_my_wallet_with_invalid_token_returns_401(
    client,
):
    response = client.get(
        "/me/wallet",
        headers={
            "Authorization": (
                "Bearer esto-no-es-un-token-valido"
            )
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }

    
def test_inactive_customer_cannot_get_wallet(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
        available_seconds=7200,
    )

    headers = auth_headers(customer)

    customer.is_active = False
    db_session.commit()

    response = client.get(
        "/me/wallet",
        headers=headers,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }