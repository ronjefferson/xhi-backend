# xHi-Reader (Backend)

A Dockerized FastAPI backend for xHi-Reader that parses uploaded eBooks, extracts metadata, and securely stores library data.

---

## Project Overview
- **Automated Metadata Extraction**: Instantly extracts titles, authors, and high-quality cover images when you upload EPUB or PDF files.
- **Smart File Management**: Uses hashing to keep your storage clean and free of duplicates.
- **Cloud-Sync Ready**: Stores reading progress (last page, percentage, and chapter) in a relational database for access across multiple devices.
- **Secure by Default**: Implements JWT (JSON Web Token) authentication and password hashing to keep your library private.

---

## Tech Stack

* [![Python][Python.org]][Python-url]
* [![FastAPI][FastAPI.io]][FastAPI-url]
* [![PostgreSQL][PostgreSQL.org]][PostgreSQL-url]
* [![Docker][Docker.com]][Docker-url]
* [![SQLAlchemy][SQLAlchemy.org]][SQLAlchemy-url]

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

[Python.org]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/

[FastAPI.io]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[FastAPI-url]: https://fastapi.tiangolo.com/

[PostgreSQL.org]: https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white
[PostgreSQL-url]: https://www.postgresql.org/

[Docker.com]: https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white
[Docker-url]: https://www.docker.com/

[SQLAlchemy.org]: https://img.shields.io/badge/SQLAlchemy-000000?style=for-the-badge&logo=sqlalchemy&logoColor=white
[SQLAlchemy-url]: https://www.sqlalchemy.org/
