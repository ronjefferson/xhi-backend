from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    books = relationship("Book", back_populates="owner")
    transactions = relationship("Transaction", back_populates="owner")
    progress = relationship("UserBookProgress", back_populates="user")

class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    author = Column(String, nullable=True)
    
    file_path = Column(String)
    cover_path = Column(String, nullable=True)
    unpacked_path = Column(String, nullable=True) # Path to the exploded folder
    file_hash = Column(String, index=True) 
    file_size = Column(Integer)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="books")
    
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    progress = relationship("UserBookProgress", back_populates="book", cascade="all, delete-orphan")

class Chapter(Base):
    __tablename__ = "chapters"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    order = Column(Integer)
    file_name = Column(String)
    size_bytes = Column(Integer) # Critical for calculating total pages
    
    book_id = Column(Integer, ForeignKey("books.id"))
    book = relationship("Book", back_populates="chapters")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    book_title = Column(String)
    file_size = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="transactions")

class UserBookProgress(Base):
    __tablename__ = "user_book_progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    book_id = Column(Integer, ForeignKey("books.id"))
    
    chapter_index = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)
    last_read_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="progress")
    book = relationship("Book", back_populates="progress")