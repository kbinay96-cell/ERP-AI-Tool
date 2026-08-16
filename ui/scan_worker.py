"""
ui/scan_worker.py

Background worker - MemoryIndex.update_index_incremental() ko QThread par
chalata hai taaki UI thread kabhi block na ho.

Layer: Controller/Service (UI layer aur memory_index.py ke beech pul).
Is file mein koi PyQt widget nahi banta - sirf signals emit hote hain.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from memory_index import MemoryIndex

logger = logging.getLogger(__name__)

# Memory file tool ke apne folder mein rehti hai (jo project scan ho raha
# hai uske andar nahi) - memory_index.py ke __main__ block se confirm hai.
MEMORY_FILE_NAME = "erp_memory.json"


class ScanWorker(QThread):
    """
    Ek project ka scan/index-update background thread par chalata hai.

    Signals
    -------
    finished_ok(dict)
        Scan safal hone par emit hota hai. Payload shape:
            {
                "added": list[str], "updated": list[str], "removed": list[str],
                "added_count": int, "updated_count": int, "removed_count": int,
                "total_files": int,
            }
    failed(str)
        Kisi exception aane par emit hota hai - user-facing safe message.
        Poori traceback sirf log file mein jaati hai.
    """

    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, project_root: str, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self._project_root = project_root

    def run(self) -> None:
        """
        Qt ise start() call hone par chalata hai. Kabhi bhi exception
        thread boundary cross nahi karega - yahin catch, log, aur
        `failed` signal ke through report hota hai.
        """
        try:
            memory = MemoryIndex(MEMORY_FILE_NAME)
            report = memory.update_index_incremental(self._project_root)

            overview = memory.get_project_overview()

            result = {
                "added": report.get("added", []),
                "updated": report.get("updated", []),
                "removed": report.get("removed", []),
                "added_count": len(report.get("added", [])),
                "updated_count": len(report.get("updated", [])),
                "removed_count": len(report.get("removed", [])),
                "total_files": overview.get("total_files", 0),
            }
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - worker boundary, kabhi crash nahi hona chahiye
            logger.exception(
                "ScanWorker: scan failed for project_root=%s", self._project_root
            )
            self.failed.emit(f"Scan failed: {exc}")