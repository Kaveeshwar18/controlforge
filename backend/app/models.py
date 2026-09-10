from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from .database import Base


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    org_type = Column(String, nullable=False)  # plant | corporate
    parent_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    assets = relationship("Asset", back_populates="org")
    controls = relationship("Control", back_populates="org")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    # CISO | PLANT_MANAGER | OT_ENGINEER | EXTERNAL_AUDITOR | CORP_ADMIN
    title = Column(String, nullable=True)


class UserOrgAccess(Base):
    __tablename__ = "user_org_access"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    redacted = Column(Boolean, default=False)  # True for external auditors


class Account(Base):
    """Login credentials. Kept separate from `User` (which carries role and
    org access) so that authentication and authorisation stay distinct:
    proving who you are is not the same as deciding what you may see."""
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)  # bcrypt; never the raw password
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False)  # PLC, HMI, Historian, SIS, Workstation, Server, Switch
    zone = Column(String, nullable=False)  # IT | OT | DMZ
    criticality_scanner = Column(Integer, nullable=True)  # 1-5, source A
    criticality_cmdb = Column(Integer, nullable=True)     # 1-5, source B
    criticality_resolved = Column(Integer, nullable=True)  # set once conflict resolved / or auto if they match
    business_impact_weight = Column(Float, nullable=False)  # relative $ downtime exposure
    has_telemetry = Column(Boolean, default=True)  # False => no monitoring agent/feed at all

    org = relationship("Organization", back_populates="assets")


class Control(Base):
    __tablename__ = "controls"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)
    control_type = Column(String, nullable=False)
    scope_type = Column(String, nullable=False)  # asset | zone
    scope_asset_id = Column(String, ForeignKey("assets.id"), nullable=True)
    scope_zone = Column(String, nullable=True)
    status = Column(String, nullable=False)  # planned | in_progress | completed
    rollout_percentage = Column(Float, default=0.0)
    planned_date = Column(Date, nullable=True)
    completion_date = Column(Date, nullable=True)

    org = relationship("Organization", back_populates="controls")


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True, autoincrement=True)
    control_id = Column(String, ForeignKey("controls.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)  # automated_scan | manual_attestation | third_party_audit
    result = Column(String, nullable=False)  # pass | fail


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"
    id = Column(String, primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False)
    cve_ref = Column(String, nullable=False)
    cvss = Column(Float, nullable=False)
    discovered_date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # open | mitigated | accepted_risk | false_positive
    resolved_date = Column(Date, nullable=True)


class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False)
    severity = Column(String, nullable=False)  # low | medium | high | critical
    detected_date = Column(Date, nullable=False)
    resolved_date = Column(Date, nullable=True)
    root_cause = Column(Text, nullable=True)
    related_control_id = Column(String, ForeignKey("controls.id"), nullable=True)


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    issue_type = Column(String, nullable=False)  # conflict | missing_feed | stale_evidence | regression
    asset_id = Column(String, ForeignKey("assets.id"), nullable=True)
    control_id = Column(String, ForeignKey("controls.id"), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(String, default="open")  # open | resolved
    created_date = Column(Date, nullable=False)
    resolved_date = Column(Date, nullable=True)
    resolved_by = Column(String, nullable=True)


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    as_of_date = Column(Date, nullable=False)
    snapshot_type = Column(String, nullable=False)  # historical | target
    score_raw = Column(Float, nullable=False)
    score_normalized = Column(Float, nullable=False)
    method_version = Column(String, nullable=False)
