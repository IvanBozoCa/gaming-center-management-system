def test_cors_allows_configured_frontend_origin(
    client,
):
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200

    assert (
        response.headers[
            "access-control-allow-origin"
        ]
        == "http://localhost:5173"
    )

    assert (
        response.headers[
            "access-control-allow-credentials"
        ]
        == "true"
    )


def test_cors_rejects_unknown_origin(
    client,
):
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400

    assert (
        "access-control-allow-origin"
        not in response.headers
    )