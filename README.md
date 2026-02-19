# xHi-Reader (Backend)

The backend for managing eBooks, tracking reading progress, and syncing library across devices for xHi-Reader.

---

## Project Overview
- **Automated Metadata Extraction**: Instantly extracts titles, authors, and high-quality cover images when you upload EPUB or PDF files.
- **Smart File Management**: Uses hashing to keep your storage clean and free of duplicates.
- **Cloud-Sync Ready**: Stores reading progress (last page, percentage, and chapter) in a relational database for access across multiple devices.
- **Secure by Default**: Implements JWT (JSON Web Token) authentication and password hashing to keep your library private.

---

## Tech Stack

- **Language:** Python  
- **Framework:** FastAPI  
- **Database:** PostgreSQL  
- **Containerization:** Docker & Docker Compose  
- **ORM:** SQLAlchemy  

---

## Getting Started

### Prerequisites

Ensure you have the following installed:

- Docker  
- Docker Compose  

### Configuration

The backend uses environment variables for security. Copy the example template to create your local config:

```cp .env.example .env```

Then, open `.env` and fill in your database credentials and a secure `SECRET_KEY`.

### Launching the Project

Docker handles the full environment; you don’t need to install Python or PostgreSQL manually:

```docker-compose up --build -d```

### Verification

Once the containers are running, access the interactive API documentation at:

```http://localhost:8000/docs```

---

## Project Structure

    /app/models      # Database schemas and SQLAlchemy tables
    /app/routers     # API endpoints (Books, Users, Auth)
    /app/core        # Core logic for file parsing (PyMuPDF, EbookLib)
    /epub_data       # Persistent storage for book files and covers (Git-ignored)

---

## License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
