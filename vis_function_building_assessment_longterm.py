import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mpl_toolkits.axes_grid1 import make_axes_locatable

def function_building_assessment_longterm(records_res_time, bag_pand_id):

    df_records = pd.DataFrame(records_res_time)

    df_records['overheat_m2'] = (df_records['overheat_m2'].clip(lower=0))
    df_records['underheat_m2'] = (df_records['underheat_m2'].clip(lower=0))
    year_min = 1
    year_max = 69
    n_lines = 10
    df_records = df_records[(df_records["year"] >= year_min)].copy()
    variables = [
        ("heating_dem_m2", "Heating demand (kWh/m²)"),
        ("cooling_dem_m2", "Cooling demand (kWh/m²)"),
        ("overheat_m2", "Overheating hours (h/m²)"),
        ("underheat_m2", "Underheating hours (h/m²)"),
        ("heating_gas_m2", "Heating gas (kWh/m²)"),
        ("heating_elec_m2", "Heating electricity (kWh/m²)"),
        ("heating_distr_heat_m2", "District heating distribution (kWh/m²)"),
        ("cooling_elec_m2", "Cooling electricity (kWh/m²)"),
    ]

    cmap = plt.get_cmap("tab20b")
    hist_start_color = "steelblue"
    hist_end_color = "darkcyan"

    # Histogram styling: narrower side panels and thinner horizontal bins
    hist_axis_size = "12%"
    hist_bar_height_scale = 0.7
    hist_n_bins = 20

    # Y tick-label spacing for the left/main axis (outside the plot).
    y_tick_pad = 28

    def select_representative_sims(df, value_col, ref_year, n_select=10):
        ref = df[df["year"] == ref_year][["sim", value_col]].dropna().drop_duplicates("sim")
        if ref.empty:
            return []

        n_select = min(n_select, len(ref))
        targets = np.linspace(ref[value_col].min(), ref[value_col].max(), n_select)

        remaining = ref.copy()
        selected = []
        for target in targets:
            idx = (remaining[value_col] - target).abs().idxmin()
            selected.append(remaining.loc[idx, "sim"])
            remaining = remaining.drop(index=idx)
            if remaining.empty:
                break
        return selected

    def add_side_histograms(main_ax, dataset, var, y_min, y_max):
        vals_start = dataset[dataset["year"] == year_min][var].dropna()
        vals_end = dataset[dataset["year"] == year_max][var].dropna()

        divider = make_axes_locatable(main_ax)
        ax_left = divider.append_axes("left", size=hist_axis_size, pad=0.04, sharey=main_ax)
        ax_right = divider.append_axes("right", size=hist_axis_size, pad=0.04, sharey=main_ax)

        for vals, hist_ax, hist_color in [
            (vals_start, ax_left, hist_start_color),
            (vals_end, ax_right, hist_end_color),
        ]:
            counts, bin_edges = np.histogram(vals, bins=hist_n_bins, range=(y_min, y_max))
            hist_ax.barh(
                bin_edges[:-1],
                counts,
                height=np.diff(bin_edges) * hist_bar_height_scale,
                align="edge",
                color=hist_color,
                alpha=0.8,
            )
            for spine in hist_ax.spines.values():
                spine.set_visible(False)
            hist_ax.tick_params(axis="x", bottom=False, labelbottom=False)
            hist_ax.tick_params(axis="y", left=False, labelleft=False)
            hist_ax.grid(False)

        ax_left.invert_xaxis()

    n_rows = len(variables)
    fig, axes = plt.subplots(n_rows, 1, figsize=(8, 2.9 * n_rows), dpi=300, sharex=True)

    # Ensure 2D indexing even when n_rows == 1
    if n_rows == 1:
        axes = np.array([axes])

    for row_idx, (var, y_label) in enumerate(variables):
        ax_prob = axes[row_idx]

        line_color = cmap((row_idx * 4) % 20)

        sims = select_representative_sims(df_records, var, year_min, n_lines)
        y_min = df_records[var].min() - 2
        y_max = df_records[var].max() + 2
        # Plot probabilistic + side histograms
        for sim_id in sims:
            group = df_records[df_records["sim"] == sim_id]
            ax_prob.plot(group["year"], group[var], color=line_color, alpha=0.65, linewidth=1.0)
        mean_prob = df_records.groupby("year")[var].mean()
        ax_prob.plot(mean_prob.index, mean_prob.values, color="midnightblue", linewidth=2.0)
        ax_prob.set_xlim(year_min, year_max)
        ax_prob.set_ylim(y_min, y_max)
        ax_prob.tick_params(axis="both", labelsize=10)
        ax_prob.tick_params(axis="y", pad=50)
        ax_prob.grid(True, which="major", linestyle="-", linewidth=0.5, alpha=0.45)
        ax_prob.set_ylabel(y_label, fontsize=10, labelpad=10)

        add_side_histograms(ax_prob, df_records, var, y_min, y_max)

        # if row_idx == 0:
        #     ax_prob.set_title("Probabilistic initialization", fontsize=10, fontweight="bold")

        if row_idx == n_rows - 1:
            ax_prob.set_xlabel("Year", fontsize=11)

    legend_handles = [
        Line2D([0], [0], color="0.4", alpha=0.85, linewidth=1.5, label="Selected trajectories (10)"),
        Line2D([0], [0], color="midnightblue", linewidth=2.0, label="Mean"),
        Line2D([0], [0], color=hist_start_color, linewidth=8, alpha=0.8, label=f"Distribution year {year_min}"),
        Line2D([0], [0], color=hist_end_color, linewidth=8, alpha=0.8, label=f"Distribution year {year_max}"),
    ]

    fig.suptitle(f"BAG {bag_pand_id}", fontsize=15, fontweight="bold")
    fig.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, 0.027), ncol=4, frameon=False, fontsize=10)
    plt.tight_layout(rect=[0, 0.03, 1, 0.98])
    plt.show()