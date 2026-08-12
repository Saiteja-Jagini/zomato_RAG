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
6. Use `fig, ax = plt.subplots(...)`, `fig.tight_layout()`, and save at 150 DPI or higher.
7. Create `/outputs` when needed, save the figure as PNG, and call `plt.close(fig)`.
8. Verify the output file exists and report its path with the main visual insight.

