#!/usr/bin/env python3
"""
Interactive tool to find and fill missing LCSC codes for R/C components.

Features:
- Parses KiCad schematics to find R/C without LCSC codes
- Searches JLCPCB for Basic library parts (free assembly)
- Interactive curses UI for reviewing and selecting suggestions
- Updates .kicad_sch files with selected LCSC codes
"""

import curses
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Configuration
SCRIPT_DIR = Path(__file__).parent
PCB_DIR = Path.cwd()
DB_PATH = PCB_DIR / ".lcsc_cache.db"
CACHE_EXPIRY_DAYS = 30


def discover_boards() -> list[str]:
    """Auto-discover KiCad projects and return schematic paths relative to PCB_DIR."""
    boards = []
    for pro_file in sorted(PCB_DIR.rglob("*.kicad_pro")):
        sch_file = pro_file.with_suffix(".kicad_sch")
        if sch_file.exists():
            boards.append(str(sch_file.relative_to(PCB_DIR)))
    return boards


@dataclass
class ComponentSuggestion:
    """A component with a suggested LCSC code."""
    sch_path: Path
    ref: str
    value: str
    package: str
    uuid: str
    current_lcsc: str
    suggested_lcsc: Optional[str]
    suggested_price: Optional[float]
    note: str = ""
    selected: bool = True


# -----------------------------------------------------------------------------
# Database caching
# -----------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the SQLite cache database."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jlcpcb_part_cache (
            lcsc_part TEXT PRIMARY KEY,
            response_json TEXT,
            fetched_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jlcpcb_search_cache (
            search_key TEXT PRIMARY KEY,
            lcsc_code TEXT,
            price REAL,
            fetched_at REAL
        )
    """)
    conn.commit()


class CacheMiss:
    """Sentinel to indicate cache miss (distinct from cached None result)."""
    pass


CACHE_MISS = CacheMiss()


def get_cached_search(conn: sqlite3.Connection, search_key: str) -> tuple[Optional[str], Optional[float]] | CacheMiss:
    """Get cached JLCPCB search result.

    Returns:
        - (lcsc_code, price) if cached (lcsc_code may be None if not found in Basic)
        - CACHE_MISS if not in cache
    """
    cursor = conn.execute(
        "SELECT lcsc_code, price, fetched_at FROM jlcpcb_search_cache WHERE search_key = ?",
        (search_key,)
    )
    row = cursor.fetchone()
    if row:
        fetched_at = row[2]
        if time.time() - fetched_at < CACHE_EXPIRY_DAYS * 86400:
            return (row[0], row[1])  # Return tuple even if lcsc_code is None
    return CACHE_MISS


def cache_search(conn: sqlite3.Connection, search_key: str, lcsc_code: Optional[str], price: Optional[float]) -> None:
    """Store JLCPCB search result in cache."""
    conn.execute(
        """
        INSERT OR REPLACE INTO jlcpcb_search_cache (search_key, lcsc_code, price, fetched_at)
        VALUES (?, ?, ?, ?)
        """,
        (search_key, lcsc_code, price, time.time())
    )
    conn.commit()


def get_cached_part_data(conn: sqlite3.Connection, lcsc_part: str) -> Optional[dict]:
    """Get cached JLCPCB part data."""
    cursor = conn.execute(
        "SELECT response_json, fetched_at FROM jlcpcb_part_cache WHERE lcsc_part = ?",
        (lcsc_part,)
    )
    row = cursor.fetchone()
    if row:
        fetched_at = row[1]
        if time.time() - fetched_at < CACHE_EXPIRY_DAYS * 86400:
            return json.loads(row[0]) if row[0] else {}
    return None


def cache_part_data(conn: sqlite3.Connection, lcsc_part: str, data: dict) -> None:
    """Store JLCPCB part data in cache."""
    conn.execute(
        """
        INSERT OR REPLACE INTO jlcpcb_part_cache (lcsc_part, response_json, fetched_at)
        VALUES (?, ?, ?)
        """,
        (lcsc_part, json.dumps(data), time.time())
    )
    conn.commit()


def fetch_jlcpcb_part_data(lcsc_part: str) -> dict:
    """Fetch part data (prices, stock, description, library type) from JLCPCB API."""
    url = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
    payload = json.dumps({
        "keyword": lcsc_part,
        "pageSize": 5,
        "currentPage": 1
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        components = data.get("data", {}).get("componentPageInfo", {}).get("list", [])
        for comp in components:
            if comp.get("componentCode") == lcsc_part:
                return comp
        return {}
    except Exception:
        return {}


def get_part_description(conn: sqlite3.Connection, lcsc_part: str) -> Optional[str]:
    """Get the product description for a part via JLCPCB API."""
    cached = get_cached_part_data(conn, lcsc_part)
    if cached is not None:
        return cached.get("describe", "")

    data = fetch_jlcpcb_part_data(lcsc_part)
    cache_part_data(conn, lcsc_part, data)
    time.sleep(0.3)
    return data.get("describe", "")


# -----------------------------------------------------------------------------
# Value parsing
# -----------------------------------------------------------------------------

def parse_resistor_value(value_str: str) -> Optional[float]:
    """Parse resistor value string like '10k', '2.2k', '100' to ohms."""
    if not value_str:
        return None
    value_str = value_str.strip().lower().replace("ω", "").replace("ohm", "").replace("r", "")
    # Handle values like "4k7" -> "4.7k"
    value_str = re.sub(r'(\d+)k(\d+)', r'\1.\2k', value_str)
    value_str = re.sub(r'(\d+)m(\d+)', r'\1.\2m', value_str)

    multipliers = {"k": 1e3, "m": 1e6, "g": 1e9}
    for suffix, mult in multipliers.items():
        if value_str.endswith(suffix):
            try:
                return float(value_str[:-1]) * mult
            except ValueError:
                return None
    try:
        return float(value_str)
    except ValueError:
        return None


def parse_capacitor_value(value_str: str) -> Optional[float]:
    """Parse capacitor value string like '10uF', '100nF', '4.7pF' to farads."""
    if not value_str:
        return None
    value_str = value_str.strip().lower().replace("f", "")

    # Map prefixes to multipliers
    multipliers = {
        "p": 1e-12,  # pico
        "n": 1e-9,   # nano
        "u": 1e-6,   # micro
        "µ": 1e-6,   # micro (unicode)
        "m": 1e-3,   # milli
    }

    for suffix, mult in multipliers.items():
        if suffix in value_str:
            try:
                num_str = value_str.replace(suffix, "")
                return float(num_str) * mult
            except ValueError:
                return None

    # No prefix, assume farads (unlikely for capacitors)
    try:
        return float(value_str)
    except ValueError:
        return None


def extract_package_from_footprint(footprint: str) -> str:
    """Extract package size from footprint like 'Resistor_SMD:R_0603_1608Metric'."""
    match = re.search(r'_(\d{4})_', footprint)
    if match:
        return match.group(1)
    return "0603"  # Default


def extract_package_from_lcsc(lcsc_value: str) -> Optional[str]:
    """Extract package size from LCSC description like '...±1% 100mW 0603'."""
    if not lcsc_value:
        return None
    match = re.search(r'\b(\d{4})\b', lcsc_value)
    if match:
        return match.group(1)
    return None


def extract_resistor_from_lcsc(lcsc_value: str) -> Optional[float]:
    """Extract resistor value from LCSC description like 'RES 10kΩ ±1% 100mW 0603'."""
    if not lcsc_value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k|m|g)?Ω", lcsc_value, re.IGNORECASE)
    if match:
        num = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        # In resistor context, 'm' means milli (10^-3), not mega
        multipliers = {"k": 1e3, "m": 1e-3, "g": 1e9, "": 1}
        return num * multipliers.get(suffix, 1)
    return None


def extract_capacitor_from_lcsc(lcsc_value: str) -> Optional[float]:
    """Extract capacitor value from LCSC description like 'CAP 10uF ±10% 16V 0603'."""
    if not lcsc_value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(p|n|u|µ|m)?F", lcsc_value, re.IGNORECASE)
    if match:
        num = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        multipliers = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1}
        return num * multipliers.get(suffix, 1)
    return None


# -----------------------------------------------------------------------------
# JLCPCB API
# -----------------------------------------------------------------------------

def search_jlcpcb_basic_resistor(resistance_ohms: float, package: str = "0603") -> tuple[Optional[str], Optional[float]]:
    """Search JLCPCB for a Basic library resistor with given value and package.

    Returns: (lcsc_code, unit_price) or (None, None) if not found.
    """
    # Format resistance for search
    if resistance_ohms >= 1e6:
        search_val = f"{resistance_ohms/1e6:.10g}M"
    elif resistance_ohms >= 1e3:
        search_val = f"{resistance_ohms/1e3:.10g}k"
    elif resistance_ohms < 1:
        search_val = f"{resistance_ohms*1e3:.10g}m"
    else:
        search_val = f"{resistance_ohms:.10g}"

    url = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
    search_query = f"{search_val}Ω {package}"
    payload = json.dumps({
        "keyword": search_query,
        "pageSize": 20,
        "currentPage": 1,
        "firstSortName": "Resistors",
        "secondSortName": "Chip Resistor - Surface Mount"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        components = data.get("data", {}).get("componentPageInfo", {}).get("list", [])
        for comp in components:
            if comp.get("componentLibraryType") == "base":
                lcsc = comp.get("componentCode")
                # Get price from price tiers
                prices = comp.get("componentPrices", [])
                price = None
                if prices:
                    # Get the first tier price
                    price = prices[0].get("productPrice")
                return lcsc, price
    except Exception:
        pass

    return None, None


def search_jlcpcb_basic_capacitor(capacitance_farads: float, package: str = "0603") -> tuple[Optional[str], Optional[float]]:
    """Search JLCPCB for a Basic library capacitor with given value and package.

    Returns: (lcsc_code, unit_price) or (None, None) if not found.
    """
    # Format capacitance for search
    if capacitance_farads >= 1e-6:
        search_val = f"{capacitance_farads*1e6:.10g}uF"
    elif capacitance_farads >= 1e-9:
        search_val = f"{capacitance_farads*1e9:.10g}nF"
    else:
        search_val = f"{capacitance_farads*1e12:.10g}pF"

    url = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
    search_query = f"{search_val} {package}"
    payload = json.dumps({
        "keyword": search_query,
        "pageSize": 20,
        "currentPage": 1,
        "firstSortName": "Capacitors",
        "secondSortName": "Multilayer Ceramic Capacitors MLCC - SMD/SMT"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        components = data.get("data", {}).get("componentPageInfo", {}).get("list", [])
        for comp in components:
            if comp.get("componentLibraryType") == "base":
                lcsc = comp.get("componentCode")
                prices = comp.get("componentPrices", [])
                price = None
                if prices:
                    price = prices[0].get("productPrice")
                return lcsc, price
    except Exception:
        pass

    return None, None


# -----------------------------------------------------------------------------
# Schematic parsing
# -----------------------------------------------------------------------------

def discover_hierarchical_sheets(root_sch: Path) -> list[Path]:
    """Recursively discover all hierarchical sub-sheets from a root schematic.

    Returns a list of all schematic files including the root, in order suitable
    for processing (root first, then sub-sheets).
    """
    all_sheets = [root_sch]
    visited = {root_sch.resolve()}
    to_process = [root_sch]

    while to_process:
        current = to_process.pop(0)
        if not current.exists():
            continue

        content = current.read_text(encoding="utf-8")

        # Find all (property "Sheetfile" "xxx.kicad_sch") entries
        for match in re.finditer(r'\(property\s+"Sheetfile"\s+"([^"]+)"', content):
            sheet_filename = match.group(1)
            # Sub-sheets are in the same directory as the parent
            sheet_path = current.parent / sheet_filename

            if sheet_path.resolve() not in visited and sheet_path.exists():
                visited.add(sheet_path.resolve())
                all_sheets.append(sheet_path)
                to_process.append(sheet_path)

    return all_sheets


def parse_schematic_symbols(sch_path: Path) -> list[dict]:
    """Parse .kicad_sch and extract symbol instances with properties."""
    content = sch_path.read_text(encoding="utf-8")

    symbols = []

    # Find all top-level (symbol ...) blocks (not lib_symbols)
    # Use a simple state machine approach
    depth = 0
    in_symbol = False
    in_lib_symbols = False
    symbol_start = 0

    i = 0
    while i < len(content):
        if content[i] == '(':
            if not in_lib_symbols and content[i:i+8] == "(symbol\n" or content[i:i+8] == "(symbol ":
                if depth == 1:  # Top level inside kicad_sch
                    in_symbol = True
                    symbol_start = i
            if content[i:i+13] == "(lib_symbols\n" or content[i:i+13] == "(lib_symbols ":
                in_lib_symbols = True
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if in_lib_symbols and depth == 1:
                in_lib_symbols = False
            if in_symbol and depth == 1:
                in_symbol = False
                symbol_text = content[symbol_start:i+1]
                symbols.append(symbol_text)
        i += 1

    # Parse each symbol
    result = []
    for symbol_text in symbols:
        parsed = parse_symbol_text(symbol_text)
        if parsed:
            result.append(parsed)

    return result


def parse_symbol_text(text: str) -> Optional[dict]:
    """Parse a single symbol block and extract relevant info."""
    # Extract lib_id
    lib_id_match = re.search(r'\(lib_id\s+"([^"]+)"\)', text)
    if not lib_id_match:
        return None
    lib_id = lib_id_match.group(1)

    # Only process Device:R and Device:C
    if lib_id not in ("Device:R", "Device:C"):
        return None

    # Extract UUID
    uuid_match = re.search(r'\(uuid\s+"([^"]+)"\)', text)
    uuid = uuid_match.group(1) if uuid_match else ""

    # Extract properties
    def get_property(name: str) -> str:
        # Match property with name and extract value
        pattern = rf'\(property\s+"{re.escape(name)}"\s+"([^"]*)"\s*\n'
        match = re.search(pattern, text)
        return match.group(1) if match else ""

    ref = get_property("Reference")
    value = get_property("Value")
    footprint = get_property("Footprint")
    lcsc = get_property("LCSC")

    # Also try to get reference from instances section
    if not ref:
        ref_match = re.search(r'\(reference\s+"([^"]+)"\)', text)
        ref = ref_match.group(1) if ref_match else ""

    return {
        "lib_id": lib_id,
        "uuid": uuid,
        "ref": ref,
        "value": value,
        "footprint": footprint,
        "lcsc": lcsc,
        "raw": text,
    }


def scan_schematic_for_missing_lcsc(sch_path: Path, conn: sqlite3.Connection, fix_mismatches: bool = False) -> list[ComponentSuggestion]:
    """Parse .kicad_sch and find R/C components without LCSC property or with mismatched values."""
    symbols = parse_schematic_symbols(sch_path)
    suggestions = []

    for sym in symbols:
        ref = sym["ref"]
        value = sym["value"]
        lcsc = sym["lcsc"]
        footprint = sym["footprint"]
        lib_id = sym["lib_id"]
        uuid = sym["uuid"]

        package = extract_package_from_footprint(footprint)
        suggested_lcsc = None
        suggested_price = None
        note = ""
        is_mismatch = False

        # Check if already has LCSC code
        if lcsc and lcsc.strip():
            if not fix_mismatches:
                continue

            # Check for value mismatch
            lcsc_value_str = get_part_description(conn, lcsc)

            if lib_id == "Device:R":
                kicad_ohms = parse_resistor_value(value)
                lcsc_ohms = extract_resistor_from_lcsc(lcsc_value_str)
                if kicad_ohms is not None and lcsc_ohms is not None:
                    # Allow 1% tolerance
                    if abs(kicad_ohms - lcsc_ohms) > 0.01 * max(kicad_ohms, lcsc_ohms):
                        is_mismatch = True
                        note = f"MISMATCH: LCSC={lcsc_ohms}Ω"

            elif lib_id == "Device:C":
                kicad_farads = parse_capacitor_value(value)
                lcsc_farads = extract_capacitor_from_lcsc(lcsc_value_str)
                if kicad_farads is not None and lcsc_farads is not None:
                    if abs(kicad_farads - lcsc_farads) > 0.01 * max(kicad_farads, lcsc_farads):
                        is_mismatch = True
                        note = f"MISMATCH: LCSC={lcsc_farads*1e6:.1f}uF"

            # Check for package mismatch
            if not is_mismatch and lcsc_value_str:
                lcsc_pkg = extract_package_from_lcsc(lcsc_value_str)
                if lcsc_pkg and lcsc_pkg != package:
                    is_mismatch = True
                    note = f"PKG MISMATCH: KiCad={package} LCSC={lcsc_pkg}"

            if not is_mismatch:
                continue  # LCSC code is correct, skip

        # Search for correct LCSC code
        if lib_id == "Device:R":
            ohms = parse_resistor_value(value)
            if ohms is not None:
                search_key = f"R:{ohms}:{package}"
                cached = get_cached_search(conn, search_key)
                if cached is not CACHE_MISS:
                    suggested_lcsc, suggested_price = cached
                else:
                    suggested_lcsc, suggested_price = search_jlcpcb_basic_resistor(ohms, package)
                    cache_search(conn, search_key, suggested_lcsc, suggested_price)
                    time.sleep(0.3)  # Rate limiting

        elif lib_id == "Device:C":
            farads = parse_capacitor_value(value)
            if farads is not None:
                search_key = f"C:{farads}:{package}"
                cached = get_cached_search(conn, search_key)
                if cached is not CACHE_MISS:
                    suggested_lcsc, suggested_price = cached
                else:
                    suggested_lcsc, suggested_price = search_jlcpcb_basic_capacitor(farads, package)
                    cache_search(conn, search_key, suggested_lcsc, suggested_price)
                    time.sleep(0.3)

        if not suggested_lcsc:
            if not note:
                note = "Not found in Basic"

        suggestions.append(ComponentSuggestion(
            sch_path=sch_path,
            ref=ref,
            value=value,
            package=package,
            uuid=uuid,
            current_lcsc=lcsc,
            suggested_lcsc=suggested_lcsc,
            suggested_price=suggested_price,
            note=note,
            selected=suggested_lcsc is not None,  # Auto-select if we have a suggestion
        ))

    return suggestions


# -----------------------------------------------------------------------------
# Schematic update
# -----------------------------------------------------------------------------

def apply_updates_grouped_by_file(updates: list[ComponentSuggestion]) -> int:
    """Apply updates grouped by their actual schematic file.

    Each ComponentSuggestion has a sch_path field indicating which file it belongs to.
    This function groups them and updates each file separately.

    Returns total number of components updated.
    """
    from collections import defaultdict

    # Group by schematic file
    by_file: dict[Path, list[ComponentSuggestion]] = defaultdict(list)
    for u in updates:
        if u.suggested_lcsc:
            by_file[u.sch_path].append(u)

    total = 0
    for sch_path, file_updates in by_file.items():
        count = update_schematic_lcsc(sch_path, file_updates)
        if count > 0:
            print(f"  Updated {count} components in {sch_path.name}")
        total += count

    return total


def update_schematic_lcsc(sch_path: Path, updates: list[ComponentSuggestion]) -> int:
    """Update .kicad_sch file with LCSC codes.

    Returns number of components updated.
    """
    if not updates:
        return 0

    content = sch_path.read_text(encoding="utf-8")
    updated_count = 0

    for suggestion in updates:
        if not suggestion.suggested_lcsc:
            continue

        # Find the symbol by UUID and update LCSC property
        # Pattern: find (property "LCSC" "" ...) within the symbol with matching uuid

        # Find the symbol block containing this UUID
        uuid_pattern = rf'\(uuid\s+"{re.escape(suggestion.uuid)}"\)'
        uuid_match = re.search(uuid_pattern, content)

        if not uuid_match:
            continue

        # Find the symbol block containing this uuid
        # Search backwards for (symbol and forwards for matching )
        uuid_pos = uuid_match.start()

        # Find (symbol that contains this uuid
        symbol_start = content.rfind("(symbol\n", 0, uuid_pos)
        if symbol_start == -1:
            symbol_start = content.rfind("(symbol ", 0, uuid_pos)
        if symbol_start == -1:
            continue

        # Find the end of this symbol block
        depth = 0
        symbol_end = symbol_start
        for i in range(symbol_start, len(content)):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    symbol_end = i + 1
                    break

        symbol_text = content[symbol_start:symbol_end]

        # Update or add LCSC property within this symbol
        lcsc_pattern = r'\(property\s+"LCSC"\s+"[^"]*"'
        lcsc_match = re.search(lcsc_pattern, symbol_text)

        if lcsc_match:
            # Replace existing LCSC value
            old_lcsc = lcsc_match.group(0)
            new_lcsc = f'(property "LCSC" "{suggestion.suggested_lcsc}"'
            new_symbol_text = symbol_text[:lcsc_match.start()] + new_lcsc + symbol_text[lcsc_match.end():]
            content = content[:symbol_start] + new_symbol_text + content[symbol_end:]
            updated_count += 1
        else:
            # No LCSC property exists - add it after Description or last property
            # Find the last (property ...) block to insert after
            # We'll insert before (pin or (instances

            # Find insertion point - before (pin or (instances
            pin_match = re.search(r'\n\t\t\(pin\s', symbol_text)
            instances_match = re.search(r'\n\t\t\(instances\s', symbol_text)

            if pin_match:
                insert_pos = pin_match.start()
            elif instances_match:
                insert_pos = instances_match.start()
            else:
                # Fallback: insert before closing paren
                insert_pos = len(symbol_text) - 1

            # Create LCSC property block (matching KiCad format)
            # Use position from symbol's at property or (0 0 0)
            lcsc_property = f'''
		(property "LCSC" "{suggestion.suggested_lcsc}"
			(at 0 0 0)
			(effects
				(font
					(size 1.27 1.27)
				)
				(hide yes)
			)
		)'''

            new_symbol_text = symbol_text[:insert_pos] + lcsc_property + symbol_text[insert_pos:]
            content = content[:symbol_start] + new_symbol_text + content[symbol_end:]
            updated_count += 1

    # Write back
    sch_path.write_text(content, encoding="utf-8")
    return updated_count


# -----------------------------------------------------------------------------
# Interactive UI
# -----------------------------------------------------------------------------

def safe_addstr(stdscr, row: int, col: int, text: str, attr: int = 0) -> None:
    """Safely add a string to the screen, handling edge cases."""
    height, width = stdscr.getmaxyx()
    if row < 0 or row >= height:
        return
    # Truncate text to fit within the window, leaving space for the last char
    max_len = width - col - 1
    if max_len <= 0:
        return
    text = text[:max_len]
    try:
        if attr:
            stdscr.addstr(row, col, text, attr)
        else:
            stdscr.addstr(row, col, text)
    except curses.error:
        pass  # Ignore errors at screen edges


def interactive_selector(stdscr, suggestions: list[ComponentSuggestion], board_name: str) -> list[ComponentSuggestion]:
    """Display curses UI and return selected items."""
    curses.curs_set(0)  # Hide cursor

    # Initialize colors if terminal supports it
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)

    current_row = 0
    scroll_offset = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Minimum size check
        if height < 10 or width < 60:
            safe_addstr(stdscr, 0, 0, "Terminal too small. Resize to at least 60x10.")
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord('q') or key == ord('Q'):
                return []
            continue

        # Header
        title = f" JLCPCB Basic Component Finder - {board_name} "
        title = title[:width-1].center(width-1)
        safe_addstr(stdscr, 0, 0, title, curses.A_REVERSE)

        # Column headers
        header = f"{'Sel':<4} {'Ref':<8} {'Value':<12} {'Pkg':<6} {'LCSC':<10} {'Price':<8} {'Note'}"
        safe_addstr(stdscr, 2, 0, header[:width-1], curses.A_BOLD)
        safe_addstr(stdscr, 3, 0, "-" * (width - 2))

        # Visible rows
        list_height = max(1, height - 8)
        visible_items = suggestions[scroll_offset:scroll_offset + list_height]

        for idx, item in enumerate(visible_items):
            row = 4 + idx
            if row >= height - 4:
                break

            actual_idx = scroll_offset + idx
            is_selected = actual_idx == current_row

            # Checkbox
            checkbox = "[x]" if item.selected else "[ ]"

            # Format price
            price_str = f"${item.suggested_price:.3f}" if item.suggested_price else "-"

            # LCSC code
            lcsc_str = item.suggested_lcsc or "-"

            # Build line
            line = f"{checkbox:<4} {item.ref:<8} {item.value:<12} {item.package:<6} {lcsc_str:<10} {price_str:<8} {item.note}"
            line = line[:width-2]

            # Determine attributes
            attr = 0
            if is_selected:
                attr |= curses.A_REVERSE
            if curses.has_colors():
                if item.suggested_lcsc:
                    attr |= curses.color_pair(1)  # Green
                elif item.note:
                    attr |= curses.color_pair(3)  # Red

            safe_addstr(stdscr, row, 0, line, attr)

        # Stats
        selected_count = sum(1 for s in suggestions if s.selected and s.suggested_lcsc)
        total_with_suggestion = sum(1 for s in suggestions if s.suggested_lcsc)
        stats = f" {selected_count}/{total_with_suggestion} selected | {len(suggestions)} total "
        safe_addstr(stdscr, height - 4, 0, "-" * (width - 2))
        attr = curses.color_pair(4) if curses.has_colors() else 0
        safe_addstr(stdscr, height - 3, 0, stats, attr)

        # Help
        help_text = " [Space] Toggle  [A] All  [N] None  [Enter] Apply  [Q] Quit "
        help_text = help_text[:width-1].center(width-1)
        safe_addstr(stdscr, height - 2, 0, help_text, curses.A_REVERSE)

        stdscr.refresh()

        # Handle input
        key = stdscr.getch()

        if key == ord('q') or key == ord('Q'):
            return []  # Quit without saving

        elif key == ord('\n') or key == curses.KEY_ENTER or key == 10:
            return [s for s in suggestions if s.selected and s.suggested_lcsc]

        elif key == ord(' '):
            if suggestions:
                suggestions[current_row].selected = not suggestions[current_row].selected

        elif key == ord('a') or key == ord('A'):
            for s in suggestions:
                if s.suggested_lcsc:
                    s.selected = True

        elif key == ord('n') or key == ord('N'):
            for s in suggestions:
                s.selected = False

        elif key == curses.KEY_UP or key == ord('k'):
            if current_row > 0:
                current_row -= 1
                if current_row < scroll_offset:
                    scroll_offset = current_row

        elif key == curses.KEY_DOWN or key == ord('j'):
            if current_row < len(suggestions) - 1:
                current_row += 1
                if current_row >= scroll_offset + list_height:
                    scroll_offset = current_row - list_height + 1

        elif key == curses.KEY_PPAGE:  # Page Up
            current_row = max(0, current_row - list_height)
            scroll_offset = max(0, scroll_offset - list_height)

        elif key == curses.KEY_NPAGE:  # Page Down
            current_row = min(len(suggestions) - 1, current_row + list_height)
            scroll_offset = min(len(suggestions) - list_height, scroll_offset + list_height)
            scroll_offset = max(0, scroll_offset)


def simple_interactive_selector(suggestions: list[ComponentSuggestion], board_name: str) -> Optional[list[ComponentSuggestion]]:
    """Simple interactive mode using standard input (fallback when curses fails)."""
    print_suggestions_table(suggestions, board_name)

    # Filter to only those with suggestions
    with_suggestions = [s for s in suggestions if s.suggested_lcsc]

    if not with_suggestions:
        print("\nNo suggestions available to apply.")
        return []

    print(f"\n{len(with_suggestions)} components have JLCPCB Basic suggestions.")
    print("\nOptions:")
    print("  [a] Apply all suggestions")
    print("  [s] Select individually")
    print("  [q] Quit without changes")

    while True:
        try:
            choice = input("\nChoice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return None

        if choice == 'q':
            print("Cancelled.")
            return []
        elif choice == 'a':
            return with_suggestions
        elif choice == 's':
            # Individual selection
            selected = []
            for s in with_suggestions:
                try:
                    ans = input(f"  {s.ref} {s.value} -> {s.suggested_lcsc}? [Y/n] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    return None
                if ans != 'n':
                    selected.append(s)
            return selected
        else:
            print("Invalid choice. Use 'a', 's', or 'q'.")


def print_suggestions_table(suggestions: list[ComponentSuggestion], board_name: str) -> None:
    """Print suggestions in a table format (non-interactive mode)."""
    print(f"\n{'='*70}")
    print(f" {board_name}: Missing LCSC codes")
    print(f"{'='*70}")
    print(f"{'Ref':<8} {'Value':<12} {'Pkg':<6} {'Suggested':<12} {'Price':<10} {'Note'}")
    print("-" * 70)

    for s in suggestions:
        price_str = f"${s.suggested_price:.4f}" if s.suggested_price else "-"
        lcsc_str = s.suggested_lcsc or "-"
        print(f"{s.ref:<8} {s.value:<12} {s.package:<6} {lcsc_str:<12} {price_str:<10} {s.note}")

    with_suggestion = sum(1 for s in suggestions if s.suggested_lcsc)
    print("-" * 70)
    print(f"Total: {len(suggestions)} components, {with_suggestion} with suggestions")


def run_interactive(board_path: str, list_only: bool = False, auto_apply: bool = False, fix_mismatches: bool = False) -> None:
    """Run interactive selection for a single board."""
    sch_path = PCB_DIR / board_path

    if not sch_path.exists():
        print(f"Error: {sch_path} not found")
        return

    board_name = sch_path.parent.name

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    mode = "missing LCSC codes" + (" and mismatches" if fix_mismatches else "")

    # Discover all hierarchical sheets
    all_sheets = discover_hierarchical_sheets(sch_path)
    if len(all_sheets) > 1:
        print(f"Found {len(all_sheets)} schematic files (including sub-sheets)")

    suggestions = []
    for sheet in all_sheets:
        rel_name = sheet.name if sheet == sch_path else f"  └─ {sheet.name}"
        print(f"Scanning {rel_name} for {mode}...")
        sheet_suggestions = scan_schematic_for_missing_lcsc(sheet, conn, fix_mismatches=fix_mismatches)
        suggestions.extend(sheet_suggestions)

    conn.close()

    if not suggestions:
        print(f"No R/C components with {mode} found.")
        return

    # List-only mode
    if list_only:
        print_suggestions_table(suggestions, board_name)
        return

    # Auto-apply mode (no interactive UI)
    if auto_apply:
        selected = [s for s in suggestions if s.suggested_lcsc]
        if not selected:
            print("No suggestions to apply.")
            return
        print(f"\nAuto-applying {len(selected)} changes to {board_name}...")
        updated = apply_updates_grouped_by_file(selected)
        print(f"Total: {updated} components updated.")
        return

    print(f"Found {len(suggestions)} components...")

    # Check if we have a proper TTY
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("\nNot running in interactive terminal.")
        print_suggestions_table(suggestions, board_name)
        print("\nUse --auto to apply all suggestions, or run directly in terminal.")
        return

    # Try curses UI, fall back to simple prompt if not available
    try:
        selected = curses.wrapper(lambda stdscr: interactive_selector(stdscr, suggestions, board_name))
    except Exception as e:
        print(f"\nCurses UI failed: {e}")
        print("Falling back to simple interactive mode...\n")
        selected = simple_interactive_selector(suggestions, board_name)
        if selected is None:
            return

    if not selected:
        print("No changes made.")
        return

    print(f"\nApplying {len(selected)} changes to {board_name}...")
    updated = apply_updates_grouped_by_file(selected)
    print(f"Total: {updated} components updated.")


def run_all_boards(list_only: bool = False, auto_apply: bool = False, fix_mismatches: bool = False) -> None:
    """Process all boards with interactive confirmation."""
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    all_suggestions: dict[str, list[ComponentSuggestion]] = {}
    mode = "missing/mismatched" if fix_mismatches else "missing"

    for board_path in discover_boards():
        sch_path = PCB_DIR / board_path
        if not sch_path.exists():
            continue

        board_name = sch_path.parent.name
        print(f"Scanning {board_name}...")

        # Discover all hierarchical sheets
        all_sheets = discover_hierarchical_sheets(sch_path)
        if len(all_sheets) > 1:
            print(f"  Found {len(all_sheets)} schematic files (including sub-sheets)")

        suggestions = []
        for sheet in all_sheets:
            sheet_suggestions = scan_schematic_for_missing_lcsc(sheet, conn, fix_mismatches=fix_mismatches)
            suggestions.extend(sheet_suggestions)

        if suggestions:
            all_suggestions[board_path] = suggestions
            print(f"  Found {len(suggestions)} components with {mode} LCSC")
        else:
            print(f"  All components OK")

    conn.close()

    if not all_suggestions:
        print(f"\nNo components with {mode} LCSC codes found in any board.")
        return

    # List-only mode
    if list_only:
        for board_path, suggestions in all_suggestions.items():
            board_name = (PCB_DIR / board_path).parent.name
            print_suggestions_table(suggestions, board_name)
        return

    # Auto-apply mode
    if auto_apply:
        total_applied = 0
        total_no_suggestion = 0
        for board_path, suggestions in all_suggestions.items():
            sch_path = PCB_DIR / board_path
            board_name = sch_path.parent.name
            selected = [s for s in suggestions if s.suggested_lcsc]
            no_suggestion = [s for s in suggestions if not s.suggested_lcsc]
            total_no_suggestion += len(no_suggestion)
            if selected:
                print(f"\nAuto-applying {len(selected)} changes to {board_name}...")
                updated = apply_updates_grouped_by_file(selected)
                total_applied += updated
            elif no_suggestion:
                print(f"\n{board_name}: {len(no_suggestion)} components without suggestions (not in JLCPCB Basic)")

        if total_applied == 0 and total_no_suggestion > 0:
            print(f"\nNo changes applied. {total_no_suggestion} components have no JLCPCB Basic alternative.")
        return

    # Process each board interactively
    for board_path, suggestions in all_suggestions.items():
        sch_path = PCB_DIR / board_path
        board_name = sch_path.parent.name

        print(f"\nProcessing {board_name}...")

        # Check if we have a proper TTY
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("\nNot running in interactive terminal.")
            print_suggestions_table(suggestions, board_name)
            print("\nUse --auto to apply all suggestions.")
            return

        try:
            selected = curses.wrapper(lambda stdscr: interactive_selector(stdscr, suggestions, board_name))
        except Exception as e:
            print(f"Curses UI failed: {e}")
            print("Falling back to simple interactive mode...\n")
            selected = simple_interactive_selector(suggestions, board_name)
            if selected is None:
                return

        if selected:
            updated = apply_updates_grouped_by_file(selected)
            print(f"Total: {updated} components updated in {board_name}")
        else:
            print(f"Skipped {board_name}")


def main():
    os.chdir(PCB_DIR)

    # Parse arguments
    args = sys.argv[1:]
    list_only = "--list" in args
    auto_apply = "--auto" in args
    fix_mismatches = "--fix-mismatches" in args or "--fix" in args
    args = [a for a in args if not a.startswith("--")]

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: fill_lcsc_codes.py [board] [--list] [--auto] [--fix-mismatches]")
        print()
        print("Find and fill missing LCSC codes for R/C components in KiCad schematics.")
        print()
        print("Arguments:")
        print("  board      Optional board name (LED, ...)")
        print("             If omitted, processes all boards")
        print()
        print("Options:")
        print("  --list            List suggestions only, don't modify files")
        print("  --auto            Auto-apply all suggestions (no interactive UI)")
        print("  --fix-mismatches  Also fix components with wrong LCSC codes (value mismatch)")
        print("  --fix             Alias for --fix-mismatches")
        print("  --help            Show this help message")
        print()
        print("Examples:")
        print("  fill_lcsc_codes.py                      # Interactive, missing codes only")
        print("  fill_lcsc_codes.py --fix                # Interactive, include mismatches")
        print("  fill_lcsc_codes.py LED --fix --list     # List mismatches for LED")
        print("  fill_lcsc_codes.py --fix --auto         # Auto-fix all mismatches")
        return

    if args:
        # Process specific board
        board_arg = args[0]
        boards = discover_boards()
        # Find matching board
        for board_path in boards:
            if board_arg in board_path:
                run_interactive(board_path, list_only=list_only, auto_apply=auto_apply, fix_mismatches=fix_mismatches)
                return
        print(f"Board not found: {board_arg}")
        print(f"Available boards: {', '.join(boards)}")
    else:
        # Process all boards
        run_all_boards(list_only=list_only, auto_apply=auto_apply, fix_mismatches=fix_mismatches)


if __name__ == "__main__":
    main()
