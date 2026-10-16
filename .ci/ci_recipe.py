#!/usr/bin/env python3
"""
Produce CI recipes for things where GitHub isn't quite flexible enough or where you keep
repeating the same data.

For things that are easily expressed in the GitHub workflow YAML syntax, that is usually
a better fit even with this ci_recipe mechanism in place. But we want to be able to vary
job configuration matrices based on parameters, and we don't want to keep typing GHC
version numbers for every matrix, duplicating the same datum in a lot of places. For
those cases, as well as other things that are hard to express in the GitHub workflow
YAML, we can define in this script recipes that specify data to pass to job
configurations. The script is invoked with a parameter describing the flavor of CI we
want to run, and it combines recipes to create the desired flavor. If needed, more
ad-hoc processing could be added for certain flavors.

All the list parts of the JSON recipe are sorted lexicographically and duplicates are
removed if they happen to occur; basically they are treated like unordered sets. This
matches how lists in workflow YAML are usually used, where duplicates don't make sense.
The sorting makes it easy to compare two jobs in the JSON output.
"""

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
    "9124",
    "9103",
    "967",
]

nightly_nix_ghcs = ["984"]

all_nix_ghcs = base_nix_ghcs + nightly_nix_ghcs

# If something isn't needed, just comment it out so it can be easily reinstated with
# different parameters later.
nix_also = [
    {
        # "UpperBounds" variants are built against the newest versions of
        # some of our dependencies, see 'nix/overlay-upper-bounds.nix'.
        "ghc": "9141",
        "variant": "UpperBounds",
    },
]

other_packages = [
    "clash-benchmark",
    "clash-lib-hedgehog",
    "clash-prelude-hedgehog",
    "clash-profiling",
    "clash-profiling-prepare",
    "clash-term",
]

hdls = ["VHDL", "Verilog", "SystemVerilog"]
# XXX: With VHDL, Vivado randomly fails with the following error message:
#
#          FATAL_ERROR: Vivado Simulator kernel has discovered an exceptional
#          condition from which it cannot recover. Process will terminate. For
#          technical support on this issue, please open a WebCase with this
#          project attached at http://www.xilinx.com/support.
#
#      Until we have a way of retrying these test cases or marking them as
#      skipped, these nightlies have been disabled to prevent a "boy who cried
#      wolf" situtation.
vivado_hdls = ["Verilog", "SystemVerilog"]

recipes0 = {
    # These will always run
    "base": {
        "cabal": {
            "matrix": {
                "ghc": ["9.14.1", "9.12.4", "9.10.3", "9.6.7"],
            },
        },
        "packages_common": {
            "matrix": {
                "ghc": all_nix_ghcs,
                "variant": [""],
                "include": nix_also,
            },
        },
        "packages_other": {
            "matrix": {
                "package": other_packages,
                "ghc": all_nix_ghcs,
                "variant": [""],
                "include": [
                    inc | {"package": package}
                    for package in other_packages
                    for inc in nix_also
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
                "include": nix_also,
            },
        },
        "running_testsuite": {
            "matrix": {
                "ghc": base_nix_ghcs,
                "hdl": hdls,
                "variant": [""],
                "include": [inc | {"hdl": hdl} for hdl in hdls for inc in nix_also],
            },
        },
        "running_nightly_testsuite": {
            "matrix": {
                "ghc": [],
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
                "include": nix_also,
            },
        },
        "running_testsuite": {
            "matrix": {
                "ghc": nightly_nix_ghcs,
            },
        },
        "running_nightly_testsuite": {
            "matrix": {
                "ghc": all_nix_ghcs,
                "hdl": vivado_hdls,
                "variant": [""],
                "include": [
                    inc | {"hdl": hdl} for hdl in vivado_hdls for inc in nix_also
                ],
            },
        },
    },
}
recipes = sort_recipe_lists(recipes0)

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
