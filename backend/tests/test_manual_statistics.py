from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.models import ManualStatisticsSnapshot


def _manual_statistics_file(rows: list[tuple[object, object]]) -> BytesIO:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Ручная статистика"
    worksheet.append(["Показатель", "Значение"])
    for row in rows:
        worksheet.append(list(row))

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def test_manual_stats_empty_for_viewer(viewer_client):
    response = viewer_client.get("/api/stats/manual")

    assert response.status_code == 200
    payload = response.get_json()["data"]
    assert payload == {
        "items": [],
        "source_filename": None,
        "updated_at": None,
    }


def test_manual_stats_template_can_be_downloaded(viewer_client):
    response = viewer_client.get("/api/stats/manual/template")

    assert response.status_code == 200
    assert response.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(response.data), read_only=True, data_only=True)
    worksheet = workbook.active
    assert worksheet["A1"].value == "Показатель"
    assert worksheet["B1"].value == "Значение"
    workbook.close()


def test_manual_stats_upload_and_read(hr_client, seed_company):
    response = hr_client.post(
        "/api/stats/manual/upload",
        data={
            "file": (
                _manual_statistics_file(
                    [
                        ("Среднесписочная численность", 125),
                        ("Комментарий", "Данные из отчёта"),
                    ]
                ),
                "manual.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["items"] == [
        {"label": "Среднесписочная численность", "value": "125"},
        {"label": "Комментарий", "value": "Данные из отчёта"},
    ]
    assert data["source_filename"] == "manual.xlsx"
    assert data["updated_at"] is not None

    stored = ManualStatisticsSnapshot.query.filter_by(company_id=seed_company.id).one()
    assert stored.items == data["items"]

    get_response = hr_client.get("/api/stats/manual")
    assert get_response.status_code == 200
    assert get_response.get_json()["data"]["items"] == data["items"]


def test_manual_stats_upload_replaces_previous_snapshot(hr_client):
    first = hr_client.post(
        "/api/stats/manual/upload",
        data={"file": (_manual_statistics_file([("Первый", 1)]), "first.xlsx")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200

    second = hr_client.post(
        "/api/stats/manual/upload",
        data={"file": (_manual_statistics_file([("Второй", 2)]), "second.xlsx")},
        content_type="multipart/form-data",
    )
    assert second.status_code == 200

    data = second.get_json()["data"]
    assert data["items"] == [{"label": "Второй", "value": "2"}]
    assert data["source_filename"] == "second.xlsx"
    assert ManualStatisticsSnapshot.query.count() == 1


def test_manual_stats_upload_rejects_wrong_template(hr_client):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Не тот столбец", "Значение"])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    response = hr_client.post(
        "/api/stats/manual/upload",
        data={"file": (output, "wrong.xlsx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "Ожидаются колонки" in response.get_json()["message"]


def test_manual_stats_upload_rejects_duplicate_labels(hr_client):
    response = hr_client.post(
        "/api/stats/manual/upload",
        data={
            "file": (
                _manual_statistics_file([("Одинаковый", 1), ("Одинаковый", 2)]),
                "duplicates.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "более одного раза" in response.get_json()["message"]


def test_manual_stats_upload_viewer_forbidden(viewer_client):
    response = viewer_client.post(
        "/api/stats/manual/upload",
        data={"file": (_manual_statistics_file([("Показатель", 1)]), "manual.xlsx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 403
