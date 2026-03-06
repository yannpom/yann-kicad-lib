#!/usr/bin/env python3
"""
Export BOM from all KiCad projects, fetch JLCPCB part data, and generate enriched CSV reports.

Features:
- Auto-export BOM from KiCad schematics
- Fetch and cache JLCPCB part data (prices, stock, library type)
- Detect resistor value mismatches
- Suggest JLCPCB Basic resistors for missing/wrong parts
- Generate enriched CSV with prices and cumulative costs
"""

import csv
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

# Configuration
SCRIPT_DIR = Path(__file__).parent
PCB_DIR = Path.cwd()
DB_PATH = PCB_DIR / ".lcsc_cache.db"
CACHE_EXPIRY_DAYS = 30
KICAD_CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")


def discover_boards() -> list[str]:
    """Auto-discover KiCad projects and return schematic paths relative to PCB_DIR."""
    boards = []
    for pro_file in sorted(PCB_DIR.rglob("*.kicad_pro")):
        sch_file = pro_file.with_suffix(".kicad_sch")
        if sch_file.exists():
            boards.append(str(sch_file.relative_to(PCB_DIR)))
    return boards


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the SQLite cache database."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jlcpcb_part_cache (
            lcsc_part TEXT PRIMARY KEY,
            response_json TEXT,
            fetched_at REAL
        )
    """)
    conn.commit()


def get_cached_data(conn: sqlite3.Connection, lcsc_part: str) -> Optional[dict]:
    """Get cached JLCPCB API response if not expired."""
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


def cache_data(conn: sqlite3.Connection, lcsc_part: str, data: dict) -> None:
    """Store JLCPCB API response in cache."""
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
    except Exception as e:
        print(f"    Error fetching {lcsc_part}: {e}")
        return {}


def get_price_for_quantity(price_list: list, qty: int) -> Optional[float]:
    """Get unit price for a given quantity from price tier list."""
    if not price_list:
        return None

    sorted_tiers = sorted(price_list, key=lambda t: t.get("startNumber", t.get("ladder", 1)))
    applicable_price = None

    if sorted_tiers:
        first_price = sorted_tiers[0].get("productPrice")
        if first_price is not None:
            applicable_price = float(first_price)

    for tier in sorted_tiers:
        ladder = tier.get("startNumber", tier.get("ladder", 1))
        if qty >= ladder:
            price = tier.get("productPrice")
            if price is not None:
                applicable_price = float(price)

    return applicable_price


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


def extract_resistor_from_lcsc(lcsc_value: str) -> Optional[float]:
    """Extract resistor value from LCSC description like 'RES 10kΩ ±1% 100mW 0603'."""
    if not lcsc_value:
        return None
    # Match patterns like "10kΩ", "10mΩ" (milliohms), "100Ω"
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k|m|g)?Ω", lcsc_value, re.IGNORECASE)
    if match:
        num = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        # In resistor context, 'm' means milli (10^-3), not mega
        multipliers = {"k": 1e3, "m": 1e-3, "g": 1e9, "": 1}
        return num * multipliers.get(suffix, 1)
    return None


def extract_package_from_footprint(footprint: str) -> str:
    """Extract package size from footprint like 'Resistor_SMD:R_0603_1608Metric'."""
    match = re.search(r'_(\d{4})_', footprint)
    if match:
        return match.group(1)
    return "0603"  # Default


def search_jlcpcb_basic_resistor(resistance_ohms: float, package: str = "0603") -> Optional[str]:
    """Search JLCPCB for a Basic library resistor with given value and package."""
    # Format resistance for search (e.g., "10k", "100", "2.2k")
    if resistance_ohms >= 1e6:
        search_val = f"{resistance_ohms/1e6:.10g}M"
    elif resistance_ohms >= 1e3:
        search_val = f"{resistance_ohms/1e3:.10g}k"
    elif resistance_ohms < 1:
        search_val = f"{resistance_ohms*1e3:.10g}m"
    else:
        search_val = f"{resistance_ohms:.10g}"

    # Search JLCPCB API for resistors
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
            # Only return Basic parts
            if comp.get("componentLibraryType") == "base":
                return comp.get("componentCode")
    except Exception as e:
        pass  # Silently fail for suggestions

    return None


def export_bom_from_kicad(schematic_path: Path) -> list[dict]:
    """Export BOM from KiCad schematic using kicad-cli."""
    bom_path = schematic_path.with_suffix(".csv")

    cmd = [
        KICAD_CLI, "sch", "export", "bom",
        "--fields", "Reference,Value,Footprint,LCSC,${QUANTITY}",
        "--labels", "Reference,Value,Footprint,LCSC,Quantity",
        "--group-by", "Value,Footprint,LCSC",
        "--ref-delimiter", " ",
        "--exclude-dnp",
        "-o", str(bom_path),
        str(schematic_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    Error exporting BOM: {result.stderr}")
        return []

    # Parse the exported CSV
    components = []
    with open(bom_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            components.append({
                "refs": row.get("Reference", ""),
                "value": row.get("Value", ""),
                "footprint": row.get("Footprint", ""),
                "lcsc": row.get("LCSC", "").strip() or None,
                "quantity": int(row.get("Quantity", 1)),
            })

    return components


def enrich_with_prices(components: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """Enrich components with JLCPCB part data (prices, stock, library type)."""
    unique_parts = set(c["lcsc"] for c in components if c["lcsc"])

    part_data = {}

    for lcsc_part in unique_parts:
        cached = get_cached_data(conn, lcsc_part)
        if cached is not None:
            part_data[lcsc_part] = cached
        else:
            print(f"    Fetching {lcsc_part}...")
            data = fetch_jlcpcb_part_data(lcsc_part)
            cache_data(conn, lcsc_part, data)
            part_data[lcsc_part] = data
            time.sleep(0.3)

    for comp in components:
        lcsc = comp.get("lcsc")
        if lcsc and lcsc in part_data:
            data = part_data[lcsc]
            price_list = data.get("componentPrices", [])
            comp["lcsc_name"] = data.get("componentModelEn", "")
            comp["lcsc_value"] = data.get("describe", "")
            comp["stock"] = data.get("stockCount", 0)
            comp["price_1"] = get_price_for_quantity(price_list, 1)
            comp["price_10"] = get_price_for_quantity(price_list, 10)
            comp["price_100"] = get_price_for_quantity(price_list, 100)
            # JLCPCB library type: base = Basic (free), expand = Extended (fee)
            lib_type = data.get("componentLibraryType", "")
            comp["jlc_type"] = "Basic" if lib_type == "base" else "Extended" if lib_type == "expand" else lib_type or ""
        else:
            comp["lcsc_name"] = None
            comp["lcsc_value"] = None
            comp["stock"] = None
            comp["price_1"] = None
            comp["price_10"] = None
            comp["price_100"] = None
            comp["jlc_type"] = ""

    return components


def check_resistor_errors(comp: dict) -> tuple[list[str], Optional[str]]:
    """Check for resistor value mismatches and suggest alternatives.

    Returns: (list of errors, suggested LCSC code or None)
    """
    errors = []
    suggested_lcsc = None

    refs = comp.get("refs", "")
    first_ref = refs.split()[0] if refs else ""

    # Only check components starting with R (resistors)
    if not first_ref.startswith("R"):
        return errors, suggested_lcsc

    kicad_value = comp.get("value", "")
    lcsc_value = comp.get("lcsc_value", "")
    package = extract_package_from_footprint(comp.get("footprint", ""))

    kicad_ohms = parse_resistor_value(kicad_value)

    if comp.get("lcsc") and lcsc_value:
        # Check if LCSC value matches KiCad value
        lcsc_ohms = extract_resistor_from_lcsc(lcsc_value)
        if kicad_ohms is not None and lcsc_ohms is not None:
            # Allow 1% tolerance for comparison
            if abs(kicad_ohms - lcsc_ohms) > 0.01 * max(kicad_ohms, lcsc_ohms):
                errors.append(f"VALUE_MISMATCH: KiCad={kicad_value} LCSC={lcsc_ohms}Ω")
                # Search for correct Basic resistor
                basic_lcsc = search_jlcpcb_basic_resistor(kicad_ohms, package)
                if basic_lcsc:
                    suggested_lcsc = basic_lcsc
    elif not comp.get("lcsc") and kicad_ohms is not None:
        # No LCSC code, suggest a Basic resistor
        basic_lcsc = search_jlcpcb_basic_resistor(kicad_ohms, package)
        if basic_lcsc:
            suggested_lcsc = basic_lcsc

    return errors, suggested_lcsc


def export_enriched_csv(components: list[dict], csv_path: Path) -> None:
    """Export enriched BOM with prices to CSV."""

    # Add error checking and suggestions
    for comp in components:
        errors, suggested = check_resistor_errors(comp)
        comp["errors"] = "; ".join(errors) if errors else ""
        comp["suggested_lcsc"] = suggested or ""

    # Calculate totals and cumulative sums
    for comp in components:
        qty = comp["quantity"]
        comp["total_1"] = round(comp["price_1"] * qty, 4) if comp["price_1"] else None
        comp["total_10"] = round(comp["price_10"] * qty, 4) if comp["price_10"] else None
        comp["total_100"] = round(comp["price_100"] * qty, 4) if comp["price_100"] else None

    # Sort by total_100 descending (most expensive first)
    components = sorted(components, key=lambda x: (x["total_100"] is None, -(x["total_100"] or 0)))

    # Calculate cumulative sums
    grand_total = sum(c["total_100"] or 0 for c in components)
    cumsum = 0.0
    for comp in components:
        cumsum += comp["total_100"] or 0
        comp["cumsum_usd"] = round(cumsum, 4)
        comp["cumsum_pct"] = round(100 * cumsum / grand_total, 1) if grand_total > 0 else 0

    # Export to CSV
    fieldnames = [
        "refs", "value", "footprint", "lcsc", "jlc_type", "lcsc_name", "lcsc_value",
        "stock", "quantity",
        "price_1", "price_10", "price_100",
        "total_1", "total_10", "total_100",
        "cumsum_usd", "cumsum_pct",
        "errors", "suggested_lcsc"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(components)

    print(f"    Exported enriched BOM to {csv_path}")


def compute_board_cost(components: list[dict]) -> dict:
    """Compute total cost for a board at different quantities."""
    total_1 = 0.0
    total_10 = 0.0
    total_100 = 0.0
    missing_lcsc = []
    low_stock = []
    value_errors = []

    for comp in components:
        qty = comp["quantity"]

        if not comp["lcsc"]:
            missing_lcsc.append({
                "refs": comp["refs"],
                "value": comp["value"],
                "suggested": comp.get("suggested_lcsc", "")
            })
            continue

        if comp["price_1"]:
            total_1 += comp["price_1"] * qty
        if comp["price_10"]:
            total_10 += comp["price_10"] * qty
        if comp["price_100"]:
            total_100 += comp["price_100"] * qty

        if comp["stock"] is not None and comp["stock"] < qty * 10:
            low_stock.append(f"{comp['refs']} ({comp['lcsc']}: {comp['stock']} in stock)")

        if comp.get("errors"):
            value_errors.append({
                "refs": comp["refs"],
                "error": comp["errors"],
                "suggested": comp.get("suggested_lcsc", "")
            })

    # Count Basic vs Extended parts
    basic_count = sum(1 for c in components if c.get("jlc_type") == "Basic")
    extended_count = sum(1 for c in components if c.get("jlc_type") == "Extended")

    return {
        "total_1": round(total_1, 2),
        "total_10": round(total_10, 2),
        "total_100": round(total_100, 2),
        "component_count": len(components),
        "total_parts": sum(c["quantity"] for c in components),
        "basic_count": basic_count,
        "extended_count": extended_count,
        "missing_lcsc": missing_lcsc,
        "low_stock": low_stock,
        "value_errors": value_errors,
    }


def process_board(schematic_path: Path, conn: sqlite3.Connection) -> dict:
    """Process a single board and return cost data."""
    board_name = schematic_path.parent.name
    print(f"\n{'='*60}")
    print(f"Processing: {board_name}")
    print(f"{'='*60}")

    # Export BOM
    print(f"  Exporting BOM from {schematic_path.name}...")
    components = export_bom_from_kicad(schematic_path)

    if not components:
        return {"name": board_name, "error": "Failed to export BOM"}

    print(f"  Found {len(components)} unique component groups")

    # Enrich with prices
    print(f"  Fetching JLCPCB data...")
    components = enrich_with_prices(components, conn)

    # Export enriched CSV
    enriched_csv_path = schematic_path.with_name(f"{board_name}_BOM_enriched.csv")
    export_enriched_csv(components, enriched_csv_path)

    # Compute costs
    costs = compute_board_cost(components)
    costs["name"] = board_name
    costs["components"] = components

    return costs


def print_report(boards_data: list[dict]) -> None:
    """Print a summary report for all boards."""
    print("\n")
    print("=" * 80)
    print(" BOM COST REPORT - All Boards")
    print("=" * 80)

    # Header
    print(f"\n{'Board':<12} {'Parts':<7} {'Basic':<7} {'Ext.':<7} {'@1 unit':<11} {'@10 units':<11} {'@100 units':<11}")
    print("-" * 75)

    grand_total_1 = 0
    grand_total_10 = 0
    grand_total_100 = 0

    for board in boards_data:
        if "error" in board:
            print(f"{board['name']:<12} ERROR: {board['error']}")
            continue

        name = board["name"]
        parts = board["total_parts"]
        basic = board.get("basic_count", 0)
        extended = board.get("extended_count", 0)
        t1 = board["total_1"]
        t10 = board["total_10"]
        t100 = board["total_100"]

        print(f"{name:<12} {parts:<7} {basic:<7} {extended:<7} ${t1:<10.2f} ${t10:<10.2f} ${t100:<10.2f}")

        grand_total_1 += t1
        grand_total_10 += t10
        grand_total_100 += t100

    print("-" * 75)
    total_basic = sum(b.get("basic_count", 0) for b in boards_data if "error" not in b)
    total_extended = sum(b.get("extended_count", 0) for b in boards_data if "error" not in b)
    total_parts = sum(b.get("total_parts", 0) for b in boards_data if "error" not in b)
    print(f"{'TOTAL':<12} {total_parts:<7} {total_basic:<7} {total_extended:<7} ${grand_total_1:<10.2f} ${grand_total_10:<10.2f} ${grand_total_100:<10.2f}")

    # Warnings
    print("\n" + "=" * 80)
    print(" WARNINGS")
    print("=" * 80)

    has_warnings = False
    for board in boards_data:
        if "error" in board:
            continue

        if board.get("value_errors"):
            has_warnings = True
            print(f"\n{board['name']}: VALUE MISMATCHES:")
            for err in board["value_errors"]:
                suggested = f" -> Suggested: {err['suggested']}" if err['suggested'] else ""
                print(f"  - {err['refs']}: {err['error']}{suggested}")

        if board["missing_lcsc"]:
            has_warnings = True
            print(f"\n{board['name']}: Missing LCSC codes:")
            for item in board["missing_lcsc"]:
                suggested = f" -> Suggested: {item['suggested']}" if item['suggested'] else ""
                print(f"  - {item['refs']} ({item['value']}){suggested}")

        if board["low_stock"]:
            has_warnings = True
            print(f"\n{board['name']}: Low stock warning:")
            for item in board["low_stock"]:
                print(f"  - {item}")

    if not has_warnings:
        print("\nNo warnings.")

    # CSV files generated
    print("\n" + "=" * 80)
    print(" GENERATED FILES")
    print("=" * 80)
    for board in boards_data:
        if "error" not in board:
            print(f"  - {board['name']}/{board['name']}_BOM_enriched.csv")

    print("\n")


def main():
    os.chdir(PCB_DIR)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    boards_data = []

    for sch_rel_path in discover_boards():
        sch_path = PCB_DIR / sch_rel_path
        if not sch_path.exists():
            print(f"Warning: {sch_path} not found, skipping...")
            continue

        board_data = process_board(sch_path, conn)
        boards_data.append(board_data)

    conn.close()

    print_report(boards_data)


if __name__ == "__main__":
    main()
