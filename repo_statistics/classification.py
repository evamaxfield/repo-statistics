#!/usr/bin/env python


def get_heuristic_project_type(
    starsgazers_count: int,
    total_contibutors_count: int,
) -> str:
    # This is a simple heuristic classification from Nadia Eghbal's "Working in Public"
    # This formulation is based on Sean Goggins' work

    # Compute ratio
    try:
        ratio_stargazers_to_contribs = starsgazers_count / total_contibutors_count
    except ZeroDivisionError:
        return "undefined"

    # Categorize
    if total_contibutors_count <= 5 and ratio_stargazers_to_contribs < 5:
        return "single-experiment"  # toy

    if total_contibutors_count > 5 and ratio_stargazers_to_contribs < 5:
        return "lab-level-tool"  # club

    if total_contibutors_count > 20 and ratio_stargazers_to_contribs >= 5:
        return "field-level-tool"  # federation

    if total_contibutors_count <= 20 and ratio_stargazers_to_contribs >= 5:
        return "specialized-instrument"  # stadium

    # "undefined" is the label for repos that do not fit into any of the above
    return "undefined"
