from app.extensions import db
from app.models import Role, RoleName, User


def test_login_flow(client, app):
    with app.app_context():
        db_role = Role.query.filter_by(name=RoleName.ADMIN.value).first()
        if not db_role:
            db_role = Role(name=RoleName.ADMIN.value)
            db.session.add(db_role)
            db.session.commit()

        user = User(username="tester", full_name="Tester", role_id=db_role.id)
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

    response = client.post("/api/login", json={"username": "tester", "password": "secret123"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["username"] == "tester"
