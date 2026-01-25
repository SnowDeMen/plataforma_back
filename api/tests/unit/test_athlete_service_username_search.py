"""
Tests unitarios para los metodos de busqueda por username de AthleteService.

Estos tests mockean el WebDriver de Selenium para probar la logica
de busqueda sin necesidad de un navegador real.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from app.infrastructure.driver.services.athlete_service import AthleteService


class TestAthleteServiceUsernameSearch:
    """Tests para metodos de busqueda por username."""
    
    @pytest.fixture
    def mock_driver(self):
        """Crea un mock del WebDriver."""
        driver = Mock()
        driver.current_url = "https://app.trainingpeaks.com/#calendar"
        driver.find_element = Mock()
        driver.find_elements = Mock(return_value=[])
        driver.execute_script = Mock()
        driver.get = Mock()
        return driver
    
    @pytest.fixture
    def mock_wait(self):
        """Crea un mock del WebDriverWait."""
        return Mock()
    
    @pytest.fixture
    def athlete_service(self, mock_driver, mock_wait):
        """Crea una instancia de AthleteService con mocks."""
        return AthleteService(mock_driver, mock_wait)
    
    # =========================================================================
    # Tests para navigate_to_home
    # =========================================================================
    
    def test_navigate_to_home_when_not_on_home(self, athlete_service, mock_driver, mock_wait):
        """Verifica que navega a #home si no esta ahi."""
        mock_driver.current_url = "https://app.trainingpeaks.com/#calendar"
        
        # Mock para que until retorne algo (simula que cargo la pagina)
        mock_wait.until = Mock(return_value=Mock())
        
        with patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw:
            mock_wdw.return_value.until = Mock(return_value=Mock())
            athlete_service.navigate_to_home()
        
        # Debe llamar a get con la URL de home
        mock_driver.get.assert_called_once()
        assert "#home" in mock_driver.get.call_args[0][0]
    
    def test_navigate_to_home_when_already_on_home(self, athlete_service, mock_driver, mock_wait):
        """Verifica que no navega si ya esta en #home."""
        mock_driver.current_url = "https://app.trainingpeaks.com/#home"
        
        with patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw:
            mock_wdw.return_value.until = Mock(return_value=Mock())
            athlete_service.navigate_to_home()
        
        # No debe llamar a get
        mock_driver.get.assert_not_called()
    
    # =========================================================================
    # Tests para get_athlete_name_from_tile
    # =========================================================================
    
    def test_get_athlete_name_from_tile_via_aria_label(self, athlete_service):
        """Verifica extraccion de nombre via aria-label."""
        mock_tile = Mock()
        mock_profile = Mock()
        mock_profile.get_attribute = Mock(return_value="Juan Perez")
        mock_tile.find_element = Mock(return_value=mock_profile)
        
        name = athlete_service.get_athlete_name_from_tile(mock_tile)
        
        assert name == "Juan Perez"
    
    def test_get_athlete_name_from_tile_via_typography(self, athlete_service):
        """Verifica extraccion de nombre via Typography cuando aria-label falla."""
        mock_tile = Mock()
        
        # Primera llamada falla (aria-label)
        # Segunda llamada exito (Typography)
        mock_typography = Mock()
        mock_typography.text = "Maria Garcia"
        
        def find_element_side_effect(by, selector):
            if "athleteProfileAndName" in selector:
                raise NoSuchElementException()
            return mock_typography
        
        mock_tile.find_element = Mock(side_effect=find_element_side_effect)
        
        name = athlete_service.get_athlete_name_from_tile(mock_tile)
        
        assert name == "Maria Garcia"
    
    def test_get_athlete_name_from_tile_returns_empty_on_failure(self, athlete_service):
        """Verifica que retorna string vacio si no encuentra nombre."""
        mock_tile = Mock()
        mock_tile.find_element = Mock(side_effect=NoSuchElementException())
        
        name = athlete_service.get_athlete_name_from_tile(mock_tile)
        
        assert name == ""
    
    # =========================================================================
    # Tests para get_username_from_modal
    # =========================================================================
    
    def test_get_username_from_modal_success(self, athlete_service, mock_driver):
        """Verifica extraccion de username del modal."""
        mock_label = Mock()
        mock_label.text = "juanperez123"
        mock_driver.find_element = Mock(return_value=mock_label)
        
        username = athlete_service.get_username_from_modal()
        
        assert username == "juanperez123"
    
    def test_get_username_from_modal_returns_empty_on_failure(self, athlete_service, mock_driver):
        """Verifica que retorna string vacio si no encuentra username."""
        mock_driver.find_element = Mock(side_effect=NoSuchElementException())
        
        username = athlete_service.get_username_from_modal()
        
        assert username == ""
    
    # =========================================================================
    # Tests para get_full_name_from_modal
    # =========================================================================
    
    def test_get_full_name_from_modal_success(self, athlete_service, mock_driver):
        """Verifica extraccion de nombre completo del modal."""
        mock_input = Mock()
        mock_input.get_attribute = Mock(return_value="Juan Alberto Perez")
        mock_driver.find_element = Mock(return_value=mock_input)
        
        full_name = athlete_service.get_full_name_from_modal()
        
        assert full_name == "Juan Alberto Perez"
    
    def test_get_full_name_from_modal_strips_whitespace(self, athlete_service, mock_driver):
        """Verifica que elimina espacios en blanco."""
        mock_input = Mock()
        mock_input.get_attribute = Mock(return_value="  Juan Perez  ")
        mock_driver.find_element = Mock(return_value=mock_input)
        
        full_name = athlete_service.get_full_name_from_modal()
        
        assert full_name == "Juan Perez"
    
    # =========================================================================
    # Tests para _search_in_current_group
    # =========================================================================
    
    def test_search_in_current_group_returns_not_found_when_no_tiles(self, athlete_service):
        """Verifica que retorna not found cuando no hay tiles."""
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[]):
            result = athlete_service._search_in_current_group("testuser", "My Athletes")
        
        assert result["found"] is False
        assert result["username"] == "testuser"
        assert result["tiles_checked"] == 0
    
    def test_search_in_current_group_finds_matching_username(self, athlete_service):
        """Verifica que encuentra el atleta correcto por username."""
        mock_tile = Mock()
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile]), \
             patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="Juan Perez"), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', return_value="juanperez123"), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="Juan Alberto Perez"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            result = athlete_service._search_in_current_group("juanperez123", "My Athletes")
        
        assert result["found"] is True
        assert result["username"] == "juanperez123"
        assert result["full_name"] == "Juan Alberto Perez"
        assert result["group"] == "My Athletes"
    
    def test_search_in_current_group_continues_on_non_matching_username(self, athlete_service):
        """Verifica que continua buscando si el username no coincide."""
        mock_tile1 = Mock()
        mock_tile2 = Mock()
        
        # Primer tile no coincide, segundo si
        usernames = iter(["otrousuario", "usuariobuscado"])
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile1, mock_tile2]), \
             patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="Nombre"), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', side_effect=lambda: next(usernames)), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="Nombre Encontrado"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            result = athlete_service._search_in_current_group("usuariobuscado", "Test Group")
        
        assert result["found"] is True
        assert result["tiles_checked"] == 2
    
    # =========================================================================
    # Tests para find_athlete_by_username
    # =========================================================================
    
    def test_find_athlete_by_username_found_in_first_group(self, athlete_service):
        """Verifica que retorna resultado cuando encuentra en primer grupo."""
        expected_result = {
            "found": True,
            "username": "testuser",
            "full_name": "Test User",
            "group": "My Athletes",
            "tiles_checked": 1
        }
        
        with patch.object(athlete_service, '_search_in_current_group', return_value=expected_result):
            result = athlete_service.find_athlete_by_username("testuser")
        
        assert result["found"] is True
        assert result["full_name"] == "Test User"
    
    def test_find_athlete_by_username_searches_other_groups_when_not_found(self, athlete_service):
        """Verifica que busca en otros grupos si no encuentra en el primero."""
        first_result = {
            "found": False,
            "username": "testuser",
            "full_name": "",
            "group": "My Athletes",
            "tiles_checked": 5
        }
        second_result = {
            "found": True,
            "username": "testuser",
            "full_name": "Test User Found",
            "group": "Another Group",
            "tiles_checked": 3
        }
        
        groups = [
            {"name": "My Athletes", "value": "1", "selected": True},
            {"name": "Another Group", "value": "2", "selected": False}
        ]
        
        search_results = iter([first_result, second_result])
        
        with patch.object(athlete_service, '_search_in_current_group', side_effect=lambda u, g, t=10: next(search_results)), \
             patch.object(athlete_service, 'get_available_groups', return_value=groups), \
             patch.object(athlete_service, 'select_group', return_value=True), \
             patch('time.sleep'):
            
            result = athlete_service.find_athlete_by_username("testuser")
        
        assert result["found"] is True
        assert result["full_name"] == "Test User Found"
        assert result["tiles_checked"] == 8  # 5 + 3
    
    def test_find_athlete_by_username_returns_not_found_after_all_groups(self, athlete_service):
        """Verifica que retorna not found despues de buscar en todos los grupos."""
        not_found_result = {
            "found": False,
            "username": "nonexistent",
            "full_name": "",
            "group": "",
            "tiles_checked": 2
        }
        
        groups = [
            {"name": "My Athletes", "value": "1", "selected": True},
            {"name": "Group B", "value": "2", "selected": False}
        ]
        
        with patch.object(athlete_service, '_search_in_current_group', return_value=not_found_result), \
             patch.object(athlete_service, 'get_available_groups', return_value=groups), \
             patch.object(athlete_service, 'select_group', return_value=True), \
             patch('time.sleep'):
            
            result = athlete_service.find_athlete_by_username("nonexistent")
        
        assert result["found"] is False


class TestAthleteServiceModalMethods:
    """Tests para metodos de manejo de modales."""
    
    @pytest.fixture
    def mock_driver(self):
        """Crea un mock del WebDriver."""
        return Mock()
    
    @pytest.fixture
    def mock_wait(self):
        """Crea un mock del WebDriverWait."""
        return Mock()
    
    @pytest.fixture
    def athlete_service(self, mock_driver, mock_wait):
        """Crea una instancia de AthleteService con mocks."""
        return AthleteService(mock_driver, mock_wait)
    
    def test_close_settings_modal_success(self, athlete_service, mock_driver):
        """Verifica cierre exitoso del modal."""
        mock_close = Mock()
        mock_driver.find_element = Mock(return_value=mock_close)
        mock_driver.execute_script = Mock()
        
        with patch('time.sleep'):
            result = athlete_service.close_settings_modal()
        
        assert result is True
        mock_driver.execute_script.assert_called_once()
    
    def test_close_settings_modal_returns_false_when_not_found(self, athlete_service, mock_driver):
        """Verifica que retorna False si no encuentra el boton de cerrar."""
        mock_driver.find_element = Mock(side_effect=NoSuchElementException())
        
        result = athlete_service.close_settings_modal()
        
        assert result is False
    
    def test_wait_for_settings_modal_success(self, athlete_service):
        """Verifica espera exitosa del modal."""
        with patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw:
            mock_wdw.return_value.until = Mock(return_value=Mock())
            result = athlete_service.wait_for_settings_modal()
        
        assert result is True
    
    def test_wait_for_settings_modal_timeout(self, athlete_service):
        """Verifica que retorna False en timeout."""
        with patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw:
            mock_wdw.return_value.until = Mock(side_effect=TimeoutException())
            result = athlete_service.wait_for_settings_modal()
        
        assert result is False
