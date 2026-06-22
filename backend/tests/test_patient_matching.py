from types import SimpleNamespace
from unittest.mock import Mock

from app.matchers.patient_matcher import PatientMatcher


def test_patient_matcher_uses_normalized_identifier_against_screening_records() -> None:
    row = SimpleNamespace(normalized_cid="1234567890123", normalized_full_name="alpha", normalized_birth_date=None, normalized_sex=None)
    patient = SimpleNamespace(id="patient-1", citizen_id="1234567890123", pid=None)
    db = Mock()
    db.scalar.return_value = "screening-record-1"
    db.scalars.return_value.all.return_value = [patient]

    decision = PatientMatcher.match(db, row)

    assert decision.patient is patient
    assert decision.match_method == "identifier_exact"
    assert decision.match_status == "matched"
    assert decision.matched_identifier_basis == "1234567890123"


def test_patient_matcher_returns_matched_even_without_patient_master_link() -> None:
    row = SimpleNamespace(normalized_cid="1234567890123", normalized_full_name="alpha", normalized_birth_date=None, normalized_sex=None)
    db = Mock()
    db.scalar.return_value = "screening-record-1"
    db.scalars.return_value.all.return_value = []

    decision = PatientMatcher.match(db, row)

    assert decision.patient is None
    assert decision.match_method == "identifier_exact"
    assert decision.match_status == "matched"
    assert decision.match_confidence == "medium"


def test_patient_matcher_returns_not_found_when_screening_identifier_missing() -> None:
    row = SimpleNamespace(normalized_cid="1234567890123", normalized_full_name=None, normalized_birth_date=None, normalized_sex=None)
    db = Mock()
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = []

    decision = PatientMatcher.match(db, row)

    assert decision.patient is None
    assert decision.match_method == "not_found"
    assert decision.match_status == "not_found"


def test_identifier_match_takes_precedence_over_name_secondary() -> None:
    row = SimpleNamespace(normalized_cid="1234567890123", normalized_full_name="same name", normalized_birth_date=None, normalized_sex=None)
    patient = SimpleNamespace(id="patient-1", citizen_id="1234567890123", pid=None)
    db = Mock()
    db.scalar.return_value = "screening-record-1"
    db.scalars.return_value.all.return_value = [patient]

    decision = PatientMatcher.match(db, row)

    assert decision.match_method == "identifier_exact"
    assert decision.matched_name_basis is None


def test_name_secondary_only_used_when_identifier_match_unavailable() -> None:
    row = SimpleNamespace(normalized_cid="1234567890123", normalized_full_name="same name", normalized_birth_date=None, normalized_sex=None)
    name_record = SimpleNamespace(normalized_person_identifier="9999999999999")
    db = Mock()
    db.scalar.return_value = None
    db.scalars.side_effect = [
        SimpleNamespace(all=lambda: [name_record]),
        SimpleNamespace(all=lambda: []),
    ]

    decision = PatientMatcher.match(db, row)

    assert decision.match_method == "name_exact_secondary"
    assert decision.match_status == "matched"
    assert decision.matched_identifier_basis == "9999999999999"
    assert decision.matched_name_basis == "same name"
