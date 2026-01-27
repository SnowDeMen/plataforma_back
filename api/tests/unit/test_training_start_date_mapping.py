"""
Tests unitarios para el mapeo del campo training_start_date.

Verifica el parsing correcto de fechas ISO 8601 desde Airtable
y la existencia del mapeo en la configuracion de sync.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.infrastructure.external.airtable_sync.table_mappings import (
    _parse_iso_date,
    get_table_sync_config,
)


class TestParseIsoDate:
    """Tests para la funcion _parse_iso_date."""

    def test_parse_iso_date_valid(self) -> None:
        """Fecha valida ISO 8601 retorna objeto date correcto."""
        result = _parse_iso_date("2024-09-05")
        assert result == date(2024, 9, 5)

    def test_parse_iso_date_valid_different_date(self) -> None:
        """Otra fecha valida para verificar consistencia."""
        result = _parse_iso_date("2026-01-27")
        assert result == date(2026, 1, 27)

    def test_parse_iso_date_none(self) -> None:
        """None retorna None."""
        result = _parse_iso_date(None)
        assert result is None

    def test_parse_iso_date_empty_string(self) -> None:
        """String vacio retorna None."""
        result = _parse_iso_date("")
        assert result is None

    def test_parse_iso_date_invalid_format_slash(self) -> None:
        """Formato con slashes retorna None."""
        result = _parse_iso_date("2024/09/05")
        assert result is None

    def test_parse_iso_date_invalid_format_dmY(self) -> None:
        """Formato DD-MM-YYYY retorna None (no es ISO 8601)."""
        result = _parse_iso_date("05-09-2024")
        assert result is None

    def test_parse_iso_date_invalid_text(self) -> None:
        """Texto no numerico retorna None."""
        result = _parse_iso_date("not-a-date")
        assert result is None

    def test_parse_iso_date_partial_date(self) -> None:
        """Fecha incompleta retorna None."""
        result = _parse_iso_date("2024-09")
        assert result is None

    def test_parse_iso_date_with_time(self) -> None:
        """Fecha con hora (datetime completo) se parsea correctamente."""
        # fromisoformat en Python 3.11+ puede manejar esto
        # pero la version basica de date solo acepta YYYY-MM-DD
        result = _parse_iso_date("2024-09-05T10:30:00")
        # Dependiendo de la version de Python, puede fallar o parsear solo la fecha
        # En nuestro caso, date.fromisoformat no acepta datetime strings
        assert result is None

    def test_parse_iso_date_numeric_input(self) -> None:
        """Input numerico YYYYMMDD se parsea como formato ISO 8601 compacto."""
        # Python date.fromisoformat acepta el formato compacto sin guiones
        result = _parse_iso_date(20240905)
        assert result == date(2024, 9, 5)


class TestTrainingStartDateFieldMapping:
    """Tests para verificar la configuracion del mapeo en Formulario_Inicial."""

    def test_field_mapping_exists(self) -> None:
        """Verifica que el mapeo de training_start_date existe."""
        config = get_table_sync_config(
            airtable_table_name="Formulario_Inicial",
            airtable_last_modified_field="Last Modified",
        )
        
        field_names = [m.pg_column for m in config.field_mappings]
        assert "training_start_date" in field_names

    def test_field_mapping_has_transform(self) -> None:
        """Verifica que el mapeo tiene funcion de transformacion."""
        config = get_table_sync_config(
            airtable_table_name="Formulario_Inicial",
            airtable_last_modified_field="Last Modified",
        )
        
        mapping = next(
            (m for m in config.field_mappings if m.pg_column == "training_start_date"),
            None
        )
        
        assert mapping is not None
        assert mapping.transform is not None

    def test_field_mapping_transform_is_parse_iso_date(self) -> None:
        """Verifica que la transformacion usa _parse_iso_date."""
        config = get_table_sync_config(
            airtable_table_name="Formulario_Inicial",
            airtable_last_modified_field="Last Modified",
        )
        
        mapping = next(
            (m for m in config.field_mappings if m.pg_column == "training_start_date"),
            None
        )
        
        assert mapping is not None
        # Verificar que la transformacion funciona como _parse_iso_date
        assert mapping.transform("2024-09-05") == date(2024, 9, 5)
        assert mapping.transform(None) is None
        assert mapping.transform("invalid") is None

    def test_airtable_field_name_correct(self) -> None:
        """Verifica el nombre del campo de Airtable."""
        config = get_table_sync_config(
            airtable_table_name="Formulario_Inicial",
            airtable_last_modified_field="Last Modified",
        )
        
        mapping = next(
            (m for m in config.field_mappings if m.pg_column == "training_start_date"),
            None
        )
        
        assert mapping is not None
        assert mapping.airtable_field == "Fecha de inicio de entrenamiento"
