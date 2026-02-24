"""
AuditLogger - Sistema de logging estructurado para debugging.

Proporciona funciones simples para registrar logs de:
- API: Requests y responses de endpoints
- Session: Un archivo por sesion con detalle completo
- Chat: Mensajes de conversacion
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from loguru import logger


class AuditLogger:
    """
    Gestor de logs de auditoria para debugging.
    
    Crea y mantiene logs separados para:
    - api_logs/: Logs generales de la API por dia
    - session_logs/: Un log por cada sesion de entrenamiento
    
    Uso:
        # Al inicio de la app
        AuditLogger.initialize()
        
        # En un endpoint
        AuditLogger.log_request(session_id, "POST", "/chat/", {"message": "hola"})
        # ... procesar ...
        AuditLogger.log_response(session_id, "POST", "/chat/", 200, response_data)
    """
    
    # Rutas base para los logs
    BASE_LOG_DIR = Path("logs")
    API_LOG_DIR = BASE_LOG_DIR / "api_logs"
    SESSION_LOG_DIR = BASE_LOG_DIR / "session_logs"
    
    # Formatos de timestamp
    FILE_TIMESTAMP_FORMAT = "%Y-%m-%d"
    LOG_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
    
    # Loggers configurados por sesion
    _session_loggers: Dict[str, Any] = {}
    _session_files: Dict[str, Path] = {}
    _initialized: bool = False
    
    @classmethod
    def initialize(cls) -> None:
        """
        Inicializa las carpetas de logs.
        Debe llamarse al inicio de la aplicacion.
        """
        if cls._initialized:
            return
        
        # Crear directorios si no existen
        cls.API_LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger de API
        today = datetime.now().strftime(cls.FILE_TIMESTAMP_FORMAT)
        api_log_file = cls.API_LOG_DIR / f"api_{today}.log"
        
        logger.add(
            str(api_log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
            filter=lambda record: record["extra"].get("context") == "api",
            rotation="1 day",
            retention="30 days",
            level="DEBUG"
        )
        
        cls._initialized = True
        logger.info("AuditLogger inicializado")
    
    @classmethod
    def get_session_logger(cls, session_id: str, athlete_name: str = "unknown", resume: bool = False):
        """
        Obtiene o crea un logger para una sesion especifica.
        
        Args:
            session_id: ID de la sesion
            athlete_name: Nombre del atleta
            resume: Si True, es una sesion reanudada (no imprime el banner de inicio)
            
        Returns:
            Logger configurado para la sesion
        """
        if not cls._initialized:
            cls.initialize()
        
        if session_id not in cls._session_loggers:
            cls._create_session_logger(session_id, athlete_name, resume=resume)
        
        return cls._session_loggers[session_id]
    
    @classmethod
    def _create_session_logger(cls, session_id: str, athlete_name: str, resume: bool = False) -> None:
        """Crea un nuevo logger para una sesion."""
        # Limpiar nombre del atleta para usar en el nombre de archivo
        safe_athlete = athlete_name.replace(" ", "_").lower()
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        
        # Nombre del archivo: session_<atleta>_<fecha>_<hora>_<id>.log
        short_id = session_id[:8]
        log_file = cls.SESSION_LOG_DIR / f"session_{safe_athlete}_{date_str}_{time_str}_{short_id}.log"
        
        # Crear logger con contexto unico para esta sesion
        session_logger = logger.bind(session_id=session_id)
        
        # Agregar handler especifico para esta sesion
        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
            filter=lambda record, sid=session_id: record["extra"].get("session_id") == sid,
            level="DEBUG"
        )
        
        cls._session_loggers[session_id] = session_logger
        cls._session_files[session_id] = log_file
        
        # Log inicial de la sesion
        session_logger.info("=" * 60)
        if resume:
            session_logger.info("SESION REANUDADA")
        else:
            session_logger.info("SESION INICIADA")
        session_logger.info(f"Session ID: {session_id}")
        session_logger.info(f"Atleta: {athlete_name}")
        session_logger.info(f"Timestamp: {datetime.now().isoformat()}")
        session_logger.info("=" * 60)
    
    @classmethod
    def log_request(
        cls,
        session_id: str,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> None:
        """
        Registra una request de API.
        
        Llamar al inicio de un endpoint.
        
        Args:
            session_id: ID de la sesion
            method: Metodo HTTP (GET, POST, etc.)
            path: Path del endpoint
            body: Cuerpo de la request
            params: Parametros de query
        """
        if not cls._initialized:
            cls.initialize()
        
        timestamp = datetime.now().strftime(cls.LOG_TIMESTAMP_FORMAT)
        
        log_data = {
            "type": "REQUEST",
            "timestamp": timestamp,
            "method": method,
            "path": path
        }
        
        if body:
            log_data["body"] = body
        if params:
            log_data["params"] = params
        
        # Log en API log
        api_logger = logger.bind(context="api")
        api_logger.info(f"[{session_id[:8]}] REQUEST {method} {path}")
        
        # Log en session log si existe
        if session_id in cls._session_loggers:
            cls._session_loggers[session_id].info(
                f"REQUEST {method} {path}\n{json.dumps(log_data, indent=2, default=str)}"
            )
    
    @classmethod
    def log_response(
        cls,
        session_id: str,
        method: str,
        path: str,
        status_code: int,
        body: Optional[Dict] = None,
        duration_ms: Optional[float] = None
    ) -> None:
        """
        Registra una response de API.
        
        Llamar al final de un endpoint.
        
        Args:
            session_id: ID de la sesion
            method: Metodo HTTP
            path: Path del endpoint
            status_code: Codigo HTTP de respuesta
            body: Cuerpo de la respuesta
            duration_ms: Duracion en milisegundos
        """
        if not cls._initialized:
            cls.initialize()
        
        timestamp = datetime.now().strftime(cls.LOG_TIMESTAMP_FORMAT)
        
        log_data = {
            "type": "RESPONSE",
            "timestamp": timestamp,
            "method": method,
            "path": path,
            "status_code": status_code
        }
        
        if duration_ms:
            log_data["duration_ms"] = round(duration_ms, 2)
        if body:
            # Limitar tamaño del body en el log
            body_str = json.dumps(body, default=str)
            if len(body_str) > 1000:
                log_data["body"] = body_str[:1000] + "...[truncated]"
            else:
                log_data["body"] = body
        
        # Determinar nivel de log
        log_level = "info" if status_code < 400 else "warning" if status_code < 500 else "error"
        
        # Log en API log
        api_logger = logger.bind(context="api")
        log_func = getattr(api_logger, log_level)
        log_func(f"[{session_id[:8]}] RESPONSE {status_code} {method} {path}")
        
        # Log en session log si existe
        if session_id in cls._session_loggers:
            session_log_func = getattr(cls._session_loggers[session_id], log_level)
            session_log_func(
                f"RESPONSE {status_code} {method} {path}\n{json.dumps(log_data, indent=2, default=str)}"
            )
    
    @classmethod
    def log_chat(
        cls,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Registra un mensaje de chat.
        
        Args:
            session_id: ID de la sesion
            role: Rol del mensaje (user/assistant)
            content: Contenido del mensaje
            metadata: Metadatos adicionales
        """
        if session_id not in cls._session_loggers:
            return
        
        # Truncar contenido si es muy largo para el log
        display_content = content[:200] + "..." if len(content) > 200 else content
        
        cls._session_loggers[session_id].info(
            f"CHAT [{role.upper()}]: {display_content}"
        )
        
        # Log completo si el mensaje es largo
        if len(content) > 200:
            cls._session_loggers[session_id].debug(
                f"CHAT [{role.upper()}] FULL:\n{content}"
            )
    
    @classmethod
    def log_event(
        cls,
        session_id: str,
        event: str,
        details: Optional[Dict] = None
    ) -> None:
        """
        Registra un evento de sesion.
        
        Args:
            session_id: ID de la sesion
            event: Tipo de evento
            details: Detalles adicionales
        """
        if session_id not in cls._session_loggers:
            return
        
        log_data = {
            "type": "EVENT",
            "timestamp": datetime.now().strftime(cls.LOG_TIMESTAMP_FORMAT),
            "event": event
        }
        
        if details:
            log_data["details"] = details
        
        cls._session_loggers[session_id].info(
            f"EVENT: {event}\n{json.dumps(log_data, indent=2, default=str)}"
        )
    
    @classmethod
    def log_error(
        cls,
        session_id: str,
        error_type: str,
        message: str,
        details: Optional[Dict] = None
    ) -> None:
        """
        Registra un error.
        
        Args:
            session_id: ID de la sesion
            error_type: Tipo de error
            message: Mensaje de error
            details: Detalles adicionales
        """
        if session_id not in cls._session_loggers:
            # Log en API log si no hay session logger
            api_logger = logger.bind(context="api")
            api_logger.error(f"[{session_id[:8]}] ERROR {error_type}: {message}")
            return
        
        log_data = {
            "type": "ERROR",
            "timestamp": datetime.now().strftime(cls.LOG_TIMESTAMP_FORMAT),
            "error_type": error_type,
            "message": message
        }
        
        if details:
            log_data["details"] = details
        
        cls._session_loggers[session_id].error(
            f"ERROR {error_type}: {message}\n{json.dumps(log_data, indent=2, default=str)}"
        )
    
    @classmethod
    def close_session(cls, session_id: str) -> None:
        """
        Cierra el logger de una sesion.
        
        Args:
            session_id: ID de la sesion a cerrar
        """
        if session_id in cls._session_loggers:
            cls._session_loggers[session_id].info("=" * 60)
            cls._session_loggers[session_id].info("SESION FINALIZADA")
            cls._session_loggers[session_id].info(f"Timestamp: {datetime.now().isoformat()}")
            cls._session_loggers[session_id].info("=" * 60)
            del cls._session_loggers[session_id]
        
        if session_id in cls._session_files:
            del cls._session_files[session_id]


# Alias para uso mas simple
audit = AuditLogger
