"""
Tests unitarios para TrainingPlanService.

Utiliza mocks de Selenium para verificar la logica del servicio
sin necesidad de un navegador real.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.infrastructure.driver.services.training_plan_service import TrainingPlanService


class TestTrainingPlanServiceInit:
    """Tests para la inicializacion del servicio."""

    def test_init_stores_driver_and_wait(self) -> None:
        """Verifica que el constructor almacena driver y wait."""
        mock_driver = Mock()
        mock_wait = Mock()
        
        service = TrainingPlanService(mock_driver, mock_wait)
        
        assert service._driver is mock_driver
        assert service._wait is mock_wait


class TestClickTrainingPlansTab:
    """Tests para click_training_plans_tab."""

    @pytest.fixture
    def service(self) -> TrainingPlanService:
        """Fixture que crea un servicio con mocks."""
        mock_driver = Mock()
        mock_wait = Mock()
        return TrainingPlanService(mock_driver, mock_wait)

    def test_click_training_plans_tab_finds_element_by_xpath(self, service: TrainingPlanService) -> None:
        """Verifica que busca el elemento correcto por xpath."""
        mock_element = Mock()
        
        with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
            mock_wait_instance = Mock()
            mock_webdriver_wait.return_value = mock_wait_instance
            mock_wait_instance.until.return_value = mock_element
            
            service.click_training_plans_tab()
            
            mock_element.click.assert_called_once()


class TestIsFolderExpanded:
    """Tests para is_folder_expanded."""

    @pytest.fixture
    def service(self) -> TrainingPlanService:
        """Fixture que crea un servicio con mocks."""
        mock_driver = Mock()
        mock_wait = Mock()
        return TrainingPlanService(mock_driver, mock_wait)

    def test_is_folder_expanded_returns_true_when_expanded(self, service: TrainingPlanService) -> None:
        """Verifica que retorna True si tiene clase 'expanded'."""
        mock_folder = Mock()
        mock_folder.get_attribute.return_value = "coachTrainingPlanLibraryFolder expanded"
        
        with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
            mock_wait_instance = Mock()
            mock_webdriver_wait.return_value = mock_wait_instance
            mock_wait_instance.until.return_value = mock_folder
            
            result = service.is_folder_expanded("Testing runner")
            
            assert result is True

    def test_is_folder_expanded_returns_false_when_not_expanded(self, service: TrainingPlanService) -> None:
        """Verifica que retorna False si no tiene clase 'expanded'."""
        mock_folder = Mock()
        mock_folder.get_attribute.return_value = "coachTrainingPlanLibraryFolder"
        
        mock_expander = Mock()
        mock_expander.get_attribute.return_value = "expander"
        mock_folder.find_element.return_value = mock_expander
        
        with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
            mock_wait_instance = Mock()
            mock_webdriver_wait.return_value = mock_wait_instance
            mock_wait_instance.until.return_value = mock_folder
            
            result = service.is_folder_expanded("Testing runner")
            
            assert result is False


class TestFindAndClickTrainingPlan:
    """Tests para find_and_click_training_plan."""

    @pytest.fixture
    def service(self) -> TrainingPlanService:
        """Fixture que crea un servicio con mocks."""
        mock_driver = Mock()
        mock_wait = Mock()
        return TrainingPlanService(mock_driver, mock_wait)

    def test_find_and_click_training_plan_scrolls_and_clicks(self, service: TrainingPlanService) -> None:
        """Verifica que hace scroll y click en el plan encontrado."""
        mock_tile = Mock()
        
        with patch.object(service, 'expand_folder'):
            with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
                mock_wait_instance = Mock()
                mock_webdriver_wait.return_value = mock_wait_instance
                mock_wait_instance.until.return_value = mock_tile
                
                service.find_and_click_training_plan("Test Plan")
                
                service._driver.execute_script.assert_called()
                mock_tile.click.assert_called_once()


class TestSearchAthleteInDropdown:
    """Tests para search_athlete_in_dropdown."""

    @pytest.fixture
    def service(self) -> TrainingPlanService:
        """Fixture que crea un servicio con mocks."""
        mock_driver = Mock()
        mock_wait = Mock()
        return TrainingPlanService(mock_driver, mock_wait)

    def test_search_athlete_clears_and_types_name(self, service: TrainingPlanService) -> None:
        """Verifica que limpia el input y escribe el nombre."""
        mock_input = Mock()
        
        with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
            mock_wait_instance = Mock()
            mock_webdriver_wait.return_value = mock_wait_instance
            mock_wait_instance.until.return_value = mock_input
            
            service.search_athlete_in_dropdown("Luis Aragon")
            
            mock_input.clear.assert_called_once()
            mock_input.send_keys.assert_called_once_with("Luis Aragon")


class TestSetApplyDate:
    """Tests para set_apply_date."""

    @pytest.fixture
    def service(self) -> TrainingPlanService:
        """Fixture que crea un servicio con mocks."""
        mock_driver = Mock()
        mock_wait = Mock()
        return TrainingPlanService(mock_driver, mock_wait)

    def test_set_apply_date_formats_correctly(self, service: TrainingPlanService) -> None:
        """Verifica que formatea la fecha correctamente usando JavaScript."""
        mock_input = Mock()
        
        with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
            mock_wait_instance = Mock()
            mock_webdriver_wait.return_value = mock_wait_instance
            mock_wait_instance.until.return_value = mock_input
            
            test_date = date(2024, 9, 5)
            service.set_apply_date(test_date)
            
            # Verifica que se llama execute_script con el input y la fecha formateada
            service._driver.execute_script.assert_called_once()
            call_args = service._driver.execute_script.call_args
            # El segundo argumento posicional es el input element
            assert call_args[0][1] is mock_input
            # El tercer argumento es la fecha formateada M/D/YYYY
            assert call_args[0][2] == "9/5/2024"

    def test_set_apply_date_with_two_digit_month_and_day(self, service: TrainingPlanService) -> None:
        """Verifica formato con mes y dia de dos digitos usando JavaScript."""
        mock_input = Mock()
        
        with patch('app.infrastructure.driver.services.training_plan_service.WebDriverWait') as mock_webdriver_wait:
            mock_wait_instance = Mock()
            mock_webdriver_wait.return_value = mock_wait_instance
            mock_wait_instance.until.return_value = mock_input
            
            test_date = date(2024, 12, 25)
            service.set_apply_date(test_date)
            
            # Verifica formato 12/25/2024
            call_args = service._driver.execute_script.call_args
            assert call_args[0][2] == "12/25/2024"


class TestApplyTrainingPlan:
    """Tests para el metodo principal apply_training_plan."""

    @pytest.fixture
    def service(self) -> TrainingPlanService:
        """Fixture que crea un servicio con mocks."""
        mock_driver = Mock()
        mock_wait = Mock()
        return TrainingPlanService(mock_driver, mock_wait)

    def test_apply_training_plan_calls_all_steps_in_order(self, service: TrainingPlanService) -> None:
        """Verifica que se ejecutan todos los pasos en orden."""
        with patch.object(service, 'click_training_plans_tab') as mock_click_tab, \
             patch.object(service, 'find_and_click_training_plan') as mock_find_plan, \
             patch.object(service, '_wait_for_plan_modal', return_value=True) as mock_wait_modal, \
             patch.object(service, 'click_select_athletes_button') as mock_select_btn, \
             patch.object(service, 'search_athlete_in_dropdown') as mock_search, \
             patch.object(service, 'click_athlete_in_dropdown') as mock_click_athlete, \
             patch.object(service, 'close_athlete_dropdown') as mock_close_dropdown, \
             patch.object(service, 'set_apply_date') as mock_set_date, \
             patch.object(service, 'click_apply_button') as mock_apply, \
             patch.object(service, 'confirm_apply_modal') as mock_confirm, \
             patch.object(service, 'click_ok_confirmation') as mock_ok:
            
            result = service.apply_training_plan(
                plan_name="Test Plan",
                athlete_name="Luis Aragon",
                start_date=date(2024, 9, 5)
            )
            
            assert result is True
            mock_click_tab.assert_called_once()
            mock_find_plan.assert_called_once_with("Test Plan", 10)
            mock_wait_modal.assert_called_once()
            mock_select_btn.assert_called_once()
            mock_search.assert_called_once_with("Luis Aragon", 10)
            mock_click_athlete.assert_called_once_with("Luis Aragon", 10)
            mock_close_dropdown.assert_called_once()
            mock_set_date.assert_called_once_with(date(2024, 9, 5), 10)
            mock_apply.assert_called_once()
            mock_confirm.assert_called_once()
            mock_ok.assert_called_once()

    def test_apply_training_plan_raises_on_modal_timeout(self, service: TrainingPlanService) -> None:
        """Verifica que lanza excepcion si el modal no se abre."""
        from selenium.common.exceptions import TimeoutException
        
        with patch.object(service, 'click_training_plans_tab'), \
             patch.object(service, 'find_and_click_training_plan'), \
             patch.object(service, '_wait_for_plan_modal', return_value=False):
            
            with pytest.raises(TimeoutException):
                service.apply_training_plan(
                    plan_name="Test Plan",
                    athlete_name="Luis Aragon",
                    start_date=date(2024, 9, 5)
                )


class TestDateFormatting:
    """Tests para verificar el formato de fechas."""

    def test_date_format_single_digit_month(self) -> None:
        """Verifica formato con mes de un digito."""
        test_date = date(2024, 1, 15)
        date_str = f"{test_date.month}/{test_date.day}/{test_date.year}"
        assert date_str == "1/15/2024"

    def test_date_format_single_digit_day(self) -> None:
        """Verifica formato con dia de un digito."""
        test_date = date(2024, 10, 5)
        date_str = f"{test_date.month}/{test_date.day}/{test_date.year}"
        assert date_str == "10/5/2024"

    def test_date_format_double_digits(self) -> None:
        """Verifica formato con mes y dia de dos digitos."""
        test_date = date(2024, 12, 25)
        date_str = f"{test_date.month}/{test_date.day}/{test_date.year}"
        assert date_str == "12/25/2024"
