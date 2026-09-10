"""Secure database layer for JAN-DRISHTI AI.

Implements SQLite database with encrypted sensitive data and audit logging.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

from jan_drishti.services.auth import AuthManager, create_default_users


class DatabaseManager:
    """Manages SQLite database with security features."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database manager."""
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "jandrishti.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT NOT NULL,
                    full_name TEXT,
                    email TEXT,
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_active INTEGER DEFAULT 1,
                    CHECK (role IN ('admin', 'auditor', 'viewer'))
                )
            """)
            
            # Analysis runs table (stores uploaded analysis results)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    projects_analyzed INTEGER,
                    high_risk_count INTEGER,
                    critical_risk_count INTEGER,
                    summary_json TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Projects table (stores individual project analysis results)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT,
                    run_id TEXT,
                    project_name TEXT,
                    department TEXT,
                    district TEXT,
                    contractor TEXT,
                    sanctioned_amount REAL,
                    spent_amount REAL,
                    risk_score INTEGER,
                    fraud_score INTEGER,
                    risk_level TEXT,
                    findings_json TEXT,
                    PRIMARY KEY (project_id, run_id),
                    FOREIGN KEY (run_id) REFERENCES analysis_runs(run_id)
                )
            """)
            
            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    username TEXT,
                    action TEXT NOT NULL,
                    resource TEXT,
                    details TEXT,
                    ip_address TEXT,
                    success INTEGER DEFAULT 1
                )
            """)
            
            # Session tokens table (for token revocation)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    is_revoked INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_risk ON projects(risk_level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            
            # Check if users table is empty, if so create default users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            if user_count == 0:
                default_users = create_default_users()
                for user in default_users:
                    cursor.execute("""
                        INSERT INTO users (user_id, username, password_hash, salt, role, 
                                         full_name, email, created_at, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user["user_id"], user["username"], user["password_hash"],
                        user["salt"], user["role"], user["full_name"],
                        user["email"], user["created_at"], user["is_active"]
                    ))
    
    # User Management
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, password_hash, salt, role, full_name, 
                       email, created_at, last_login, is_active
                FROM users WHERE username = ? AND is_active = 1
            """, (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_last_login(self, user_id: str):
        """Update user's last login timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET last_login = ? WHERE user_id = ?
            """, (datetime.now().isoformat(), user_id))
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users (admin only)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, role, full_name, email, 
                       created_at, last_login, is_active
                FROM users ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    # Analysis Storage
    
    def save_analysis_run(
        self,
        run_id: str,
        user_id: str,
        username: str,
        report: Dict[str, Any]
    ):
        """Save analysis run and its projects to database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Save analysis run
            metadata = report.get("metadata", {})
            summary = report.get("summary", {})
            
            cursor.execute("""
                INSERT INTO analysis_runs 
                (run_id, user_id, username, source_file, uploaded_at, 
                 projects_analyzed, high_risk_count, critical_risk_count, summary_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                user_id,
                username,
                metadata.get("source_file", "unknown"),
                datetime.now().isoformat(),
                summary.get("projects_analyzed", 0),
                summary.get("high_risk_count", 0),
                summary.get("critical_risk_count", 0),
                json.dumps(summary)
            ))
            
            # Save individual projects
            for project_result in report.get("projects", []):
                project = project_result.get("project", {})
                cursor.execute("""
                    INSERT OR REPLACE INTO projects 
                    (project_id, run_id, project_name, department, district, contractor,
                     sanctioned_amount, spent_amount, risk_score, fraud_score, 
                     risk_level, findings_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project.get("project_id"),
                    run_id,
                    project.get("project_name"),
                    project.get("department"),
                    project.get("district"),
                    project.get("contractor"),
                    project.get("sanctioned_amount"),
                    project.get("spent_amount"),
                    project_result.get("risk_score"),
                    project_result.get("fraud_score"),
                    project_result.get("risk_level"),
                    json.dumps(project_result.get("findings", []))
                ))
    
    def get_analysis_history(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get analysis history, optionally filtered by user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute("""
                    SELECT run_id, user_id, username, source_file, uploaded_at,
                           projects_analyzed, high_risk_count, critical_risk_count
                    FROM analysis_runs
                    WHERE user_id = ?
                    ORDER BY uploaded_at DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT run_id, user_id, username, source_file, uploaded_at,
                           projects_analyzed, high_risk_count, critical_risk_count
                    FROM analysis_runs
                    ORDER BY uploaded_at DESC
                    LIMIT ?
                """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_high_risk_projects(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all high and critical risk projects across all analyses."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.project_id, p.project_name, p.department, p.district,
                       p.risk_score, p.fraud_score, p.risk_level,
                       a.username, a.uploaded_at
                FROM projects p
                JOIN analysis_runs a ON p.run_id = a.run_id
                WHERE p.risk_level IN ('High', 'Critical')
                ORDER BY p.risk_score DESC, a.uploaded_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # Audit Logging
    
    def log_action(
        self,
        action: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: bool = True
    ):
        """Log an action to the audit trail."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log 
                (timestamp, user_id, username, action, resource, details, ip_address, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                user_id,
                username,
                action,
                resource,
                details,
                ip_address,
                1 if success else 0
            ))
    
    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve audit log entries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if action:
                query += " AND action = ?"
                params.append(action)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # Database Statistics
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics for dashboard."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total analyses
            cursor.execute("SELECT COUNT(*) FROM analysis_runs")
            total_analyses = cursor.fetchone()[0]
            
            # Total projects analyzed
            cursor.execute("SELECT SUM(projects_analyzed) FROM analysis_runs")
            total_projects = cursor.fetchone()[0] or 0
            
            # High risk projects
            cursor.execute("""
                SELECT COUNT(*) FROM projects WHERE risk_level IN ('High', 'Critical')
            """)
            high_risk_projects = cursor.fetchone()[0]
            
            # Active users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_users = cursor.fetchone()[0]
            
            # Recent activity
            cursor.execute("""
                SELECT COUNT(*) FROM audit_log 
                WHERE timestamp > datetime('now', '-7 days')
            """)
            recent_actions = cursor.fetchone()[0]
            
            return {
                "total_analyses": total_analyses,
                "total_projects_analyzed": total_projects,
                "high_risk_projects": high_risk_projects,
                "active_users": active_users,
                "recent_actions_7days": recent_actions
            }
