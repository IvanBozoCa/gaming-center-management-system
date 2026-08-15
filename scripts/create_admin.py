from getpass import getpass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserRegister


def create_initial_admin() -> None:
    db = SessionLocal()

    try:
        existing_admin = db.scalar(
            select(User).where(
                User.role == "ADMIN"
            )
        )

        if existing_admin is not None:
            print(
                "An ADMIN user already exists. "
                "Bootstrap cancelled."
            )
            return

        username = input(
            "Admin username: "
        )

        display_name = input(
            "Admin display name: "
        )

        password = getpass(
            "Admin password: "
        )

        password_confirmation = getpass(
            "Confirm password: "
        )

        if password != password_confirmation:
            print(
                "Passwords do not match."
            )
            return

        data = UserRegister(
            username=username,
            display_name=display_name,
            password=password,
        )

        existing_username = db.scalar(
            select(User).where(
                User.username == data.username
            )
        )

        if existing_username is not None:
            print(
                "Username already exists."
            )
            return

        admin = User(
            username=data.username,
            display_name=data.display_name,
            password_hash=hash_password(
                data.password
            ),
            role="ADMIN",
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print()
        print("Initial ADMIN created successfully.")
        print(f"Username: {admin.username}")
        print(f"User ID: {admin.id}")

    except IntegrityError:
        db.rollback()
        print(
            "Could not create ADMIN due "
            "to a database conflict."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_initial_admin()