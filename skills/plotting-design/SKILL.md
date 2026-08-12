---
name: plotting-design
description: Create or improve Matplotlib and Seaborn charts from tabular data. Use for plotting, chart selection, statistical visualization, visual design, and PNG figure generation.
---

# Plotting design

1. Inspect the source data, column types, missing values, and units before plotting.
2. Choose the simplest chart that answers the question:
   - comparison: sorted bar chart
   - trend: line chart
   - distribution: histogram, box plot, or violin plot
   - relationship: scatter plot with an optional fitted trend
   - composition: stacked bar chart; avoid pie charts when categories are numerous
3. Aggregate explicitly and document filters. Never silently discard invalid rows.
4. Use a colorblind-friendly palette, readable type sizes, clear units, and concise titles.
5. Avoid 3D effects, decorative backgrounds, misleading axes, and unnecessary legends.
6. Use `fig, ax = plt.subplots(...)` and `fig.tight_layout()`.
7. When using `execute_plot_script`, do not import modules, call `show()`, call
   `savefig()`, or access files. The isolated runner saves and closes the figure
   using the DPI configured in the database-backed skill record.
8. Verify the tool reports success and return its PNG path with the main visual
   insight.
