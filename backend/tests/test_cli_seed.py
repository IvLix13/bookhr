from app.models import GradeCatalog


def test_seed_does_not_create_default_grades(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed"])
    assert result.exit_code == 0
    assert "Seed completed" in result.output

    with app.app_context():
        assert GradeCatalog.query.count() == 0
