from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Run(Base):
    __tablename__ = "runs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    run_id     = Column(String, unique=True, nullable=False)
    issue_url  = Column(String, nullable=False)
    status     = Column(String, default="running")   # running | success | failed
    pr_url     = Column(String, nullable=True)
    error      = Column(Text,   nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    run_id     = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    status     = Column(String, nullable=True)


class CriticScore(Base):
    __tablename__ = "critic_scores"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    run_id       = Column(String, nullable=False)
    attempt      = Column(Integer, default=1)
    quality      = Column(Float, nullable=True)
    coverage     = Column(Float, nullable=True)
    security     = Column(Float, nullable=True)
    overall      = Column(Float, nullable=True)


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    issue_url   = Column(String, nullable=False)
    lesson      = Column(Text,   nullable=False)
    embedding   = Column(Text,   nullable=True)   # JSON-serialized vector
    created_at  = Column(DateTime, default=datetime.utcnow)