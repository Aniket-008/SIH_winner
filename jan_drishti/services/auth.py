"""Authentication and authorization system for JAN-DRISHTI AI.

Implements secure user authentication with role-based access control.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any


# User roles with permissions
ROLES = {
    "admin": {
        "name": "Administrator",
        "permissions": ["view", "analyze", "manage_users", "export", "configure"]
    },
    "auditor": {
        "name": "Auditor/Officer",
        "permissions": ["view", "analyze", "export"]
    },
    "viewer": {
        "name": "Viewer",
        "permissions": ["view"]
    }
}


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""
    pass


class AuthManager:
    """Manages user authentication and session tokens."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """Initialize auth manager with secret key for JWT-style tokens."""
        self.secret_key = secret_key or os.getenv("JAN_DRISHTI_SECRET_KEY") or self._generate_secret_key()
        self.token_expiry_hours = 8  # Session expires after 8 hours
        
    def _generate_secret_key(self) -> str:
        """Generate a random secret key for signing tokens."""
        return secrets.token_hex(32)
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash a password using PBKDF2 with salt.
        
        Returns:
            Tuple of (hashed_password, salt)
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Use PBKDF2 with 100,000 iterations
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return pwd_hash.hex(), salt
    
    def verify_password(self, password: str, hashed_password: str, salt: str) -> bool:
        """Verify a password against its hash."""
        pwd_hash, _ = self.hash_password(password, salt)
        return hmac.compare_digest(pwd_hash, hashed_password)
    
    def create_token(self, user_id: str, username: str, role: str) -> str:
        """Create a signed session token (JWT-style).
        
        Token format: base64(header.payload.signature)
        """
        issued_at = int(time.time())
        expires_at = issued_at + (self.token_expiry_hours * 3600)
        
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "iat": issued_at,
            "exp": expires_at
        }
        
        # Create token as JSON with signature
        payload_json = json.dumps(payload, separators=(',', ':'))
        signature = self._sign_payload(payload_json)
        
        # Encode to make URL-safe
        token_data = f"{payload_json}.{signature}"
        return self._base64_encode(token_data)
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a session token.
        
        Raises:
            AuthenticationError if token is invalid or expired
        """
        try:
            # Decode token
            token_data = self._base64_decode(token)
            
            # Split payload and signature
            if '.' not in token_data:
                raise AuthenticationError("Invalid token format")
            
            payload_json, provided_signature = token_data.rsplit('.', 1)
            
            # Verify signature
            expected_signature = self._sign_payload(payload_json)
            if not hmac.compare_digest(expected_signature, provided_signature):
                raise AuthenticationError("Invalid token signature")
            
            # Parse payload
            payload = json.loads(payload_json)
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                raise AuthenticationError("Token expired")
            
            return payload
            
        except (ValueError, json.JSONDecodeError) as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    def _sign_payload(self, payload_json: str) -> str:
        """Create HMAC signature for payload."""
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256
        )
        return signature.hexdigest()
    
    def _base64_encode(self, data: str) -> str:
        """URL-safe base64 encoding."""
        import base64
        return base64.urlsafe_b64encode(data.encode('utf-8')).decode('utf-8')
    
    def _base64_decode(self, data: str) -> str:
        """URL-safe base64 decoding."""
        import base64
        # Add padding if needed
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += '=' * padding
        return base64.urlsafe_b64decode(data.encode('utf-8')).decode('utf-8')
    
    def has_permission(self, role: str, permission: str) -> bool:
        """Check if a role has a specific permission."""
        role_config = ROLES.get(role)
        if not role_config:
            return False
        return permission in role_config["permissions"]
    
    def require_permission(self, token: str, permission: str) -> Dict[str, Any]:
        """Verify token and check permission.
        
        Returns user payload if authorized.
        Raises AuthenticationError or AuthorizationError if not.
        """
        payload = self.verify_token(token)
        role = payload.get("role", "")
        
        if not self.has_permission(role, permission):
            raise AuthorizationError(
                f"Role '{role}' does not have permission '{permission}'"
            )
        
        return payload


def create_default_users() -> list[Dict[str, Any]]:
    """Create default user accounts for initial setup.
    
    Returns list of user dictionaries ready for database insertion.
    """
    auth = AuthManager()
    
    users = []
    
    # Admin user
    admin_pwd_hash, admin_salt = auth.hash_password("admin123")
    users.append({
        "user_id": "admin001",
        "username": "admin",
        "password_hash": admin_pwd_hash,
        "salt": admin_salt,
        "role": "admin",
        "full_name": "System Administrator",
        "email": "admin@jandrishti.gov.in",
        "created_at": datetime.now().isoformat(),
        "is_active": True
    })
    
    # Auditor user
    auditor_pwd_hash, auditor_salt = auth.hash_password("auditor123")
    users.append({
        "user_id": "aud001",
        "username": "auditor",
        "password_hash": auditor_pwd_hash,
        "salt": auditor_salt,
        "role": "auditor",
        "full_name": "Government Auditor",
        "email": "auditor@jandrishti.gov.in",
        "created_at": datetime.now().isoformat(),
        "is_active": True
    })
    
    # Viewer user
    viewer_pwd_hash, viewer_salt = auth.hash_password("viewer123")
    users.append({
        "user_id": "view001",
        "username": "viewer",
        "password_hash": viewer_pwd_hash,
        "salt": viewer_salt,
        "role": "viewer",
        "full_name": "Report Viewer",
        "email": "viewer@jandrishti.gov.in",
        "created_at": datetime.now().isoformat(),
        "is_active": True
    })
    
    return users


def get_roles_info() -> Dict[str, Any]:
    """Return information about available roles and permissions."""
    return {
        "roles": ROLES,
        "permissions": {
            "view": "View reports and dashboards",
            "analyze": "Upload files and run analysis",
            "export": "Export reports and data",
            "manage_users": "Create and manage user accounts",
            "configure": "Change system configuration and thresholds"
        }
    }
