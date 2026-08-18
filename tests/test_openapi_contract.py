from app.main import app


def test_frontend_mvp_openapi_contract():
    openapi = app.openapi()
    paths = openapi["paths"]

    expected_operations = {
        # Authentication / customers
        ("/auth/login", "post"),
        ("/auth/me", "get"),
        ("/auth/register", "post"),

        # Customer administration
        ("/admin/customers", "get"),
        (
            "/admin/customers/{customer_id}",
            "get",
        ),
        (
            "/admin/customers/{customer_id}/wallet",
            "get",
        ),
        (
            "/admin/customers/"
            "{customer_id}/time-transactions",
            "get",
        ),
        (
            "/admin/customers/"
            "{customer_id}/time-purchases",
            "post",
        ),

        # Stations
        ("/admin/stations", "get"),
        ("/admin/stations", "post"),
        (
            "/admin/stations/{station_id}/status",
            "patch",
        ),
        # Time products
        ("/admin/time-products", "get"),
        ("/admin/time-products", "post"),
        (
            "/admin/time-products/{time_product_id}",
            "get",
        ),
        (
            "/admin/time-products/{time_product_id}",
            "patch",
        ),
        # Time sales
        (
            "/admin/time-sales",
            "post",
        ),

        # Registered sessions
        ("/admin/sessions", "post"),
        ("/admin/sessions/active", "get"),
        ("/admin/sessions/history", "get"),
        (
            "/admin/sessions/{session_id}/extend",
            "post",
        ),
        (
            "/admin/sessions/{session_id}/finish",
            "post",
        ),

        # Guest sessions
        ("/admin/guest-sessions", "post"),
        (
            "/admin/guest-sessions/active",
            "get",
        ),
        (
            "/admin/guest-sessions/history",
            "get",
        ),
        (
            "/admin/guest-sessions/"
            "{session_id}/finish",
            "post",
        ),
    }

    missing_operations = []

    for path, method in expected_operations:
        if path not in paths:
            missing_operations.append(
                f"{method.upper()} {path}"
            )
            continue

        if method not in paths[path]:
            missing_operations.append(
                f"{method.upper()} {path}"
            )

    assert not missing_operations, (
        "Missing frontend MVP API contracts: "
        + ", ".join(
            sorted(missing_operations)
        )
    )