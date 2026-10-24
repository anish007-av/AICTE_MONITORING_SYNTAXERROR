from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(db.Base):
    """User account with role-based access control."""

    __tablename__ = "users"

    ROLE_COMPLAINANT = "complainant"
    ROLE_INSTITUTIONAL_REVIEWER = "institutional_reviewer"
    ROLE_AICTE_OFFICER = "aicte_officer"
    ROLE_SUPER_ADMIN = "super_admin"
    ROLE_INSTITUTION_ADMIN = "institution_admin"
    ROLE_REVIEWER = "reviewer"

    ROLES = [
        ROLE_COMPLAINANT,
        ROLE_INSTITUTIONAL_REVIEWER,
        ROLE_AICTE_OFFICER,
        ROLE_SUPER_ADMIN,
        ROLE_INSTITUTION_ADMIN,
        ROLE_REVIEWER,
    ]

    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(120), nullable=False)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=ROLE_REVIEWER)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    institution = relationship("Institution", back_populates="users")
    assigned_complaints = relationship("Complaint", back_populates="assigned_reviewer", foreign_keys="Complaint.assigned_reviewer_id")
    filed_complaints = relationship("Complaint", back_populates="complainant_user", foreign_keys="Complaint.complainant_user_id")
    reviewed_overlaps = relationship("OverlapRelationship", back_populates="reviewer")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_complainant(self) -> bool:
        return self.role == self.ROLE_COMPLAINANT

    @property
    def is_institutional_reviewer(self) -> bool:
        return self.role in [self.ROLE_INSTITUTIONAL_REVIEWER, self.ROLE_INSTITUTION_ADMIN]

    @property
    def is_aicte_officer(self) -> bool:
        return self.role in [self.ROLE_AICTE_OFFICER, self.ROLE_SUPER_ADMIN]

    @property
    def is_super_admin(self) -> bool:
        return self.role in [self.ROLE_AICTE_OFFICER, self.ROLE_SUPER_ADMIN]

    @property
    def is_institution_admin(self) -> bool:
        return self.role in [self.ROLE_INSTITUTIONAL_REVIEWER, self.ROLE_INSTITUTION_ADMIN]

    @property
    def is_reviewer(self) -> bool:
        return self.role in [self.ROLE_AICTE_OFFICER, self.ROLE_REVIEWER, self.ROLE_SUPER_ADMIN]

    def role_title(self) -> str:
        mapping = {
            self.ROLE_COMPLAINANT: "Complainant / Student",
            self.ROLE_INSTITUTIONAL_REVIEWER: "Institutional Reviewer / Head",
            self.ROLE_AICTE_OFFICER: "AICTE / Government Officer",
            self.ROLE_SUPER_ADMIN: "AICTE / Government Officer",
            self.ROLE_INSTITUTION_ADMIN: "Institutional Reviewer / Head",
            self.ROLE_REVIEWER: "Complaint Reviewer",
        }
        return mapping.get(self.role, self.role.replace("_", " ").title())

    def to_dict(self):
        return {
            "id": self.id,
            "display_name": self.display_name,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "role_title": self.role_title(),
            "institution_id": self.institution_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"
