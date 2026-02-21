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
    
    def test_search_by_username_in_group_returns_not_found_when_no_tiles(self, athlete_service):
        """Verifica que retorna not found cuando no hay tiles en el grupo."""
        initial_result = {
            "found": False,
            "username": "testuser",
            "full_name": "",
            "group": "My Athletes",
            "tiles_checked": 0
        }
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[]):
            result = athlete_service._search_by_username_in_group("testuser", "My Athletes", result=initial_result)
        
        assert result["found"] is False
        assert result["username"] == "testuser"
        assert result["tiles_checked"] == 0
    
    def test_search_by_username_in_group_finds_matching_username(self, athlete_service):
        """Verifica que encuentra el atleta correcto por username en busqueda exhaustiva."""
        mock_tile = Mock()
        initial_result = {
            "found": False,
            "username": "juanperez123",
            "full_name": "",
            "group": "My Athletes",
            "tiles_checked": 0
        }
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile]), \
             patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="Juan Perez"), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', return_value="juanperez123"), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="Juan Alberto Perez"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            result = athlete_service._search_by_username_in_group("juanperez123", "My Athletes", result=initial_result)
        
        assert result["found"] is True
        assert result["username"] == "juanperez123"
        assert result["full_name"] == "Juan Alberto Perez"
        assert result["group"] == "My Athletes"
    
    def test_search_by_username_in_group_continues_on_non_matching_username(self, athlete_service):
        """Verifica que continua buscando si el username no coincide en busqueda exhaustiva."""
        mock_tile1 = Mock()
        mock_tile2 = Mock()
        initial_result = {
            "found": False,
            "username": "usuariobuscado",
            "full_name": "",
            "group": "Test Group",
            "tiles_checked": 0
        }
        
        # Primer tile no coincide, segundo si
        usernames = iter(["otrousuario", "usuariobuscado"])
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile1, mock_tile2]), \
             patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="Nombre"), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', side_effect=lambda: next(usernames)), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="Nombre Encontrado"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            result = athlete_service._search_by_username_in_group("usuariobuscado", "Test Group", result=initial_result)
        
        assert result["found"] is True
        assert result["tiles_checked"] == 2
    
    def test_search_by_username_in_group_case_insensitive_match(self, athlete_service):
        """Verifica que la busqueda es case-insensitive en busqueda exhaustiva."""
        mock_tile = Mock()
        initial_result = {
            "found": False,
            "username": "johndoe",
            "full_name": "",
            "group": "My Athletes",
            "tiles_checked": 0
        }
        
        # El modal retorna "JohnDoe" pero buscamos "johndoe" (diferente case)
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile]), \
             patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="John Doe"), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', return_value="JohnDoe"), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="John Doe"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            # Buscar con lowercase debe encontrar el uppercase
            result = athlete_service._search_by_username_in_group("johndoe", "My Athletes", result=initial_result)
        
        assert result["found"] is True
        assert result["full_name"] == "John Doe"
    
    def test_search_by_username_in_group_case_insensitive_uppercase_search(self, athlete_service):
        """Verifica que buscar con MAYUSCULAS encuentra minusculas en busqueda exhaustiva."""
        mock_tile = Mock()
        initial_result = {
            "found": False,
            "username": "JOHNDOE",
            "full_name": "",
            "group": "My Athletes",
            "tiles_checked": 0
        }
        
        # El modal retorna "johndoe" pero buscamos "JOHNDOE"
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile]), \
             patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="John Doe"), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', return_value="johndoe"), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="John Doe"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            # Buscar con UPPERCASE debe encontrar el lowercase
            result = athlete_service._search_by_username_in_group("JOHNDOE", "My Athletes", result=initial_result)
        
        assert result["found"] is True
        assert result["full_name"] == "John Doe"
    
    # =========================================================================
    # Tests para find_athlete_by_username
    # =========================================================================
    
    def test_find_athlete_by_username_found_in_first_group(self, athlete_service):
        """Verifica que retorna resultado cuando encuentra en primer grupo (usando PASE 1)."""
        expected_result = {
            "found": True,
            "username": "testuser",
            "full_name": "Test User",
            "group": "My Athletes",
            "tiles_checked": 1
        }
        
        # Como pasamos expected_name, debe llamar a _search_by_name_in_group
        with patch.object(athlete_service, '_search_by_name_in_group', return_value=expected_result):
            result = athlete_service.find_athlete_by_username("testuser", expected_name="Test")
        
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
        
        def search_side_effect(**kwargs):
            return next(search_results)
        
        with patch.object(athlete_service, '_search_by_username_in_group', side_effect=search_side_effect), \
             patch.object(athlete_service, 'get_available_groups', return_value=groups), \
             patch.object(athlete_service, 'select_group', return_value=True), \
             patch('time.sleep'):
            
            result = athlete_service.find_athlete_by_username("testuser")
        
        assert result["found"] is True
        assert result["full_name"] == "Test User Found"
        # 5 iniciales en result + 3 del segundo grupo = 8
    
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
        
        with patch.object(athlete_service, '_search_by_username_in_group', return_value=not_found_result), \
             patch.object(athlete_service, 'get_available_groups', return_value=groups), \
             patch.object(athlete_service, 'select_group', return_value=True), \
             patch('time.sleep'):
            
            result = athlete_service.find_athlete_by_username("nonexistent")
        
        assert result["found"] is False


class TestAthleteServiceNameMatching:
    """Tests para metodos de comparacion y normalizacion de nombres."""
    
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
    
    # =========================================================================
    # Tests para _normalize_name
    # =========================================================================
    
    def test_normalize_name_lowercase(self, athlete_service):
        """Verifica que convierte a minusculas."""
        result = athlete_service._normalize_name("JUAN PEREZ")
        assert result == "juan perez"
    
    def test_normalize_name_removes_accents(self, athlete_service):
        """Verifica que remueve acentos."""
        result = athlete_service._normalize_name("José García Muñoz")
        assert result == "jose garcia munoz"
    
    def test_normalize_name_strips_whitespace(self, athlete_service):
        """Verifica que elimina espacios al inicio y final."""
        result = athlete_service._normalize_name("  Juan Perez  ")
        assert result == "juan perez"
    
    def test_normalize_name_collapses_multiple_spaces(self, athlete_service):
        """Verifica que colapsa multiples espacios a uno."""
        result = athlete_service._normalize_name("Juan   Alberto    Perez")
        assert result == "juan alberto perez"
    
    def test_normalize_name_empty_string(self, athlete_service):
        """Verifica que retorna string vacio para input vacio."""
        assert athlete_service._normalize_name("") == ""
        assert athlete_service._normalize_name(None) == ""
    
    def test_normalize_name_complex_case(self, athlete_service):
        """Verifica normalizacion compleja con acentos y espacios."""
        result = athlete_service._normalize_name("  MARÍA  JOSÉ   GONZÁLEZ  ")
        assert result == "maria jose gonzalez"
    
    # =========================================================================
    # Tests para _names_match (comparacion por primer nombre)
    # =========================================================================
    
    def test_names_match_same_first_name(self, athlete_service):
        """Verifica match cuando primer nombre es igual."""
        assert athlete_service._names_match("Juan Perez", "Juan Garcia") is True
        assert athlete_service._names_match("Juan", "Juan Alberto Perez") is True
    
    def test_names_match_different_first_name(self, athlete_service):
        """Verifica no match cuando primer nombre es diferente."""
        assert athlete_service._names_match("Juan Perez", "Maria Perez") is False
        assert athlete_service._names_match("Carlos", "Luis") is False
    
    def test_names_match_case_insensitive(self, athlete_service):
        """Verifica que la comparacion es case-insensitive."""
        assert athlete_service._names_match("JUAN Perez", "juan Garcia") is True
        assert athlete_service._names_match("maria", "MARIA GARCIA") is True
    
    def test_names_match_with_accents(self, athlete_service):
        """Verifica que ignora acentos en la comparacion."""
        assert athlete_service._names_match("José Perez", "Jose Garcia") is True
        assert athlete_service._names_match("María López", "Maria Hernandez") is True
    
    def test_names_match_empty_strings(self, athlete_service):
        """Verifica que retorna False para strings vacios."""
        assert athlete_service._names_match("", "Juan") is False
        assert athlete_service._names_match("Juan", "") is False
        assert athlete_service._names_match("", "") is False
    
    def test_names_match_single_name(self, athlete_service):
        """Verifica comparacion cuando solo hay un nombre."""
        assert athlete_service._names_match("Luis", "Luis Joaquin Perez Spindola") is True
        assert athlete_service._names_match("Luis Joaquin Perez Spindola", "Luis") is True
    
    def test_names_match_real_world_example(self, athlete_service):
        """Verifica con ejemplo del mundo real (TrainingPeaks)."""
        # Nombre en BD: "Luis Aragon"
        # Nombre en tile TP: "Luis Joaquin Perez Spindola"
        assert athlete_service._names_match("Luis Aragon", "Luis Joaquin Perez Spindola") is True
    
    # =========================================================================
    # Tests para _filter_tiles_by_name
    # =========================================================================
    
    def test_filter_tiles_by_name_finds_matching(self, athlete_service):
        """Verifica que encuentra tiles con primer nombre coincidente."""
        mock_tile1 = Mock()
        mock_tile2 = Mock()
        mock_tile3 = Mock()
        
        def get_name(tile):
            if tile == mock_tile1:
                return "Luis Joaquin Perez"
            elif tile == mock_tile2:
                return "Maria Garcia"
            else:
                return "Luis Hernandez"
        
        with patch.object(athlete_service, 'get_athlete_name_from_tile', side_effect=get_name):
            candidates = athlete_service._filter_tiles_by_name(
                [mock_tile1, mock_tile2, mock_tile3], 
                "Luis Aragon"
            )
        
        # Debe encontrar 2 candidatos (Luis Joaquin y Luis Hernandez)
        assert len(candidates) == 2
        assert candidates[0][0] == mock_tile1
        assert candidates[1][0] == mock_tile3
    
    def test_filter_tiles_by_name_no_matches(self, athlete_service):
        """Verifica que retorna lista vacia si no hay matches."""
        mock_tile = Mock()
        
        with patch.object(athlete_service, 'get_athlete_name_from_tile', return_value="Maria Garcia"):
            candidates = athlete_service._filter_tiles_by_name([mock_tile], "Luis Aragon")
        
        assert len(candidates) == 0
    
    def test_filter_tiles_by_name_empty_list(self, athlete_service):
        """Verifica que retorna lista vacia para lista de tiles vacia."""
        candidates = athlete_service._filter_tiles_by_name([], "Luis Aragon")
        assert len(candidates) == 0


class TestAthleteServiceOptimizedSearch:
    """Tests para busqueda optimizada con expected_name."""
    
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
    
    def test_search_by_name_in_group_finds_quickly(self, athlete_service):
        """Verifica que la busqueda optimizada encuentra al atleta rapidamente."""
        mock_tile = Mock()
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile]), \
             patch.object(athlete_service, '_filter_tiles_by_name', return_value=[(mock_tile, "Luis Perez")]), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', return_value="luisperez123"), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="Luis Alberto Perez"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            result = athlete_service._search_by_name_in_group(
                username="luisperez123",
                group_name="My Athletes",
                expected_name="Luis Aragon"
            )
        
        assert result["found"] is True
        assert result["full_name"] == "Luis Alberto Perez"
        assert result["tiles_checked"] == 1
    
    def test_search_by_name_in_group_skips_group_when_no_candidates(self, athlete_service):
        """Verifica que salta el grupo si no hay candidatos por nombre."""
        mock_tile = Mock()
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile]), \
             patch.object(athlete_service, '_filter_tiles_by_name', return_value=[]):  # No candidatos
            
            result = athlete_service._search_by_name_in_group(
                username="luisperez123",
                group_name="My Athletes",
                expected_name="Luis Aragon"
            )
        
        # No debe encontrar y no debe verificar ningun tile
        assert result["found"] is False
        assert result["tiles_checked"] == 0
        assert result["group"] == "My Athletes"
    
    def test_search_by_name_in_group_checks_only_candidates(self, athlete_service):
        """Verifica que solo verifica los candidatos filtrados."""
        mock_tile1 = Mock()
        mock_tile2 = Mock()
        mock_tile3 = Mock()
        
        # Solo el tile2 es candidato por nombre
        candidates = [(mock_tile2, "Luis Garcia")]
        
        with patch.object(athlete_service, 'get_athlete_tiles', return_value=[mock_tile1, mock_tile2, mock_tile3]), \
             patch.object(athlete_service, '_filter_tiles_by_name', return_value=candidates), \
             patch.object(athlete_service, 'click_athlete_settings_button', return_value=True), \
             patch.object(athlete_service, 'wait_for_settings_modal', return_value=True), \
             patch.object(athlete_service, 'get_username_from_modal', return_value="luisgarcia"), \
             patch.object(athlete_service, 'get_full_name_from_modal', return_value="Luis Garcia"), \
             patch.object(athlete_service, 'close_settings_modal', return_value=True):
            
            result = athlete_service._search_by_name_in_group(
                username="luisgarcia",
                group_name="My Athletes",
                expected_name="Luis Aragon"
            )
        
        # Debe encontrar y solo verificar 1 tile (el candidato)
        assert result["found"] is True
        assert result["tiles_checked"] == 1
    
    def test_find_athlete_passes_expected_name_to_search(self, athlete_service):
        """Verifica que find_athlete_by_username pasa expected_name a _search_by_name_in_group."""
        expected_result = {
            "found": True,
            "username": "testuser",
            "full_name": "Test User",
            "group": "My Athletes",
            "tiles_checked": 1
        }
        
        with patch.object(athlete_service, '_search_by_name_in_group', return_value=expected_result) as mock_search:
            result = athlete_service.find_athlete_by_username(
                username="testuser",
                expected_name="Test Name"
            )
        
        # Verificar que se llamo con expected_name
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["expected_name"] == "Test Name"
        assert result["found"] is True


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


class TestAthleteServiceClickAndVerification:
    """
    Tests para click_athlete_by_name y _verify_athlete_selected.
    
    Verifica:
    - Scroll al elemento antes del click
    - Fallback a JavaScript click
    - Verificacion post-click
    - Manejo de errores
    """
    
    @pytest.fixture
    def mock_driver(self):
        """Crea un mock del WebDriver."""
        driver = Mock()
        driver.execute_script = Mock()
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
    # Tests para _get_selected_athlete_name y _wait_for_athlete_selection
    # =========================================================================
    
    def test_verify_athlete_selected_success(self, athlete_service):
        """Verifica que retorna True cuando el nombre coincide."""
        with patch.object(athlete_service, '_get_selected_athlete_name', return_value="Luis Aragon"), \
             patch('time.sleep'):
            result = athlete_service._verify_athlete_selected("Luis Perez")
        
        # Debe retornar True porque el primer nombre (Luis) coincide
        assert result is True
    
    def test_verify_athlete_selected_name_mismatch(self, athlete_service):
        """Verifica que retorna False cuando el nombre no coincide."""
        with patch.object(athlete_service, '_get_selected_athlete_name', return_value="Maria Garcia"), \
             patch('time.sleep'):
            # Timeout de 0.5s para que el test sea rapido
            result = athlete_service._wait_for_athlete_selection("Luis Perez", timeout=1)
        
        # Debe retornar False porque primer nombre (Maria vs Luis) no coincide
        assert result is False
    
    def test_verify_athlete_selected_timeout(self, athlete_service):
        """Verifica que retorna False cuando no encuentra el elemento."""
        with patch.object(athlete_service, '_get_selected_athlete_name', return_value=""), \
             patch('time.sleep'):
            result = athlete_service._wait_for_athlete_selection("Luis Perez", timeout=1)
        
        assert result is False
    
    def test_verify_athlete_selected_exception(self, athlete_service, mock_driver):
        """Verifica que _get_selected_athlete_name maneja excepciones."""
        mock_driver.find_element = Mock(side_effect=Exception("Error"))
        
        result = athlete_service._get_selected_athlete_name()
        
        assert result == ""
    
    # =========================================================================
    # Tests para click_athlete_by_name
    # =========================================================================
    
    def test_click_athlete_by_name_scrolls_before_click(self, athlete_service, mock_driver):
        """Verifica que hace scroll al elemento antes del click."""
        mock_tile = Mock()
        mock_tile.is_displayed = Mock(return_value=True)
        mock_tile.is_enabled = Mock(return_value=True)
        mock_tile.click = Mock()
        
        # Simular que otro atleta esta seleccionado, luego cambia al esperado
        with patch.object(athlete_service, 'expand_all_athlete_libraries'), \
             patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw, \
             patch.object(athlete_service, '_get_selected_athlete_name', side_effect=["Otro", "Luis Aragon"]), \
             patch('time.sleep'):
            
            mock_wdw.return_value.until = Mock(return_value=mock_tile)
            athlete_service.click_athlete_by_name("Luis Aragon")
        
        # Verificar que se llamo scrollIntoView
        scroll_calls = [
            call for call in mock_driver.execute_script.call_args_list
            if 'scrollIntoView' in str(call)
        ]
        assert len(scroll_calls) > 0
    
    def test_click_athlete_by_name_uses_js_click_on_failure(self, athlete_service, mock_driver):
        """Verifica que usa JavaScript click cuando click normal falla."""
        mock_tile = Mock()
        mock_tile.is_displayed = Mock(return_value=True)
        mock_tile.is_enabled = Mock(return_value=True)
        mock_tile.click = Mock(side_effect=Exception("Click intercepted"))
        
        # Simular que otro atleta esta seleccionado, luego cambia al esperado
        with patch.object(athlete_service, 'expand_all_athlete_libraries'), \
             patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw, \
             patch.object(athlete_service, '_get_selected_athlete_name', side_effect=["Otro", "Luis Aragon"]), \
             patch('time.sleep'):
            
            mock_wdw.return_value.until = Mock(return_value=mock_tile)
            athlete_service.click_athlete_by_name("Luis Aragon")
        
        # Verificar que se llamo execute_script con el tile (JS click)
        js_click_calls = [
            call for call in mock_driver.execute_script.call_args_list
            if 'click()' in str(call) or (len(call[0]) > 0 and '.click()' in str(call[0][0]))
        ]
        assert len(js_click_calls) > 0
    
    def test_click_athlete_by_name_raises_on_verification_failure(self, athlete_service, mock_driver):
        """Verifica que lanza excepcion si la verificacion falla."""
        from app.shared.exceptions.domain import AthleteNotFoundInTPException
        
        mock_tile = Mock()
        mock_tile.is_displayed = Mock(return_value=True)
        mock_tile.is_enabled = Mock(return_value=True)
        mock_tile.click = Mock()
        
        # Simular que siempre muestra otro atleta (nunca cambia al esperado)
        with patch.object(athlete_service, 'expand_all_athlete_libraries'), \
             patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw, \
             patch.object(athlete_service, '_get_selected_athlete_name', return_value="Otro Atleta"), \
             patch('time.sleep'), \
             pytest.raises(AthleteNotFoundInTPException):
            
            mock_wdw.return_value.until = Mock(return_value=mock_tile)
            athlete_service.click_athlete_by_name("Luis Aragon")
    
    def test_click_athlete_by_name_success_flow(self, athlete_service, mock_driver):
        """Verifica el flujo completo exitoso."""
        mock_tile = Mock()
        mock_tile.is_displayed = Mock(return_value=True)
        mock_tile.is_enabled = Mock(return_value=True)
        mock_tile.click = Mock()
        
        # Simular que otro atleta esta seleccionado, luego cambia al esperado
        with patch.object(athlete_service, 'expand_all_athlete_libraries'), \
             patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw, \
             patch.object(athlete_service, '_get_selected_athlete_name', side_effect=["Otro", "Luis Aragon"]), \
             patch('time.sleep'):
            
            mock_wdw.return_value.until = Mock(return_value=mock_tile)
            # No debe lanzar excepcion
            athlete_service.click_athlete_by_name("Luis Aragon")
        
        # Verificar que se llamo click
        mock_tile.click.assert_called_once()
    
    def test_click_athlete_by_name_skips_click_if_already_selected(self, athlete_service, mock_driver):
        """Verifica que no hace click si el atleta ya esta seleccionado."""
        mock_tile = Mock()
        mock_tile.is_displayed = Mock(return_value=True)
        mock_tile.is_enabled = Mock(return_value=True)
        mock_tile.click = Mock()
        
        # Simular que el atleta ya esta seleccionado
        with patch.object(athlete_service, 'expand_all_athlete_libraries'), \
             patch('app.infrastructure.driver.services.athlete_service.WebDriverWait') as mock_wdw, \
             patch.object(athlete_service, '_get_selected_athlete_name', return_value="Luis Aragon"), \
             patch('time.sleep'):
            
            mock_wdw.return_value.until = Mock(return_value=mock_tile)
            athlete_service.click_athlete_by_name("Luis Aragon")
        
        # NO debe llamar click porque ya estaba seleccionado
        mock_tile.click.assert_not_called()
