import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t

def calculate_mean_ci_by_year(
    df,
    output_cols,
    year_values,
    confidence,
    dtype=np.float32
):
    """
    Calculates mean and confidence intervals across simulations
    for each year and output variable.

    Returns arrays with shape:
        (n_years, n_outputs)
    """

    grouped = df.groupby("year")[output_cols]

    mean_df = grouped.mean().reindex(year_values)
    std_df = grouped.std(ddof=0).reindex(year_values)
    count_df = grouped.count().reindex(year_values)

    se_df = std_df / np.sqrt(count_df)

    alpha = 1 - confidence
    tcrit_df = count_df.apply(lambda x: t.ppf(1 - alpha / 2, x - 1))

    ci_half_width_df = tcrit_df * se_df

    lower_df = mean_df - ci_half_width_df
    upper_df = mean_df + ci_half_width_df

    return {
        "mean": mean_df.to_numpy(dtype=dtype),
        "lower": lower_df.to_numpy(dtype=dtype),
        "upper": upper_df.to_numpy(dtype=dtype),
        "se": se_df.to_numpy(dtype=dtype),
        "n": count_df.to_numpy(dtype=dtype),
    }

def function_cumulative_sums_neighborhood(city_sum_mean, city_lower, city_upper, building_lifetime):
    
    output_cols = [
    "heating_dem_m2",
    "cooling_dem_m2",
    "heating_gas_m2",
    "heating_elec_m2",
    "heating_distr_heat_m2",
    "cooling_elec_m2",
    "underheat_m2",
    "overheat_m2",
    "carbon_emissions",
    ]

    output_labels = [
        "Heating demand",
        "Cooling demand",
        "Gas consumption",
        "Electricity (heating)",
        "District heating",
        "Electricity (cooling)",
        "Underheating",
        "Overheating",
        "Carbon emissions",
    ]

    output_units = [
        "(kWh/m²)",
        "(kWh/m²)",
        "(kWh/m²)",
        "(kWh/m²)",
        "(kWh/m²)",
        "(kWh/m²)",
        "(hours)",
        "(hours)",
        "(kgCO₂eq/m²)",
    ]

    # Years 0, 5, 10, ..., 70
    years_to_plot = np.arange(0, building_lifetime, 5)

    fig, axes = plt.subplots(
        nrows=len(output_cols),
        ncols=1,
        figsize=(16, 3.5 * len(output_cols)),
        dpi=300,
        sharex=True,
        gridspec_kw={"hspace": 0.08},
    )

    axes = np.atleast_1d(axes)

    # One x-position for every five-year interval
    x = np.arange(len(years_to_plot))

    # Optional gradient showing progression through time
    colors_years = plt.get_cmap("Spectral")(
        np.linspace(0, 1, len(years_to_plot))
    )

    for row_idx, output_name in enumerate(output_cols):
        ax = axes[row_idx]

        values = city_sum_mean[years_to_plot, row_idx]
        lower = city_lower[years_to_plot, row_idx]
        upper = city_upper[years_to_plot, row_idx]

        # Prevent tiny floating-point differences from creating negative errors
        lower_error = np.maximum(values - lower, 0)
        upper_error = np.maximum(upper - values, 0)

        yerr = np.vstack([
            lower_error,
            upper_error,
        ])

        ax.bar(
            x,
            values,
            width=0.72,
            color=colors_years,
            yerr=yerr,
            ecolor="black",
            capsize=3,
            error_kw={
                "elinewidth": 1.2,
                "capthick": 1.2,
            },
        )

        ax.set_ylabel(
            f"{output_labels[row_idx]}\n{output_units[row_idx]}",
            fontsize=12,
            fontweight="bold",
        )

        ax.tick_params(
            axis="both",
            labelsize=11,
        )

        ax.grid(
            axis="y",
            alpha=0.25,
        )

        ax.set_axisbelow(True)

    # One tick every five years
    axes[-1].set_xticks(x)

    axes[-1].set_xticklabels(
        years_to_plot,
        fontsize=11,
        fontweight="bold",
    )

    axes[-1].set_xlabel(
        "Year",
        fontsize=13,
        fontweight="bold",
    )

    fig.subplots_adjust(
        left=0.15,
        right=0.98,
        top=0.97,
        bottom=0.06,
    )

    plt.show()