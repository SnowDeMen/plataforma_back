"""
Utilidades de seguridad: autenticación, autorización, hashing.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.shared.exceptions.auth import InvalidCredentialsException, TokenExpiredException


# Contexto para hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityService:
    """Servicio para operaciones de seguridad."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Genera un hash de la contraseña.
        
        Args:
            password: Contraseña en texto plano
            
        Returns:
            str: Hash de la contraseña
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verifica si una contraseña coincide con su hash.
        
        Args:
            plain_password: Contraseña en texto plano
            hashed_password: Hash de la contraseña
            
        Returns:
            bool: True si coinciden, False en caso contrario
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Crea un token JWT de acceso.
        
        Args:
            data: Datos a incluir en el token
            expires_delta: Tiempo de expiración personalizado
            
        Returns:
            str: Token JWT codificado
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        return encoded_jwt
    
    @staticmethod
    def decode_access_token(token: str) -> Dict[str, Any]:
        """
        Decodifica y valida un token JWT.
        
        Args:
            token: Token JWT a decodificar
            
        Returns:
            Dict[str, Any]: Datos del token decodificado
            
        Raises:
            InvalidCredentialsException: Si el token es inválido
            TokenExpiredException: Si el token ha expirado
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpiredException()
        except JWTError:
            raise InvalidCredentialsException()


# Instancia global del servicio de seguridad
security_service = SecurityService()

