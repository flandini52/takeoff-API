"""Trasformazioni dell'extract su JSON finto (nessun dato reale, nessuna
chiamata API) — stessa forma delle risposte reali di Takeoff CRM, vista
nei test manuali durante la migrazione, ma con valori inventati."""

from landini_etl.extract.activities import build_row as build_activity_row
from landini_etl.extract.deadlines import build_deadline_rows, build_subject_row

EXTRACTED_AT = "2026-09-01T00:00:00+00:00"


def test_build_activity_row_maps_nested_fields():
    fake_activity = {
        "id": 123,
        "activityType": {"id": 16602, "name": "Manutenzione ordinaria programmata"},
        "assignedUser": {"id": 5, "displayName": "Mario Rossi"},
        "contact": {"id": 9, "companyName": " Acme Srl "},
        "job": {"id": 3, "name": "Commessa test"},
        "contactAddress": {
            "address": "Via Roma 1",
            "city": "Firenze",
            "province": "FI",
            "postalCode": "50100",
            "fullAddress": "Via Roma 1, Firenze",
            "latitude": 43.77,
            "longitude": 11.25,
        },
        "start": "2026-09-01T08:00:00",
        "end": "2026-09-01T10:00:00",
        "duration": 120,
        "completed": True,
        "confirmed": True,
        "approved": False,
    }

    row = build_activity_row(fake_activity, EXTRACTED_AT)

    assert row["activity_id"] == 123
    assert row["activity_type_id"] == 16602
    assert row["assigned_user_name"] == "Mario Rossi"
    assert row["company_name"] == "Acme Srl"  # strip()-ed
    assert row["city"] == "Firenze"
    assert row["completed"] is True
    assert row["approved"] is False
    assert row["source_system"] == "takeoff_crm"
    assert row["extracted_at"] == EXTRACTED_AT


def test_build_activity_row_handles_missing_nested_objects():
    fake_activity = {"id": 1, "completed": False, "confirmed": False, "approved": False}

    row = build_activity_row(fake_activity, EXTRACTED_AT)

    assert row["activity_id"] == 1
    assert row["assigned_user_name"] is None
    assert row["company_name"] is None


def test_build_subject_row_detects_employee():
    fake_contact = {"id": 1, "companyName": "Landini Srl"}
    fake_folder = {"id": 100, "name": "Mario Rossi", "typology": {"name": "Personale"}}

    row = build_subject_row(fake_contact, fake_folder, EXTRACTED_AT)

    assert row["is_employee"] is True
    assert row["subject_name"] == "Mario Rossi"


def test_build_subject_row_non_employee():
    fake_contact = {"id": 1, "companyName": "Landini Srl"}
    fake_folder = {"id": 200, "name": "VEICOLI", "typology": {"name": "Scadenze varie"}}

    row = build_subject_row(fake_contact, fake_folder, EXTRACTED_AT)

    assert row["is_employee"] is False


def test_build_deadline_rows_normalizes_date_and_finds_document():
    fake_folder = {
        "id": 100,
        "elements": [
            {
                "id": 500,
                "name": "Antincendio",
                "typology": {"name": "Formazione"},
                "properties": [
                    {"name": "Scadenza", "value": "14/01/2027"},
                    {"name": "Documento", "value": "certificato.pdf"},
                ],
            }
        ]
    }

    rows = list(build_deadline_rows(fake_folder, EXTRACTED_AT))

    assert len(rows) == 1
    row = rows[0]
    assert row["element_id"] == 500
    assert row["subject_id"] == 100
    assert row["expiry_date"] == "2027-01-14"  # dd/mm/yyyy -> ISO 8601
    assert row["document_filename"] == "certificato.pdf"
    assert row["raw_properties"] == fake_folder["elements"][0]["properties"]


def test_build_deadline_rows_element_with_no_properties():
    fake_folder = {"id": 101, "elements": [{"id": 501, "name": "Vuoto", "typology": None, "properties": []}]}

    rows = list(build_deadline_rows(fake_folder, EXTRACTED_AT))

    assert len(rows) == 1
    assert rows[0]["expiry_date"] is None
    assert rows[0]["document_filename"] is None
