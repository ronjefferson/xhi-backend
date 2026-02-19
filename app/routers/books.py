import shutil
import os
import hashlib
import zipfile
from urllib.parse import unquote
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request, Query, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models, schemas, database, auth

router = APIRouter(tags=["Books"])

# --- CONFIG ---
env_path = os.getenv("STORAGE_PATH")
STORAGE_ROOT = Path(env_path) if env_path else Path(os.path.expanduser("~")) / "EpubReader Storage"
OBJECTS_DIR = STORAGE_ROOT / "objects"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
MAX_STORAGE_BYTES = 1024 * 1024 * 1024 

# --- READER CSS/JS ---
READER_CSS = """
body { margin: 0; padding: 20px; font-family: sans-serif; line-height: 1.6; }
img, image { max-width: 100%; height: auto; display: block; margin: 10px auto; }
#viewer { padding-bottom: 50px; }
"""
READER_JS = """
console.log("Reader JS Loaded");
"""

# --- AUTH ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def get_current_user_hybrid(
    token: Optional[str] = Query(None), 
    header_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    actual_token = token if token else header_token
    if not actual_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth.get_user_from_token_string(actual_token, db)

# --- HELPERS ---
def get_user_storage_usage(user_id: int, db: Session) -> int:
    total = db.query(func.sum(models.Book.file_size)).filter(models.Book.owner_id == user_id).scalar()
    return total if total else 0

def calculate_file_hash_and_size(file: UploadFile):
    sha256_hash = hashlib.sha256()
    size = 0
    file.file.seek(0)
    for byte_block in iter(lambda: file.file.read(4096), b""):
        sha256_hash.update(byte_block)
        size += len(byte_block)
    file.file.seek(0)
    return sha256_hash.hexdigest(), size

# --- NEW COVER LOGIC (Mirrors Frontend) ---
def extract_file_from_zip(zip_ref, internal_path: str, output_path: Path):
    """Helper to extract a single file from zip to disk."""
    try:
        # Normalize path (remove leading slashes, handle windows/linux separators)
        internal_path = internal_path.lstrip('/')
        # Find the file in the zip (case insensitive search if needed)
        try:
            zip_ref.extract(internal_path, path=output_path.parent)
            # Move it to the exact output_path name we want
            extracted = output_path.parent / internal_path
            if extracted.resolve() != output_path.resolve():
                shutil.move(str(extracted), str(output_path))
                # Cleanup empty dirs created by extract
                if extracted.parent != output_path.parent:
                    shutil.rmtree(str(output_path.parent / internal_path.split('/')[0]))
        except KeyError:
            # Fallback: case insensitive search
            for name in zip_ref.namelist():
                if name.lower() == internal_path.lower():
                    zip_ref.extract(name, path=output_path.parent)
                    extracted = output_path.parent / name
                    shutil.move(str(extracted), str(output_path))
                    break
    except Exception as e:
        print(f"Failed to extract {internal_path}: {e}")

def find_epub_cover(epub_path: Path, unpack_dir: Path) -> Optional[str]:
    """
    Robust cover extraction mirroring Flutter logic:
    1. Parse META-INF/container.xml -> OPF
    2. Parse OPF -> <meta name="cover"> -> item href
    3. Fallback: Scan first page for <svg>/<img>
    4. Fallback: Scan for 'cover.jpg' in filenames
    """
    cover_save_path = unpack_dir / "cover.jpg" # We will save whatever we find as cover.jpg or .png

    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            
            # --- PLAN A: The "Official" Metadata Way (Dart Logic) ---
            try:
                # 1. Read Container.xml
                with z.open('META-INF/container.xml') as f:
                    soup = BeautifulSoup(f, 'xml')
                    rootfile = soup.find('rootfile')
                    if rootfile:
                        opf_path = rootfile.get('full-path')
                        
                        # 2. Read OPF
                        with z.open(opf_path) as opf:
                            opf_soup = BeautifulSoup(opf, 'xml')
                            
                            # 3. Look for <meta name="cover" content="ID">
                            cover_id = None
                            meta = opf_soup.find('meta', attrs={'name': 'cover'})
                            if meta:
                                cover_id = meta.get('content')
                            
                            # 4. Find the Item with that ID
                            if cover_id:
                                item = opf_soup.find('item', attrs={'id': cover_id})
                                if item:
                                    href = item.get('href')
                                    if href:
                                        # Resolve path relative to OPF location
                                        # e.g. OPF is in OEBPS/content.opf, href is images/cover.jpg
                                        # Result: OEBPS/images/cover.jpg
                                        opf_dir = os.path.dirname(opf_path)
                                        full_path = os.path.join(opf_dir, unquote(href)).replace('\\', '/')
                                        
                                        # Extract and Return
                                        with z.open(full_path) as img_in:
                                            with open(cover_save_path, "wb") as img_out:
                                                shutil.copyfileobj(img_in, img_out)
                                        return str(cover_save_path)
            except Exception as e:
                print(f"Plan A (Metadata) failed: {e}")

            # --- PLAN B: The "First Page" Visual Scan (Backup) ---
            # (Requires reading the epub with ebooklib for easy spine access)
            try:
                book = epub.read_epub(str(epub_path))
                if len(book.spine) > 0:
                    item_id = book.spine[0][0]
                    page_item = book.get_item_with_id(item_id)
                    if page_item:
                        soup = BeautifulSoup(page_item.get_content(), 'html.parser')
                        img_src = None
                        
                        # Find <image> (SVG) or <img>
                        svg = soup.find('image')
                        if svg: img_src = svg.get('xlink:href') or svg.get('href')
                        
                        if not img_src:
                            img = soup.find('img')
                            if img: img_src = img.get('src')

                        if img_src:
                            # Clean path
                            target = unquote(img_src.split('/')[-1])
                            
                            # Find matching file in zip
                            for name in z.namelist():
                                if name.endswith(target):
                                    with z.open(name) as img_in:
                                        with open(cover_save_path, "wb") as img_out:
                                            shutil.copyfileobj(img_in, img_out)
                                    return str(cover_save_path)
            except Exception as e:
                print(f"Plan B (First Page) failed: {e}")

            # --- PLAN C: Filename Guessing (Last Resort) ---
            for name in z.namelist():
                lower = name.lower()
                if 'cover' in lower and (lower.endswith('.jpg') or lower.endswith('.png')):
                    with z.open(name) as img_in:
                        with open(cover_save_path, "wb") as img_out:
                            shutil.copyfileobj(img_in, img_out)
                    return str(cover_save_path)

    except Exception as e:
        print(f"Cover extraction fatal error: {e}")
    
    return None

def unpack_and_parse_epub(epub_path: Path, vault_path: Path) -> Tuple[List[dict], Optional[str]]:
    try:
        # 1. Standard EbookLib parsing for Text/Chapters
        book = epub.read_epub(str(epub_path))
        chapters_data = []
        unpacked_dir = vault_path / "unpacked"
        images_dir = unpacked_dir / "images"
        unpacked_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        # 2. Extract Images for reading
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                # Store all images in one flat 'images' folder
                image_path = images_dir / item.get_name().split('/')[-1]
                with open(image_path, "wb") as f: f.write(item.get_content())

        # 3. Extract Cover (Using NEW Logic)
        cover_path = find_epub_cover(epub_path, vault_path)

        # 4. Process Chapters
        for i, item_id in enumerate(book.spine):
            item = book.get_item_with_id(item_id[0])
            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT: continue
            
            content = item.get_content().decode('utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Simple rewrite during parse
            for img in soup.find_all('img'):
                if img.get('src'): img['src'] = f"images/{img['src'].split('/')[-1]}"

            chapter_filename = f"chapter_{i}.html"
            with open(unpacked_dir / chapter_filename, "w", encoding='utf-8') as f:
                f.write(str(soup))
            
            title = f"Chapter {i+1}"
            header = soup.find(['h1', 'h2', 'h3'])
            if header: title = header.get_text()[:100]

            chapters_data.append({
                "title": title, 
                "file_name": chapter_filename, 
                "order": i, 
                "size_bytes": len(str(soup).encode('utf-8'))
            })
        return chapters_data, cover_path
    except Exception as e:
        print(f"Error Parsing: {e}")
        return [], None

# --- ENDPOINTS ---
@router.post("/books/", response_model=schemas.BookResponse)
async def upload_book(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    if not file.filename.lower().endswith(('.epub', '.pdf')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_hash, file_size = calculate_file_hash_and_size(file)
    if get_user_storage_usage(current_user.id, db) + file_size > MAX_STORAGE_BYTES:
        raise HTTPException(status_code=400, detail="Storage limit exceeded")

    # Deduplication Check
    if db.query(models.Book).filter(models.Book.owner_id == current_user.id, models.Book.file_hash == file_hash).first():
        raise HTTPException(status_code=400, detail="Book already exists")

    vault_path = OBJECTS_DIR / file_hash
    final_file_path = str(vault_path / file.filename)
    chapters_data = []
    final_cover_path = None
    final_unpacked_path = None

    # Storage Logic
    if vault_path.exists():
        # Reuse existing file
        existing = db.query(models.Book).filter(models.Book.file_hash == file_hash).first()
        if existing:
            final_file_path = existing.file_path
            final_cover_path = existing.cover_path
            final_unpacked_path = existing.unpacked_path
            src_chapters = db.query(models.Chapter).filter(models.Chapter.book_id == existing.id).all()
            for c in src_chapters:
                chapters_data.append({"title": c.title, "file_name": c.file_name, "order": c.order, "size_bytes": c.size_bytes})
    else:
        # New Upload
        vault_path.mkdir(parents=True, exist_ok=True)
        try:
            with open(final_file_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            final_unpacked_path = str(vault_path / "unpacked")
            
            if file.filename.endswith('.epub'):
                chapters_data, final_cover_path = unpack_and_parse_epub(Path(final_file_path), vault_path)
            elif file.filename.endswith('.pdf'):
                doc = fitz.open(final_file_path)
                if len(doc) > 0:
                    pix = doc.load_page(0).get_pixmap()
                    c_path = vault_path / "cover.png"
                    pix.save(c_path)
                    final_cover_path = str(c_path)
        except Exception as e:
            shutil.rmtree(vault_path)
            print(f"Upload failed: {e}")
            raise HTTPException(status_code=500, detail="Processing failed")

    new_book = models.Book(
        title=file.filename, file_path=final_file_path, cover_path=final_cover_path,
        unpacked_path=final_unpacked_path, file_hash=file_hash, file_size=file_size,
        owner_id=current_user.id
    )
    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    for c in chapters_data:
        db.add(models.Chapter(title=c['title'], order=c['order'], file_name=c['file_name'], size_bytes=c['size_bytes'], book_id=new_book.id))
    db.commit()

    return new_book

@router.delete("/books/{book_id}")
def delete_book(book_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    book = db.query(models.Book).filter(models.Book.id == book_id, models.Book.owner_id == current_user.id).first()
    if not book: raise HTTPException(status_code=404)
    
    file_hash = book.file_hash
    db.delete(book)
    db.commit()
    
    if db.query(models.Book).filter(models.Book.file_hash == file_hash).count() == 0:
        if (OBJECTS_DIR / file_hash).exists(): shutil.rmtree(OBJECTS_DIR / file_hash)
    
    return {"detail": "Deleted"}

@router.get("/books/", response_model=List[schemas.BookResponse])
def read_books(current_user: models.User = Depends(auth.get_current_user)):
    return current_user.books

@router.get("/books/{book_id}/cover")
def get_cover(book_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    book = db.query(models.Book).filter(models.Book.id == book_id, models.Book.owner_id == current_user.id).first()
    if not book or not book.cover_path: raise HTTPException(status_code=404)
    
    path = Path(book.cover_path)
    if not path.exists(): raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path)

@router.get("/books/{book_id}/download")
def download_book(
    book_id: int, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(database.get_db)
):
    book = db.query(models.Book).filter(models.Book.id == book_id, models.Book.owner_id == current_user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    file_path = Path(book.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing from server")
        
    return FileResponse(
        path=file_path, 
        filename=book.title, 
        media_type="application/epub+zip"
    )

# --- READER ENDPOINTS ---
@router.get("/books/{book_id}/manifest")
def get_manifest(book_id: int, request: Request, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    book = db.query(models.Book).filter(models.Book.id == book_id, models.Book.owner_id == current_user.id).first()
    if not book: raise HTTPException(status_code=404)
    
    chapters = db.query(models.Chapter).filter(models.Chapter.book_id == book_id).order_by(models.Chapter.order).all()
    manifest = []
    base_url = str(request.base_url).rstrip("/")
    
    for c in chapters:
        manifest.append({
            "index": c.order, "title": c.title, "sizeBytes": c.size_bytes,
            "url": f"{base_url}/books/{book_id}/content/{c.id}"
        })
    return {"bookId": str(book.id), "title": book.title, "chapters": manifest}

@router.api_route("/books/{book_id}/content/{chapter_id}", methods=["GET", "HEAD"], response_class=HTMLResponse)
def get_content(
    book_id: int, chapter_id: int, request: Request,
    current_user: models.User = Depends(get_current_user_hybrid),
    token: Optional[str] = Query(None), header_token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    if request.method == "HEAD": return HTMLResponse("")
    active_token = token if token else header_token
    
    chapter = db.query(models.Chapter).filter(models.Chapter.id == chapter_id).first()
    if not chapter or chapter.book.owner_id != current_user.id: raise HTTPException(status_code=404)

    path = Path(chapter.book.unpacked_path) / chapter.file_name
    if not path.exists(): raise HTTPException(status_code=404)

    with open(path, "r", encoding='utf-8') as f: soup = BeautifulSoup(f.read(), 'html.parser')
    
    if not soup.find('meta', attrs={'name': 'viewport'}):
        soup.insert(0, BeautifulSoup('<meta name="viewport" content="width=device-width, initial-scale=1.0">', 'html.parser'))
    soup.head.append(BeautifulSoup(f'<style>{READER_CSS}</style>', 'html.parser'))
    soup.body.append(BeautifulSoup(f'<script>{READER_JS}</script>', 'html.parser'))
    
    viewer = soup.new_tag('div', id="viewer")
    for child in list(soup.body.contents):
        if child.name != 'script': viewer.append(child.extract())
    soup.body.insert(0, viewer)

    base = str(request.base_url).rstrip("/")
    
    # Image Injection
    for img in soup.find_all('img'):
        if img.get('src') and not img['src'].startswith('http'):
            clean = img['src'].split('/')[-1]
            img['src'] = f"{base}/books/{book_id}/images/{clean}?token={active_token}"

    for img in soup.find_all('image'):
        href = img.get('xlink:href') or img.get('href')
        if href and not href.startswith('http'):
            clean = href.split('/')[-1]
            new_url = f"{base}/books/{book_id}/images/{clean}?token={active_token}"
            if img.has_attr('xlink:href'): img['xlink:href'] = new_url
            else: img['href'] = new_url
            
    return str(soup)

@router.get("/books/{book_id}/images/{name}")
def get_image(
    book_id: int, name: str, 
    current_user: models.User = Depends(get_current_user_hybrid), 
    db: Session = Depends(database.get_db)
):
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book or book.owner_id != current_user.id: raise HTTPException(status_code=403)
    
    images_dir = Path(book.unpacked_path) / "images"
    safe_filename = os.path.basename(name)
    target_path = images_dir / safe_filename

    if not target_path.exists(): raise HTTPException(status_code=404, detail="Image not found")
    
    try:
        if not str(target_path.resolve()).startswith(str(images_dir.resolve())):
             raise HTTPException(status_code=403, detail="Illegal path traversal")
    except Exception:
         raise HTTPException(status_code=404)

    return FileResponse(target_path)

# --- PROGRESS ---
@router.get("/books/{book_id}/progress", response_model=schemas.ProgressResponse)
def get_progress(book_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    prog = db.query(models.UserBookProgress).filter(models.UserBookProgress.user_id==current_user.id, models.UserBookProgress.book_id==book_id).first()
    if not prog: return {"book_id": book_id, "chapter_index": 0, "progress_percent": 0.0, "last_read_at": datetime.utcnow()}
    return prog

@router.put("/books/{book_id}/progress")
def update_progress(book_id: int, update: schemas.ProgressUpdate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    prog = db.query(models.UserBookProgress).filter(models.UserBookProgress.user_id==current_user.id, models.UserBookProgress.book_id==book_id).first()
    if not prog:
        prog = models.UserBookProgress(user_id=current_user.id, book_id=book_id, chapter_index=update.chapter_index, progress_percent=update.progress_percent)
        db.add(prog)
    else:
        prog.chapter_index = update.chapter_index
        prog.progress_percent = update.progress_percent
        prog.last_read_at = datetime.utcnow()
    db.commit()
    return {"detail": "Saved"}