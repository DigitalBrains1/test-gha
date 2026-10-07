#!/usr/bin/env python3

import json
import os
import sys


###############################################################################
# UTILITY FUNCTIONS                                                           #
###############################################################################


def nub_sort(xs):
    """Remove duplicates from a list of JSON entries and sort them lexicographically"""

    # Output of json.dumps with sorted object keys actually sorts nicely
    # lexicographically and equality is simply string equality. Equality does consider
    # order of list elements, though, a wrinkle we deal with by sorting `recipes` below.
    # This way list order is not considered for equality in practice.

    as_json = sorted(
        [(json.dumps(e, sort_keys=True), e) for e in xs], key=lambda e: e[0]
    )
    if not as_json:
        return []
    prev = as_json[0][0]
    filtered = [as_json[0][1]]
    for e in as_json[1:]:
        if e[0] == prev:
            continue
        prev = e[0]
        filtered.append(e[1])
    return filtered


def sort_recipe_lists(recipe):
    if isinstance(recipe, list):
        return nub_sort([sort_recipe_lists(e) for e in recipe])
    if isinstance(recipe, dict):
        return {k: sort_recipe_lists(v) for k, v in recipe.items()}
    return recipe


def combine(x, y):
    """Combine collections

    Dictionaries have their values combined. Lists are concatenated, but any duplicates
    are removed, and the entries are sorted lexicographically.
    """

    if isinstance(x, list) and isinstance(y, list):
        return nub_sort(x + y)
    if isinstance(x, dict) and isinstance(y, dict):
        combined = {}
        for k in set(x.keys()) & set(y.keys()):
            v = combine(x[k], y[k])
            combined[k] = v
        return x | y | combined
    print(f"Error: cannot combine {x!r} and {y!r}!", file=sys.stderr)
    sys.exit(1)


###############################################################################
# RECIPE SPECIFICATION                                                        #
#                                                                             #
# This is probably what you want to edit                                      #
###############################################################################


base_nix_ghcs = [
    "9141",
    #    "9124",
    #    "9103",
    #    "967",
]

nightly_nix_ghcs = ["984"]

all_nix_ghcs = base_nix_ghcs + nightly_nix_ghcs

upper_bounds = {
    "ghc": "9141",
    "variant": "UpperBounds",
}

other_packages = [
    "clash-benchmark",
    #    "clash-lib-hedgehog",
    #    "clash-prelude-hedgehog",
    #    "clash-profiling",
    #    "clash-profiling-prepare",
    #    "clash-term",
]

recipes = {
    # These will always run
    "base": {
        "cabal": {
            "matrix": {
                # "ghc": ["9.14.1", "9.12.4", "9.10.3", "9.6.7"],
                "ghc": ["9.14.1"],
            },
        },
        "packages_common": {
            "matrix": {
                "ghc": all_nix_ghcs,
                "variant": [""],
                "include": [
                    upper_bounds,
                ],
            },
        },
        "packages_other": {
            "matrix": {
                "package": other_packages,
                "ghc": all_nix_ghcs,
                "variant": [""],
                "include": [
                    upper_bounds | {"package": package} for package in other_packages
                ],
            },
        },
        "developer_shells": {
            "matrix": {
                "ghc": all_nix_ghcs,
            },
        },
        "packages_testsuite": {
            "matrix": {
                "ghc": base_nix_ghcs,
                "variant": [""],
                "include": [
                    upper_bounds,
                ],
            },
        },
        "running_testsuite": {
            "matrix": {
                "ghc": base_nix_ghcs,
                "variant": [""],
                "include": [
                    upper_bounds,
                ],
            },
        },
    },
    # These will run in nightlies but not in PR's
    "nightly": {
        "cabal": {
            "matrix": {
                "ghc": ["9.8.4"],
            },
        },
        "packages_testsuite": {
            "matrix": {
                "ghc": nightly_nix_ghcs,
                "include": [
                    upper_bounds,
                ],
            },
        },
        "running_testsuite": {
            "matrix": {
                "ghc": nightly_nix_ghcs,
            },
        },
    },
}
recipes = sort_recipe_lists(recipes)

flavors = {
    "pr": ["base"],
    "nightly": ["base", "nightly"],
}


###############################################################################
# MAIN SCRIPT                                                                 #
###############################################################################


def build_recipe(flavor):
    try:
        input_recipes = flavors[flavor]
    except KeyError:
        print(f"Invalid flavor {flavor!r}!", file=sys.stderr)
        sys.exit(1)
    recipe = {}
    for input_recipe in input_recipes:
        recipe = combine(recipe, recipes[input_recipe])
    return recipe


def output_recipe(flavor, out):
    recipe = build_recipe(flavor)
    json.dump(recipe, sys.stdout, indent=4)
    out.write("recipe=")
    json.dump(recipe, out)
    out.write("\n")


def main():
    out = None
    try:
        out = open(os.environ["GITHUB_OUTPUT"], "a")
    except KeyError:
        print("$GITHUB_OUTPUT has not been set\n", file=sys.stderr)
    except OSError as e:
        print(f"Failed to open $GITHUB_OUTPUT: {e}\n", file=sys.stderr)
    if out is None or len(sys.argv) != 2:
        print(
            "Invocation: GITHUB_OUTPUT=<file> .ci/ci-recipe.py <flavor>\n",
            file=sys.stderr,
        )
        print(f"Flavors: {list(flavors.keys())}\n", file=sys.stderr)
        print("If an output file is undesired, just do", file=sys.stderr)
        print("GITHUB_OUTPUT=/dev/null .ci/ci-recipe.py <flavor>", file=sys.stderr)
        sys.exit(1)
    output_recipe(sys.argv[1], out)
    out.close()


if __name__ == "__main__":
    main()
