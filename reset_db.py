from app.database import engine
from app.models import Base
import app.models 

print("WARNING: This will delete all users, books, and transactions.")
print("Dropping all tables...")

Base.metadata.drop_all(bind=engine)

print("Creating new tables...")

Base.metadata.create_all(bind=engine)

print("Database is fresh and ready.")