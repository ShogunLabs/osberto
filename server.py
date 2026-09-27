"""
Augur DRHP IPO Intelligence Server
Provides FastAPI backend with full Augur compatibility, automatic directory scanning,
real-time indexing, search, filtering, and deep financial analytics for Indian IPOs.
"""

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import glob
import json
import re
from datetime import datetime

app = FastAPI(
    title="Augur DRHP IPO Intelligence API",
    description="High-performance IPO exploration and Augur-compatible data layer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data", "drhp")
os.makedirs(DATA_DIR, exist_ok=True)

# In-memory storage of loaded IPOs
ipos_cache: Dict[str, Dict[str, Any]] = {}
last_scanned_at: Optional[datetime] = None


def slugify(text: str) -> str:
    """Generate a clean URL-friendly slug from company name."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


def determine_issue_type(issue: Dict[str, Any], name: str, industry: str) -> str:
    """
    Augur schema compatibility: classifies as 'regular' or 'sme'.
    SME IPOs in India typically have issue sizes under 25-50 Cr or specific naming.
    """
    total = (issue or {}).get("total_cr")
    fresh = (issue or {}).get("fresh_cr")
    val = total if total is not None else fresh
    if val is not None and val < 50.0:
        return "sme"
    return "regular"


def derive_symbol(name: str) -> str:
    """Generate a clean alphabetic ticker symbol from company name."""
    clean = re.sub(r"[^\w\s]", " ", name)
    boilerplate = {
        "limited", "ltd", "pvt", "private", "india", "industries",
        "services", "technologies", "corporation", "corp", "co"
    }
    words = [w.upper() for w in re.split(r"\s+", clean) if w and w.lower() not in boilerplate]
    if not words:
        words = [w.upper() for w in re.split(r"\s+", clean) if w]
    if len(words) >= 3:
        return "".join(w[0] for w in words[:4])
    elif len(words) == 2:
        return (words[0][:3] + words[1][:3])
    elif len(words) == 1:
        return words[0][:6]
    return "IPO"


def load_all_ipos() -> Dict[str, Dict[str, Any]]:
    """Scan and parse all IPO JSON files in directory."""
    global ipos_cache, last_scanned_at
    records = {}
    seen_names = {}

    # Scan dedicated data directory, with graceful fallback to BASE_DIR
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    if not json_files:
        json_files = glob.glob(os.path.join(BASE_DIR, "*.json"))

    for filepath in sorted(json_files):
        filename = os.path.basename(filepath)
        # Skip potential non-data JSONs if any
        if filename in ["package.json", "package-lock.json", "tsconfig.json"]:
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate basic IPO structure
            if not isinstance(data, dict) or "name" not in data:
                continue

            name = data.get("name", "").strip()
            if not name:
                continue

            # Deterministic unique ID
            base_slug = slugify(name)
            if base_slug in seen_names:
                seen_names[base_slug] += 1
                unique_id = f"{base_slug}-{seen_names[base_slug]}"
            else:
                seen_names[base_slug] = 1
                unique_id = base_slug

            issue = data.get("issue") or {}
            financials = data.get("financials") or []
            objects = data.get("objects") or []
            top_risks = data.get("top_risks") or []

            # Format objects with percentage calculation if fresh_cr exists
            fresh_cr = issue.get("fresh_cr")
            enhanced_objects = []
            for obj in objects:
                amt = obj.get("amount_cr")
                pct = None
                if amt is not None and fresh_cr and fresh_cr > 0:
                    pct = round((amt / fresh_cr) * 100, 1)
                enhanced_objects.append({
                    "purpose": obj.get("purpose", ""),
                    "amount_cr": amt,
                    "percentage_of_fresh": pct,
                    "source_page": obj.get("source_page")
                })

            # Format financials with calculated profit margins & YoY where possible
            enhanced_financials = []
            for i, fin in enumerate(financials):
                rev = fin.get("revenue_cr")
                pat = fin.get("pat_cr")
                margin = None
                if rev and pat and rev > 0:
                    margin = round((pat / rev) * 100, 2)

                enhanced_financials.append({
                    "fy": fin.get("fy", ""),
                    "revenue_cr": rev,
                    "pat_cr": pat,
                    "net_worth_cr": fin.get("net_worth_cr"),
                    "borrowings_cr": fin.get("borrowings_cr"),
                    "eps": fin.get("eps"),
                    "pat_margin_pct": margin,
                    "source_page": fin.get("source_page")
                })

            # Derive metrics for fast filtering
            latest_fin = enhanced_financials[0] if enhanced_financials else {}
            latest_revenue = latest_fin.get("revenue_cr")
            latest_pat = latest_fin.get("pat_cr")
            latest_eps = latest_fin.get("eps")
            latest_period = latest_fin.get("fy", "")

            # Growth calculation if at least 2 annual periods exist
            growth_pct = None
            if len(enhanced_financials) >= 2:
                r1 = enhanced_financials[0].get("revenue_cr")
                r2 = enhanced_financials[1].get("revenue_cr")
                if r1 and r2 and r2 > 0:
                    growth_pct = round(((r1 - r2) / r2) * 100, 1)

            total_cr = issue.get("total_cr")
            ofs_cr = issue.get("ofs_cr")
            issue_type = determine_issue_type(issue, name, data.get("industry", ""))
            symbol = derive_symbol(name)

            file_stat = os.stat(filepath)
            file_mtime = datetime.fromtimestamp(file_stat.st_mtime).isoformat()

            # Construct standardized record adhering both to Augur's database schema
            # and DRHP prospectus deep attributes
            record = {
                # Augur PostgreSQL schema fields
                "id": unique_id,
                "symbol": symbol,
                "name": name,
                "status": "upcoming",  # All DRHP prospectuses are pre-issue upcoming stage
                "isin": None,
                "issue_type": issue_type,
                "issue_size": total_cr if total_cr is not None else fresh_cr,
                "industry": data.get("industry", "Diversified"),
                "minimum_price": None,
                "maximum_price": None,
                "drhp_url": data.get("drhp_url", ""),
                "rhp_url": None,
                "listing_exchange": "NSE / BSE",
                
                # DRHP Deep Metadata
                "description": data.get("description", ""),
                "unit_note": data.get("unit_note", "₹ million"),
                "basis": data.get("basis", "consolidated"),
                "issue": {
                    "fresh_cr": fresh_cr,
                    "ofs_cr": ofs_cr,
                    "total_cr": total_cr,
                    "source_page": issue.get("source_page")
                },
                "objects": enhanced_objects,
                "financials": enhanced_financials,
                "promoter_holding_pre": data.get("promoter_holding_pre"),
                "promoter_holding_post": data.get("promoter_holding_post"),
                "top_risks": top_risks,

                # Calculated indicators
                "latest_revenue": latest_revenue,
                "latest_pat": latest_pat,
                "latest_eps": latest_eps,
                "latest_period": latest_period,
                "revenue_growth_pct": growth_pct,
                "is_profitable": latest_pat is not None and latest_pat > 0,
                "risk_count": len(top_risks),
                "objects_count": len(enhanced_objects),
                "financial_years_count": len(enhanced_financials),

                # System & File metadata
                "file_source": filename,
                "file_size": file_stat.st_size,
                "last_modified": file_mtime,
                "raw_data": data  # Preserved as JSONB in Augur!
            }

            records[unique_id] = record

        except Exception as e:
            print(f"Error parsing {filepath}: {e}")

    ipos_cache = records
    last_scanned_at = datetime.now()
    return ipos_cache


# Initial load at boot
load_all_ipos()


# --- API Routes ---

@app.get("/health")
def health_check():
    """Health status and metadata compatible with Augur backend."""
    return {
        "status": "ok",
        "service": "Augur DRHP IPO Intelligence Engine",
        "version": "1.0.0",
        "total_ipos_indexed": len(ipos_cache),
        "last_scanned_at": last_scanned_at.isoformat() if last_scanned_at else None,
        "augur_compatible": True
    }


@app.post("/api/v1/sync")
def sync_directory():
    """Re-scan the folder dynamically to discover any newly added or updated JSON files."""
    load_all_ipos()
    return {
        "status": "success",
        "message": f"Successfully indexed {len(ipos_cache)} IPO prospectuses",
        "total_ipos": len(ipos_cache),
        "synced_at": last_scanned_at.isoformat()
    }


@app.get("/api/v1/stats")
def get_stats():
    """Summary metrics across all indexed DRHP prospectuses."""
    items = list(ipos_cache.values())
    total_ipos = len(items)

    total_pipeline_cr = 0.0
    total_fresh_cr = 0.0
    total_ofs_cr = 0.0
    valid_size_count = 0

    industry_counts = {}
    profitable_count = 0
    total_risks_count = 0

    for ipo in items:
        issue = ipo.get("issue") or {}
        tot = issue.get("total_cr")
        fresh = issue.get("fresh_cr")
        ofs = issue.get("ofs_cr")

        if tot is not None:
            total_pipeline_cr += tot
            valid_size_count += 1
        elif fresh is not None:
            # If total is not explicitly calculated yet, count fresh
            total_pipeline_cr += fresh
            valid_size_count += 1

        if fresh is not None:
            total_fresh_cr += fresh
        if ofs is not None:
            total_ofs_cr += ofs

        ind = ipo.get("industry") or "Other"
        industry_counts[ind] = industry_counts.get(ind, 0) + 1

        if ipo.get("is_profitable"):
            profitable_count += 1

        total_risks_count += ipo.get("risk_count", 0)

    avg_issue_size = round(total_pipeline_cr / valid_size_count, 1) if valid_size_count > 0 else 0.0

    # Top industries sorted by frequency
    sorted_industries = sorted(
        [{"industry": k, "count": v} for k, v in industry_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )

    # Top 5 largest issues
    top_by_size = sorted(
        [ipo for ipo in items if ipo.get("issue_size") is not None],
        key=lambda x: x.get("issue_size") or 0,
        reverse=True
    )[:5]

    return {
        "total_ipos": total_ipos,
        "total_pipeline_cr": round(total_pipeline_cr, 2),
        "total_fresh_cr": round(total_fresh_cr, 2),
        "total_ofs_cr": round(total_ofs_cr, 2),
        "avg_issue_size_cr": avg_issue_size,
        "profitable_companies_count": profitable_count,
        "total_risk_factors_indexed": total_risks_count,
        "industries_count": len(industry_counts),
        "top_industries": sorted_industries[:8],
        "top_largest_issues": [
            {
                "id": ipo["id"],
                "name": ipo["name"],
                "industry": ipo["industry"],
                "issue_size": ipo["issue_size"],
                "fresh_cr": (ipo.get("issue") or {}).get("fresh_cr"),
                "ofs_cr": (ipo.get("issue") or {}).get("ofs_cr")
            }
            for ipo in top_by_size
        ]
    }


@app.get("/api/v1/ipos")
def list_ipos(
    search: Optional[str] = Query(None, description="Search by name, industry, or description"),
    industry: Optional[str] = Query(None, description="Filter by specific industry"),
    issue_type: Optional[str] = Query(None, description="Filter by regular or sme"),
    basis: Optional[str] = Query(None, description="Filter by consolidated or standalone"),
    min_size: Optional[float] = Query(None, description="Minimum issue size in Cr"),
    max_size: Optional[float] = Query(None, description="Maximum issue size in Cr"),
    profitable_only: Optional[bool] = Query(False, description="Show only profitable companies"),
    sort_by: Optional[str] = Query("issue_size", description="issue_size, name, latest_revenue, latest_pat, promoter_holding"),
    sort_order: Optional[str] = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Search, filter, and paginate through IPO prospectuses.
    Adheres to Augur Phase 3 pagination and query specifications.
    """
    # Auto re-scan if cache is empty
    if not ipos_cache:
        load_all_ipos()

    results = list(ipos_cache.values())

    # Text search
    if search:
        q = search.lower().strip()
        results = [
            r for r in results
            if q in r["name"].lower()
            or q in r["industry"].lower()
            or q in r.get("description", "").lower()
            or q in r["symbol"].lower()
        ]

    # Industry filter
    if industry and industry != "all":
        results = [r for r in results if r["industry"].lower() == industry.lower()]

    # Issue type filter
    if issue_type and issue_type != "all":
        results = [r for r in results if r["issue_type"].lower() == issue_type.lower()]

    # Basis filter
    if basis and basis != "all":
        results = [r for r in results if r["basis"].lower() == basis.lower()]

    # Size bounds
    if min_size is not None:
        results = [r for r in results if (r.get("issue_size") or 0) >= min_size]
    if max_size is not None:
        results = [r for r in results if (r.get("issue_size") or 0) <= max_size]

    # Profitability filter
    if profitable_only:
        results = [r for r in results if r.get("is_profitable") is True]

    # Sorting
    reverse = (sort_order.lower() == "desc")
    if sort_by == "name":
        results.sort(key=lambda x: x["name"].lower(), reverse=reverse)
    elif sort_by == "latest_revenue":
        results.sort(key=lambda x: (x.get("latest_revenue") or -999999), reverse=reverse)
    elif sort_by == "latest_pat":
        results.sort(key=lambda x: (x.get("latest_pat") or -999999), reverse=reverse)
    elif sort_by == "promoter_holding":
        results.sort(key=lambda x: (x.get("promoter_holding_pre") or -1), reverse=reverse)
    else:  # issue_size default
        results.sort(key=lambda x: (x.get("issue_size") or -1), reverse=reverse)

    total = len(results)
    start = (page - 1) * limit
    end = start + limit
    items = results[start:end]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
        "items": items
    }


@app.get("/api/v1/ipos/{ipo_id}")
def get_ipo_detail(ipo_id: str):
    """Retrieve complete DRHP detail, financial statements, and Augur mapping for a single IPO."""
    if not ipos_cache:
        load_all_ipos()

    # Match by id or slug
    ipo = ipos_cache.get(ipo_id)
    if not ipo:
        # Fallback search by name or symbol
        for item in ipos_cache.values():
            if item["id"] == ipo_id or item["symbol"].lower() == ipo_id.lower() or slugify(item["name"]) == ipo_id:
                ipo = item
                break

    if not ipo:
        raise HTTPException(status_code=404, detail=f"IPO with ID '{ipo_id}' not found.")

    return ipo


@app.get("/api/v1/compare")
def compare_ipos(ids: str = Query(..., description="Comma-separated IPO IDs e.g. 'hero-motors,moneyview'")):
    """Compare up to 4 IPOs side-by-side."""
    if not ipos_cache:
        load_all_ipos()

    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    selected = []
    for ipo_id in id_list[:5]:
        if ipo_id in ipos_cache:
            selected.append(ipos_cache[ipo_id])

    return {
        "count": len(selected),
        "comparison": selected
    }


@app.get("/api/v1/augur/export")
def export_augur_records():
    """
    Exports all current IPOs formatted directly for Augur's PostgreSQL `ipos` table.
    Enables instant compatibility/hydration into the Augur database.
    """
    if not ipos_cache:
        load_all_ipos()

    records = []
    for ipo in ipos_cache.values():
        records.append({
            "id": ipo["id"],
            "symbol": ipo["symbol"],
            "name": ipo["name"],
            "status": ipo["status"],
            "isin": ipo["isin"],
            "issue_type": ipo["issue_type"],
            "issue_size": ipo["issue_size"],
            "industry": ipo["industry"],
            "minimum_price": ipo["minimum_price"],
            "maximum_price": ipo["maximum_price"],
            "listing_exchange": ipo["listing_exchange"],
            "drhp_url": ipo["drhp_url"],
            "rhp_url": ipo["rhp_url"],
            "timeline": {
                "drhp_stage": True,
                "basis": ipo["basis"],
                "unit_note": ipo["unit_note"]
            },
            "registrar_info": {
                "source": "DRHP",
                "extracted": True
            },
            "raw_data": ipo["raw_data"],
            "first_seen_at": ipo["last_modified"],
            "last_synced_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })

    return {
        "status": "success",
        "description": "Formatted specifically for Augur PostgreSQL 'ipos' table",
        "count": len(records),
        "records": records
    }


class IPOUploadRequest(BaseModel):
    name: str
    industry: Optional[str] = "Diversified"
    description: Optional[str] = ""
    unit_note: Optional[str] = "₹ million"
    basis: Optional[str] = "consolidated"
    issue: Optional[Dict[str, Any]] = None
    objects: Optional[List[Dict[str, Any]]] = None
    financials: Optional[List[Dict[str, Any]]] = None
    promoter_holding_pre: Optional[float] = None
    promoter_holding_post: Optional[float] = None
    top_risks: Optional[List[str]] = None
    drhp_url: Optional[str] = ""


@app.post("/api/v1/ipos/create")
def create_ipo_json(payload: IPOUploadRequest):
    """
    Allows programmatically or UI-based adding a new IPO JSON file to the folder.
    Immediately saves to disk and updates the in-memory index.
    """
    clean_name = slugify(payload.name)
    filename = f"{clean_name}_DRHP.json"
    filepath = os.path.join(DATA_DIR, filename)

    data = payload.dict()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    load_all_ipos()
    return {
        "status": "created",
        "filename": filename,
        "total_ipos": len(ipos_cache),
        "id": clean_name
    }


@app.post("/api/v1/ipos/upload-file")
async def upload_json_file(file: UploadFile = File(...)):
    """Upload a new .json file directly into the folder."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted.")

    filepath = os.path.join(DATA_DIR, file.filename)
    contents = await file.read()

    # Validate JSON syntax
    try:
        parsed = json.loads(contents.decode("utf-8"))
        if not isinstance(parsed, dict) or "name" not in parsed:
            raise ValueError("JSON must be an object with at least a 'name' field.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid IPO JSON format: {str(e)}")

    with open(filepath, "wb") as f:
        f.write(contents)

    load_all_ipos()
    return {
        "status": "success",
        "filename": file.filename,
        "total_ipos": len(ipos_cache),
        "message": f"Successfully uploaded and indexed {file.filename}"
    }


# Mount static assets
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "message": "Augur DRHP IPO Intelligence Server is Running.",
        "api_docs": "/docs",
        "ipos_count": len(ipos_cache)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.py:app", host="0.0.0.0", port=8000, reload=True)
