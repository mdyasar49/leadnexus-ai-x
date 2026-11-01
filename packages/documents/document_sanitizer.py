"""
LeadNexus AI X - Phase 42: Document Sanitizer & Security Inspector
Enforces security barriers against untrusted document inputs, detecting malicious scripts,
embedded macros, dangerous payloads, and computing cryptographic hash proofs.
"""

import hashlib
import re
from typing import Dict, List, Tuple


class DocumentSanitizer:
    """Inspects and validates document content for safety and integrity."""

    # Signatures for malicious macros or active executable scripts
    DANGEROUS_SIGNATURES: List[Tuple[str, str]] = [
        ("VBA_MACRO", r"(?i)(vbaProject\.bin|auto_open|workbook_open|powershell|cmd\.exe)"),
        ("SCRIPT_INJECTION", r"(?i)(<script[^>]*>|javascript:|eval\(|base64_decode)"),
        ("XML_EXTERNAL_ENTITY", r"(?i)(<!ENTITY\s+[\w\-]+\s+SYSTEM)"),
        ("SUSPICIOUS_SHELL", r"(?i)(/bin/sh|/bin/bash|wget\s+http|curl\s+http)"),
    ]

    @classmethod
    def compute_sha256(cls, content: bytes) -> str:
        """Calculates canonical SHA-256 fingerprint for document bytes."""
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def inspect(cls, filename: str, content: bytes) -> Dict[str, any]:
        """
        Inspects raw content bytes and filename.
        Returns safety assessment, flagged threats, and calculated hash.
        """
        file_hash = cls.compute_sha256(content)
        threats_found: List[str] = []

        # Convert sample up to 1MB to text for heuristic regex inspection
        sample_text = content[: 1024 * 1024].decode("utf-8", errors="ignore")

        for threat_name, pattern in cls.DANGEROUS_SIGNATURES:
            if re.search(pattern, sample_text):
                threats_found.append(threat_name)

        # Check filename for path traversal or executable extensions
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
            threats_found.append("PATH_TRAVERSAL_ATTEMPT")

        dangerous_extensions = [".exe", ".bat", ".cmd", ".vbs", ".ps1", ".sh", ".dll", ".so"]
        if any(filename.lower().endswith(ext) for ext in dangerous_extensions):
            threats_found.append("EXECUTABLE_EXTENSION_REJECTED")

        if threats_found:
            malware_status = "REJECTED" if any(t in ["EXECUTABLE_EXTENSION_REJECTED", "VBA_MACRO", "XML_EXTERNAL_ENTITY"] for t in threats_found) else "SUSPICIOUS"
            quality_score = 0.0 if malware_status == "REJECTED" else 0.4
        else:
            malware_status = "CLEAN"
            quality_score = 1.0

        return {
            "file_hash": file_hash,
            "filename": filename,
            "file_size_bytes": len(content),
            "malware_status": malware_status,
            "threats_found": threats_found,
            "quality_score": quality_score,
            "is_safe": malware_status == "CLEAN",
        }
