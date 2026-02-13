"""Helper functions to extract administrative hierarchy relationships from CSV data."""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Set, Optional
from app.core.config import PROJECT_ROOT
from app.utils.logging import log_error


def load_hierarchy_from_csv(csv_path: Optional[Path] = None) -> Dict[str, Dict[str, List[str]]]:
    """
    Load administrative hierarchy relationships from the compiled dataset CSV.
    
    Returns a dictionary with structure:
    {
        "state_to_counties": {"State Name": ["County1", "County2", ...]},
        "county_to_payams": {"County Name": ["Payam1", "Payam2", ...]},
        "payam_to_bomas": {"Payam Name": ["Boma1", "Boma2", ...]}
    }
    """
    if csv_path is None:
        csv_path = PROJECT_ROOT / "resources" / "GPS point data" / "Compiled dataset.csv"
    
    if not csv_path.exists():
        return {
            "state_to_counties": {},
            "county_to_payams": {},
            "payam_to_bomas": {}
        }
    
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Check for required columns
        required_cols = ["admin1_state", "admin2_county", "admin3_payam", "admin4_boma"]
        if not all(col in df.columns for col in required_cols):
            return {
                "state_to_counties": {},
                "county_to_payams": {},
                "payam_to_bomas": {}
            }
        
        # Build state -> counties mapping
        state_to_counties: Dict[str, Set[str]] = {}
        for _, row in df.iterrows():
            state = str(row["admin1_state"]).strip() if pd.notna(row["admin1_state"]) else None
            county = str(row["admin2_county"]).strip() if pd.notna(row["admin2_county"]) else None
            if state and county:
                if state not in state_to_counties:
                    state_to_counties[state] = set()
                state_to_counties[state].add(county)
        
        # Build county -> payams mapping
        county_to_payams: Dict[str, Set[str]] = {}
        for _, row in df.iterrows():
            county = str(row["admin2_county"]).strip() if pd.notna(row["admin2_county"]) else None
            payam = str(row["admin3_payam"]).strip() if pd.notna(row["admin3_payam"]) else None
            if county and payam:
                if county not in county_to_payams:
                    county_to_payams[county] = set()
                county_to_payams[county].add(payam)
        
        # Build payam -> bomas mapping
        payam_to_bomas: Dict[str, Set[str]] = {}
        for _, row in df.iterrows():
            payam = str(row["admin3_payam"]).strip() if pd.notna(row["admin3_payam"]) else None
            boma = str(row["admin4_boma"]).strip() if pd.notna(row["admin4_boma"]) else None
            if payam and boma:
                if payam not in payam_to_bomas:
                    payam_to_bomas[payam] = set()
                payam_to_bomas[payam].add(boma)
        
        # Convert sets to sorted lists
        return {
            "state_to_counties": {k: sorted(list(v)) for k, v in state_to_counties.items()},
            "county_to_payams": {k: sorted(list(v)) for k, v in county_to_payams.items()},
            "payam_to_bomas": {k: sorted(list(v)) for k, v in payam_to_bomas.items()}
        }
    
    except Exception as e:
        log_error(e, {
            "module": "admin_hierarchy",
            "function": "load_hierarchy_from_csv",
            "csv_path": str(csv_path)
        })
        return {
            "state_to_counties": {},
            "county_to_payams": {},
            "payam_to_bomas": {}
        }


def get_all_states(csv_path: Optional[Path] = None) -> List[str]:
    """Get all unique state names from the CSV."""
    if csv_path is None:
        csv_path = PROJECT_ROOT / "resources" / "GPS point data" / "Compiled dataset.csv"
    
    if not csv_path.exists():
        return []
    
    try:
        df = pd.read_csv(csv_path)
        if "admin1_state" not in df.columns:
            return []
        states = df["admin1_state"].dropna().unique().tolist()
        return sorted([str(s).strip() for s in states if str(s).strip()])
    except Exception:
        return []


def get_all_counties(csv_path: Optional[Path] = None) -> List[str]:
    """Get all unique county names from the CSV."""
    if csv_path is None:
        csv_path = PROJECT_ROOT / "resources" / "GPS point data" / "Compiled dataset.csv"
    
    if not csv_path.exists():
        return []
    
    try:
        df = pd.read_csv(csv_path)
        if "admin2_county" not in df.columns:
            return []
        counties = df["admin2_county"].dropna().unique().tolist()
        return sorted([str(c).strip() for c in counties if str(c).strip()])
    except Exception:
        return []


def get_all_payams(csv_path: Optional[Path] = None) -> List[str]:
    """Get all unique payam names from the CSV."""
    if csv_path is None:
        csv_path = PROJECT_ROOT / "resources" / "GPS point data" / "Compiled dataset.csv"
    
    if not csv_path.exists():
        return []
    
    try:
        df = pd.read_csv(csv_path)
        if "admin3_payam" not in df.columns:
            return []
        payams = df["admin3_payam"].dropna().unique().tolist()
        return sorted([str(p).strip() for p in payams if str(p).strip()])
    except Exception:
        return []


def get_all_bomas(csv_path: Optional[Path] = None) -> List[str]:
    """Get all unique boma names from the CSV."""
    if csv_path is None:
        csv_path = PROJECT_ROOT / "resources" / "GPS point data" / "Compiled dataset.csv"
    
    if not csv_path.exists():
        return []
    
    try:
        df = pd.read_csv(csv_path)
        if "admin4_boma" not in df.columns:
            return []
        bomas = df["admin4_boma"].dropna().unique().tolist()
        return sorted([str(b).strip() for b in bomas if str(b).strip()])
    except Exception:
        return []

