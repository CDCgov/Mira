def discrete_background_color_bins(df, n_bins=5, columns="all"):
    # from dash import html
    import colorlover
    bounds = [i * (1.0 / n_bins) for i in range(n_bins + 1)]
    if columns == "all":
        if "id" in df:
            df_numeric_columns = df.select_dtypes("number").drop(["id"], axis=1)
        else:
            df_numeric_columns = df.select_dtypes("number")
    else:
        df_noUndetermined = df[df["Sample"] != "Undetermined"]
        df_numeric_columns = df_noUndetermined[columns]
    styles = []
    legend = []
    ranges = {}
    for column in df_numeric_columns:
        df_max = df_numeric_columns[column].max()
        df_min = df_numeric_columns[column].min()
        ranges[column] = [((df_max - df_min) * i) + df_min for i in bounds]
        for i in range(1, len(bounds)):
            min_bound = ranges[column][i - 1]
            max_bound = ranges[column][i]
            backgroundColor = colorlover.scales[str(n_bins)]["seq"]["PuBuGn"][i - 1]
            # 			backgroundColor = colorlover.scales[str(n_bins)]['div']['RdYlBu'][i - 1]
            color = "white" if i > len(bounds) / 2.0 else "inherit"
            styles.append(
                {
                    "if": {
                        "filter_query": (
                            "{{{column}}} >= {min_bound}"
                            + (
                                " && {{{column}}} < {max_bound}"
                                if (i < len(bounds) - 1)
                                else ""
                            )
                        ).format(
                            column=column, min_bound=min_bound, max_bound=max_bound
                        ),
                        "column_id": column,
                    },
                    "backgroundColor": backgroundColor,
                    "color": color,
                }
            )
    return styles  # , html.Div(legend, style={'padding': '5px 0 5px 0'}))

