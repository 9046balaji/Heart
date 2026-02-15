import os
import aiofiles
from pathlib import Path
from datetime import datetime

class DocumentStorage:
    def __init__(self, base_path: str = "uploads/documents"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file_data: bytes, filename: str) -> str:
        """Save file and return the file path"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = self.base_path / safe_filename

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)

        return str(file_path)

    async def delete_file(self, file_path: str):
        """Delete a file"""
        path = Path(file_path)
        if path.exists():
            path.unlink()
