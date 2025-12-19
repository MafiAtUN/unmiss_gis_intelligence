"""Diagnostics page for monitoring performance and cache statistics."""
import streamlit as st
from app.core.duckdb_store import DuckDBStore
from app.core.config import DUCKDB_PATH
from datetime import datetime, timedelta


# Initialize session state if not already initialized
if "db_store" not in st.session_state:
    st.session_state.db_store = DuckDBStore(DUCKDB_PATH)

st.title("🔧 Diagnostics")

db_store: DuckDBStore = st.session_state.db_store

# Cache statistics
st.subheader("Cache Statistics")
cache_stats = db_store.get_cache_stats()

col1, col2 = st.columns(2)
with col1:
    st.metric("Total cache entries", cache_stats["total_entries"])
with col2:
    st.metric("Unique queries", cache_stats["unique_queries"])

# Recent queries
st.subheader("Recent Queries")
recent_queries = db_store.conn.execute("""
    SELECT input_text, normalized_text, resolved_layer, matched_name, score,
           lon, lat, created_at
    FROM geocode_cache
    ORDER BY created_at DESC
    LIMIT 20
""").fetchall()

if recent_queries:
    import pandas as pd
    
    df = pd.DataFrame(recent_queries, columns=[
        "Input", "Normalized", "Layer", "Matched", "Score",
        "Lon", "Lat", "Timestamp"
    ])
    
    st.dataframe(df, use_container_width=True)
else:
    st.info("No cached queries yet")

# Database info
st.subheader("Database Information")
db_path = db_store.db_path
db_size = db_path.stat().st_size if db_path.exists() else 0

col1, col2 = st.columns(2)
with col1:
    st.text(f"Database path: {db_path}")
with col2:
    st.text(f"Database size: {db_size / 1024 / 1024:.2f} MB")

# Layer statistics
st.subheader("Layer Statistics")
from app.core.config import LAYER_NAMES

layer_stats = []
for layer_name in LAYER_NAMES.values():
    count = db_store.conn.execute(
        f"SELECT COUNT(*) FROM {layer_name}"
    ).fetchone()[0]
    layer_stats.append({"Layer": layer_name, "Features": count})

if layer_stats:
    import pandas as pd
    st.dataframe(pd.DataFrame(layer_stats), use_container_width=True)

# Name index statistics
st.subheader("Name Index Statistics")
index_count = db_store.conn.execute(
    "SELECT COUNT(*) FROM name_index"
).fetchone()[0]
st.metric("Index entries", index_count)

# Clear cache
st.subheader("Cache Management")
if st.button("Clear Cache", type="secondary"):
    db_store.conn.execute("DELETE FROM geocode_cache")
    # DuckDB is autocommit
    st.success("Cache cleared")
    st.rerun()

