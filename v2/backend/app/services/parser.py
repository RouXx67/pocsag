from __future__ import annotations

import re
from typing import Optional


class POCSAGParser:
    """Stateful POCSAG line parser that handles multiline messages.
    
    Multimon-ng outputs:
      1) First line: "POCSAG1200: Address: 1234567 Function: 3 Alpha:   TEXT"
      2) Continuations: "POCSAG1200: Alpha:   MORE TEXT" (no Address/Function)
         or "POCSAG1200: Address: 0 Function: 0 Alpha: ..."
      3) Numeric messages: "POCSAG512: Address: 1234567 Function: 3 Numeric: 12345..."
    
    This parser buffers continuation Alpha lines and returns a dict when a new
    header (Address) appears or at flush(), preserving the original regex from F4JTV
    for robustness.
    """
    
    # F4JTV's robust regex (Alpha|Numeric) - captures address/function/message
    HEADER_RE = re.compile(
        r"POCSAG\d+:\s+Address:\s+(\d+)\s+Function:\s+(\d+)\s+(?:Alpha:|Numeric:)\s+(.*)"
    )
    
    # Continuation line (Alpha only, no Address)
    CONTINUATION_RE = re.compile(
        r"POCSAG\d+:\s+Alpha:\s+(.*)"
    )
    
    def __init__(self):
        self.current_ric: Optional[str] = None
        self.current_func: Optional[str] = None
        self.current_message_parts: list[str] = []
        self.current_raw_lines: list[str] = []
    
    def feed(self, line: str) -> Optional[dict]:
        """Process a line from multimon-ng.
        
        Returns a dict with keys 'ric', 'func', 'message', 'raw_line' when a
        complete message is ready, otherwise None.
        """
        line = line.rstrip('\n')
        if not line:
            return None
        
        header_match = self.HEADER_RE.match(line)
        if header_match:
            # We have a new header => finish previous message if any
            result = self._flush()
            
            ric, func, message = header_match.groups()
            self.current_ric = ric
            self.current_func = func
            self.current_message_parts = [message.strip()] if message else []
            self.current_raw_lines = [line]
            
            # Return previous message (if any)
            return result
        
        # Check for continuation line (Alpha only)
        continuation_match = self.CONTINUATION_RE.match(line)
        if continuation_match and self.current_ric is not None:
            # Append to current message
            part = continuation_match.group(1).strip()
            if part:
                self.current_message_parts.append(part)
            self.current_raw_lines.append(line)
            return None
        
        # Non-matching line (could be noise) → ignore but flush if we have a pending message
        if self.current_ric is not None:
            # Unexpected line ends current message
            return self._flush()
        return None
    
    def _flush(self) -> Optional[dict]:
        """Return the current buffered message and reset."""
        if self.current_ric is None:
            return None
        
        ric = self.current_ric
        func = self.current_func
        message = " ".join(self.current_message_parts) if self.current_message_parts else ""
        raw_line = "\n".join(self.current_raw_lines)
        
        self.current_ric = None
        self.current_func = None
        self.current_message_parts.clear()
        self.current_raw_lines.clear()
        
        return {
            "ric": ric,
            "func": func,
            "message": message,
            "raw_line": raw_line,
        }
    
    def flush(self) -> Optional[dict]:
        """Force flush of any pending buffered message."""
        return self._flush()


# Legacy function for backward compatibility (will be used until radio.py update)
def parse_line(line: str) -> dict | None:
    """Parse a single POCSAG line (backward compatibility).
    
    This is a simple wrapper using the stateful parser for single lines.
    It does NOT handle multiline concatenation, just for compatibility.
    """
    if not line:
        return None
    match = POCSAGParser.HEADER_RE.match(line)
    if not match:
        return None
    ric, func, text = match.groups()
    return {
        "ric": ric,
        "func": func,
        "message": text.strip() if text else "",
        "raw_line": line.strip(),
    }