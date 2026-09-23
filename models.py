from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, date
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(128))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    last_login_date = Column(Date)
    is_admin = Column(Boolean, default=False)

    word_progress = relationship("WordProgress", back_populates="user")
    login_logs = relationship("LoginLog", back_populates="user")


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), unique=True, index=True)
    meaning = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class WordProgress(Base):
    __tablename__ = "word_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    word_id = Column(Integer, ForeignKey("words.id"))
    review_count = Column(Integer, default=0)
    next_review_date = Column(Date)
    last_reviewed_at = Column(DateTime)
    mastered = Column(Boolean, default=False)

    user = relationship("User", back_populates="word_progress")
    word = relationship("Word")


class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    login_at = Column(DateTime, default=datetime.utcnow)
    login_date = Column(Date)

    user = relationship("User", back_populates="login_logs")
