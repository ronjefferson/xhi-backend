from fastapi import FastAPI
from .database import engine, Base
from .routers import books, auth 

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router)
app.include_router(books.router)

@app.get("/")
def root():
    return {"message": "Epub Reader API is running"}