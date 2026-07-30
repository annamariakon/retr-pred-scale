import pandas as pd
from shapely import wkt
from matplotlib import ticker, colors, cm
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np

def function_neighborhood_maps(gdf_results_init, mean_by_building_year_output, year_idx):

    path_to_data = "kralingseveer_buildings_27_2.shp"
    gdf = gpd.read_file(path_to_data)
    output_cols = [
        "heating_dem_m2",
        "cooling_dem_m2",
        "underheat_m2",
        "overheat_m2",
        "heating_gas_m2",
        "heating_elec_m2",
        "cooling_elec_m2",
        "carbon_emissions",
    ]

    val_idxs = [0, 1, 6, 7, 2, 3, 5, 8]

    output_labels = [
        "Heating demand\n(kWh/m²)",
        "Cooling demand\n(kWh/m²)",
        "Underheating hours\n(hours/m²)",
        "Overheating hours\n(hours/m²)",
        "Gas consumption\n(kWh/m²)",
        "Electricity consumption, heating\n(kWh/m²)",
        "Electricity consumption, cooling\n(kWh/m²)",
        "Carbon emissions\n(kgCO₂eq/m²)",
    ]

    output_cmaps = [
        "RdYlGn_r",
        "RdYlGn_r",
        "summer",
        "RdYlBu_r",
        "Spectral_r",
        "Spectral_r",
        "Spectral_r",
        "coolwarm",
    ]

    # Build the GeoDataFrame once
    gdf_plot = gdf_results_init.copy()

    gdf_plot["geometry_gdf"] = gdf_plot["geometry_gdf"].apply(
        lambda value: wkt.loads(value)
        if isinstance(value, str)
        else value
    )

    gdf_plot = gpd.GeoDataFrame(
        gdf_plot,
        geometry="geometry_gdf",
        crs=gdf.crs,
    )

    # One subplot per output variable: 4 rows × 2 columns
    fig, axes = plt.subplots(
        nrows=4,
        ncols=2,
        figsize=(11, 16),
        dpi=300,
    )

    fig.subplots_adjust(
        left=0.04,
        right=0.91,
        top=0.95,
        bottom=0.04,
        wspace=0.22,
        hspace=0.12,
    )

    axes = axes.flatten()

    for output_idx, (col_name, label, val_idx, cmap) in enumerate(
        zip(output_cols, output_labels, val_idxs, output_cmaps)
    ):
        ax = axes[output_idx]

        # Only probabilistic values
        vals = mean_by_building_year_output[:, year_idx, val_idx].copy()

        finite_vals = vals[np.isfinite(vals)]

        if finite_vals.size == 0:
            ax.text(
                0.5,
                0.5,
                "No valid data",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=11,
            )
            ax.set_axis_off()
            continue

        ticks = None

        # Special logarithmic scale for underheating
        if col_name == "underheat_m2":
            # LogNorm cannot display zero or negative values
            vals_for_plot = vals.copy()
            vals_for_plot[vals_for_plot <= 0] = 0.01

            positive_vals = vals_for_plot[
                np.isfinite(vals_for_plot) & (vals_for_plot > 0)
            ]

            vmin = 0.01
            vmax = positive_vals.max()

            if np.isclose(vmin, vmax):
                vmax = vmin * 10

            norm = colors.LogNorm(
                vmin=vmin,
                vmax=vmax,
            )

            candidate_ticks = [0.01, 0.1, 0.3, 1, 10, 30, 100, 300, 720]

            ticks = [
                value
                for value in candidate_ticks
                if vmin <= value <= vmax
            ]

        else:
            vals_for_plot = vals

            vmin = np.nanmin(finite_vals)
            vmax = np.nanmax(finite_vals)

            if np.isclose(vmin, vmax):
                padding = max(abs(vmin) * 0.01, 1e-6)
                vmin -= padding
                vmax += padding

            norm = colors.Normalize(
                vmin=vmin,
                vmax=vmax,
            )

        gdf_plot["plot_value"] = vals_for_plot

        gdf_plot.plot(
            column="plot_value",
            cmap=cmap,
            norm=norm,
            linewidth=0.1,
            edgecolor="gray",
            legend=False,
            ax=ax,
            missing_kwds={
                "color": "lightgray",
                "edgecolor": "gray",
            },
        )

        ax.set_axis_off()

        # Colorbar to the right of each map
        scalar_map = cm.ScalarMappable(
            norm=norm,
            cmap=cmap,
        )
        scalar_map.set_array([])

        cbar_ax = ax.inset_axes([
            1.02,   # x position
            0.12,   # y position
            0.035,  # width
            0.76,   # height
        ])

        cbar = fig.colorbar(
            scalar_map,
            cax=cbar_ax,
            orientation="vertical",
        )

        if ticks:
            cbar.set_ticks(ticks)
            cbar.ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
            cbar.ax.yaxis.set_minor_formatter(ticker.NullFormatter())
            cbar.minorticks_off()

        cbar.ax.tick_params(
            labelsize=8,
            length=2,
        )
        cbar.set_label(label, rotation=90, labelpad=10, fontsize=10, fontweight="bold")
        cbar.ax.yaxis.set_label_position("right")
        cbar.ax.yaxis.set_ticks_position("right")

    plt.show()