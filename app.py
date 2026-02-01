import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Delhi in Motion — Uber 2024", layout="wide")
px.defaults.color_discrete_sequence = px.colors.qualitative.Set2
px.defaults.template = "plotly_white"


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Standardize columns to snake_case-ish (handles spaces)
    df.columns = [c.strip().replace(" ", "_").replace("-", "_") for c in df.columns]

    # Expected columns in your dataset after cleaning names:
    # Date, Time, Booking_Status, Vehicle_Type, Payment_Method, Avg_VTAT, Avg_CTAT,
    # Booking_Value, Ride_Distance, Driver_Ratings, Customer_Rating, etc.

    # Parse dates (assumes YYYY-MM-DD)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Parse time if present (optional)
    if "Time" in df.columns:
        # Keep as string; extract hour if possible
        t = pd.to_datetime(df["Time"], errors="coerce")
        df["Hour"] = t.dt.hour

    # Coerce numeric columns (handles 'null' strings)
    num_cols = ["Avg_VTAT", "Avg_CTAT", "Booking_Value", "Ride_Distance",
                "Driver_Ratings", "Customer_Rating"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # A unified outcome column (use Booking_Status if present)
    if "Booking_Status" in df.columns:
        df["Ride_Outcome"] = df["Booking_Status"].fillna("Unknown")
    else:
        df["Ride_Outcome"] = "Unknown"

    # A flag for cancellation vs completed
    df["is_completed"] = df["Ride_Outcome"].eq("Completed")
    df["is_cancelled"] = ~df["is_completed"]

    # Distance tiers for fare histograms
    if "Ride_Distance" in df.columns:
        bins = [0, 10, 25, 50]
        labels = ["0–10 km", "10–25 km", "25–50 km"]
        df["Distance_Tier"] = pd.cut(df["Ride_Distance"], bins=bins, labels=labels,
                                     include_lowest=True, right=False)
    return df

# ---- Header
st.title("Delhi in Motion — Uber Rides (2024)")
st.caption("Dashboard focusing on outcomes, cancellations, fares, and ratings.")

st.markdown(
    """
**What you can do here**
- Filter rides by date, vehicle, payment, and outcome  
- Explore cancellations, fares, and ratings interactively  
- Use the plots to locate patterns worth discussing in the report
"""
)

# ---- Load
DATA_PATH = "ncr_ride_bookings.csv"
df = load_data(DATA_PATH)

# ---- Sidebar filters
st.sidebar.header("Filters")

# Date range
if "Date" in df.columns and df["Date"].notna().any():
    min_d = df["Date"].min()
    max_d = df["Date"].max()
    date_range = st.sidebar.date_input("Date range", value=(min_d.date(), max_d.date()))
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df_f = df[(df["Date"] >= start) & (df["Date"] <= end)]
    else:
        df_f = df.copy()
else:
    df_f = df.copy()

# Booking status
if "Ride_Outcome" in df_f.columns:
    outcomes = sorted(df_f["Ride_Outcome"].dropna().unique().tolist())
    sel_outcomes = st.sidebar.multiselect("Booking status", outcomes, default=outcomes)
    df_f = df_f[df_f["Ride_Outcome"].isin(sel_outcomes)]

# Vehicle type
if "Vehicle_Type" in df_f.columns:
    vehicles = sorted(df_f["Vehicle_Type"].dropna().unique().tolist())
    sel_veh = st.sidebar.multiselect("Vehicle type", vehicles, default=vehicles)
    df_f = df_f[df_f["Vehicle_Type"].isin(sel_veh)]

# Payment method (only meaningful when completed; still allow filter)
if "Payment_Method" in df_f.columns:
    pays = sorted(df_f["Payment_Method"].dropna().unique().tolist())
    sel_pay = st.sidebar.multiselect("Payment method", pays, default=pays)
    if len(sel_pay) > 0:
        df_f = df_f[(df_f["Payment_Method"].isin(sel_pay)) | (df_f["Payment_Method"].isna())]

# ---- KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{len(df_f):,}")
if "Booking_ID" in df_f.columns:
    c2.metric("Unique bookings", f"{df_f['Booking_ID'].nunique():,}")
c3.metric("Completed (%)", f"{(df_f['is_completed'].mean()*100):.1f}%")
if "Avg_VTAT" in df_f.columns:
    c4.metric("Avg VTAT (min)", f"{df_f['Avg_VTAT'].dropna().mean():.1f}")

if {"Booking_Value", "Ride_Distance"}.issubset(df_f.columns):
    comp = df_f[df_f["is_completed"]].dropna(subset=["Booking_Value", "Ride_Distance"])
    if len(comp) > 0:
        c3, c4, c5, c6 = st.columns(4)
        c3.metric("Median fare (₹)", f"{comp['Booking_Value'].median():.0f}")
        c4.metric("Median dist (km)", f"{comp['Ride_Distance'].median():.1f}")
        c5.metric("Avg CTAT (min)", f"{comp['Avg_CTAT'].dropna().mean():.1f}" if "Avg_CTAT" in comp else "—")
        c6.metric("Avg rating", f"{comp['Customer_Rating'].dropna().mean():.2f}" if "Customer_Rating" in comp else "—")


st.divider()

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Cancellations", "Fares", "Ratings"])

# ---- Overview
with tab1:
    left, right = st.columns([1, 1])

    with left:
        outcome_counts = df_f["Ride_Outcome"].value_counts(dropna=False).reset_index()
        outcome_counts.columns = ["Ride_Outcome", "Count"]
        fig = px.bar(outcome_counts, x="Count", y="Ride_Outcome", orientation="h",
                     title="Ride Outcomes")
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        if "Hour" in df_f.columns and df_f["Hour"].notna().any():
            hourly = df_f.groupby("Hour")["is_cancelled"].mean().reset_index()
            hourly["cancel_rate"] = hourly["is_cancelled"] * 100
            fig2 = px.line(hourly, x="Hour", y="cancel_rate",
                           title="Cancellation rate by hour (%)")
            fig2.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Hour column not available (or Time parsing failed).")


with tab1:
    st.subheader("Top pickup and drop locations")
    cA, cB = st.columns(2)

    with cA:
        if "Pickup_Location" in df_f.columns:
            top_pick = df_f["Pickup_Location"].value_counts().head(10).reset_index()
            top_pick.columns = ["Pickup_Location", "Rides"]
            st.dataframe(top_pick, use_container_width=True, height=300)

    with cB:
        if "Drop_Location" in df_f.columns:
            top_drop = df_f["Drop_Location"].value_counts().head(10).reset_index()
            top_drop.columns = ["Drop_Location", "Rides"]
            st.dataframe(top_drop, use_container_width=True, height=300)

# ---- Cancellations
with tab2:
    colA, colB = st.columns(2)

    # cancellation rate by vehicle
    with colA:
        if "Vehicle_Type" in df_f.columns:
            tmp = df_f.groupby("Vehicle_Type")["is_cancelled"].mean().reset_index()
            tmp["cancel_rate"] = tmp["is_cancelled"] * 100
            tmp = tmp.sort_values("cancel_rate", ascending=False)
            fig = px.bar(tmp, x="cancel_rate", y="Vehicle_Type", orientation="h",
                         title="Cancellation rate by vehicle type (%)")
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)

    # cancellation rate by payment method (completed-only)
    with colB:
        if "Payment_Method" in df.columns:
            comp = df_f[df_f["is_completed"] & df_f["Payment_Method"].notna()].copy()
            if len(comp) > 0:
                tmp2 = comp.groupby("Payment_Method")["is_cancelled"].mean().reset_index()
                tmp2["cancel_rate"] = tmp2["is_cancelled"] * 100
                tmp2 = tmp2.sort_values("cancel_rate", ascending=False)
                fig2 = px.bar(tmp2, x="cancel_rate", y="Payment_Method", orientation="h",
                              title="Cancellation rate by payment method (completed subset) (%)")
                fig2.update_layout(height=420)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No completed rides with payment info under current filters.")

    # VTAT by outcome
    if "Avg_VTAT" in df_f.columns:
        fig3 = px.box(df_f.dropna(subset=["Avg_VTAT"]),
                      x="Ride_Outcome", y="Avg_VTAT",
                      title="Wait time (VTAT) by ride outcome")
        fig3.update_layout(height=420)
        st.plotly_chart(fig3, use_container_width=True)

    if "Hour" in df_f.columns and "Vehicle_Type" in df_f.columns:
        tmp = df_f.dropna(subset=["Hour","Vehicle_Type"]).copy()
        tmp["is_cancel"] = ~tmp["Ride_Outcome"].eq("Completed")
        heat = tmp.groupby(["Vehicle_Type","Hour"])["is_cancel"].mean().reset_index()
        heat["cancel_rate"] = heat["is_cancel"] * 100

        fig = px.density_heatmap(
            heat, x="Hour", y="Vehicle_Type", z="cancel_rate",
            color_continuous_scale="Viridis",
            title="Cancellation rate by vehicle type and hour (%)"
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

# ---- Fares
with tab3:
    comp = df_f[df_f["is_completed"]].copy()

    col1, col2 = st.columns([1.2, 0.8])

    with col1:
        if {"Ride_Distance", "Booking_Value"}.issubset(comp.columns):
            dd = comp.dropna(subset=["Ride_Distance", "Booking_Value"])
            fig = px.scatter(dd, x="Ride_Distance", y="Booking_Value",
                             color="Vehicle_Type" if "Vehicle_Type" in dd.columns else None,
                             opacity=0.35,
                             title="Fare vs Distance (completed rides)")
            fig.update_layout(height=480)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Need Ride_Distance and Booking_Value columns for the scatterplot.")

    with col2:
        if "Distance_Tier" in comp.columns and "Booking_Value" in comp.columns:
            dd = comp.dropna(subset=["Distance_Tier", "Booking_Value"])
            fig2 = px.histogram(dd, x="Booking_Value", facet_col="Distance_Tier",
                                nbins=30, title="Fare distribution by distance tier")
            fig2.update_layout(height=480)
            st.plotly_chart(fig2, use_container_width=True)

# ---- Ratings
with tab4:
    c1, c2 = st.columns(2)

    with c1:
        if {"Customer_Rating", "Driver_Ratings"}.issubset(df_f.columns):
            rr = df_f[df_f["is_completed"]].dropna(subset=["Customer_Rating", "Driver_Ratings"])
            fig = px.scatter(rr, x="Driver_Ratings", y="Customer_Rating",
                             opacity=0.35,
                             title="Driver rating vs Customer rating (completed rides)")
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ratings columns not available.")

    with c2:
        if "Customer_Rating" in df_f.columns:
            rr = df_f[df_f["is_completed"]].dropna(subset=["Customer_Rating"])
            fig2 = px.histogram(rr, x="Customer_Rating", nbins=20,
                                title="Customer rating distribution (completed rides)")
            fig2.update_layout(height=420)
            st.plotly_chart(fig2, use_container_width=True)

# Download button
csv_bytes = df_f.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    "Download filtered data (CSV)",
    data=csv_bytes,
    file_name="uber_filtered.csv",
    mime="text/csv"
)