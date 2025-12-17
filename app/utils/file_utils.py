import os
import uuid
import hashlib
import magic
from typing import Optional, Tuple, BinaryIO
from pathlib import Path
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)


class FileUtils:
    """File handling utilities"""
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Generate unique filename with UUID"""
        ext = FileUtils.get_file_extension(original_filename)
        unique_id = uuid.uuid4().hex
        return f"{unique_id}{ext}"
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension with dot"""
        return Path(filename).suffix.lower()
    
    @staticmethod
    def get_file_mime_type(file_path: str) -> Optional[str]:
        """Get MIME type of file"""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(file_path)
        except:
            try:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(file_path)
                return mime_type
            except:
                return None
    
    @staticmethod
    def get_file_mime_type_from_buffer(buffer: bytes) -> Optional[str]:
        """Get MIME type from file buffer"""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_buffer(buffer)
        except:
            return None
    
    @staticmethod
    def validate_file_type(
        file_path: str,
        allowed_types: Optional[list] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate file type"""
        if allowed_types is None:
            allowed_types = settings.allowed_file_types
        
        mime_type = FileUtils.get_file_mime_type(file_path)
        
        if not mime_type:
            return False, "Could not determine file type"
        
        if mime_type not in allowed_types:
            return False, f"File type {mime_type} not allowed"
        
        return True, mime_type
    
    @staticmethod
    def validate_file_size(
        file_path: str,
        max_size_mb: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate file size"""
        if max_size_mb is None:
            max_size_mb = settings.max_upload_size // (1024 * 1024)
        
        max_size_bytes = max_size_mb * 1024 * 1024
        
        try:
            file_size = os.path.getsize(file_path)
            
            if file_size > max_size_bytes:
                return False, f"File size exceeds {max_size_mb}MB limit"
            
            return True, None
        except OSError as e:
            return False, f"Error checking file size: {str(e)}"
    
    @staticmethod
    def calculate_file_hash(file_path: str, algorithm: str = "sha256") -> Optional[str]:
        """Calculate file hash"""
        try:
            hash_func = hashlib.new(algorithm)
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return None
    
    @staticmethod
    def save_file(
        file_content: bytes,
        directory: str,
        filename: str
    ) -> Tuple[bool, Optional[str]]:
        """Save file to directory"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            file_path = os.path.join(directory, filename)
            
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return True, file_path
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return False, None
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    @staticmethod
    def get_file_info(file_path: str) -> Optional[dict]:
        """Get file information"""
        try:
            if not os.path.exists(file_path):
                return None
            
            stats = os.stat(file_path)
            mime_type = FileUtils.get_file_mime_type(file_path)
            
            return {
                "path": file_path,
                "filename": os.path.basename(file_path),
                "size_bytes": stats.st_size,
                "size_mb": stats.st_size / (1024 * 1024),
                "created": stats.st_ctime,
                "modified": stats.st_mtime,
                "mime_type": mime_type,
                "extension": FileUtils.get_file_extension(file_path),
                "hash_sha256": FileUtils.calculate_file_hash(file_path)
            }
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    @staticmethod
    def create_thumbnail(
        image_path: str,
        thumbnail_path: str,
        max_size: Tuple[int, int] = (200, 200)
    ) -> bool:
        """Create thumbnail from image"""
        try:
            from PIL import Image
            
            with Image.open(image_path) as img:
                img.thumbnail(max_size)
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else img)
                    img = background
                
                img.save(thumbnail_path, 'JPEG', quality=85)
                return True
        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to remove dangerous characters"""
        # Remove path traversal attempts
        filename = os.path.basename(filename)
        
        # Remove dangerous characters
        dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255 - len(ext)] + ext
        
        return filename
    
    @staticmethod
    def get_human_readable_size(size_bytes: int) -> str:
        """Convert bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def is_image_file(filename: str) -> bool:
        """Check if file is an image"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        ext = FileUtils.get_file_extension(filename)
        return ext in image_extensions
    
    @staticmethod
    def is_pdf_file(filename: str) -> bool:
        """Check if file is a PDF"""
        ext = FileUtils.get_file_extension(filename)
        return ext == '.pdf'
    
    @staticmethod
    def is_document_file(filename: str) -> bool:
        """Check if file is a document"""
        doc_extensions = {'.pdf', '.doc', '.docx', '.txt', '.rtf'}
        ext = FileUtils.get_file_extension(filename)
        return ext in doc_extensions
    
    @staticmethod
    def get_safe_tmp_path() -> str:
        """Get safe temporary file path"""
        import tempfile
        return tempfile.mkdtemp(prefix="smartaid_")
    
    @staticmethod
    def cleanup_temp_files(directory: str, max_age_hours: int = 24) -> int:
        """Cleanup temporary files older than specified hours"""
        import time
        import shutil
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0
        
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                
                if os.path.isfile(item_path):
                    file_age = current_time - os.path.getmtime(item_path)
                    if file_age > max_age_seconds:
                        os.remove(item_path)
                        deleted_count += 1
                elif os.path.isdir(item_path):
                    # Recursively cleanup subdirectories
                    deleted_count += FileUtils.cleanup_temp_files(item_path, max_age_hours)
                    
                    # Remove empty directory
                    if not os.listdir(item_path):
                        os.rmdir(item_path)
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
            return 0


# Singleton instance
file_utils = FileUtils()