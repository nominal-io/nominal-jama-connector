"""Sphinx configuration for the nominal-checks-from-jama docs.

Built with `just build-docs`. .github/workflows/deploy-docs.yml deploys the build to this repo's
GitHub Pages, and the Nominal docs hub (nominal-io/pub-docs) pulls it from there and serves it at
/tools/jama/.
"""

import sys
from pathlib import Path

from nominal_sphinx_theme import theme_options

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "_ext"))

project = "Nominal checks from Jama"  # the name in the header, after the Nominal Docs logo
copyright = "Nominal, Inc."

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "nominal_sphinx_theme",
    "site_links",  # [text](site:/quickstart/...) links to other projects on the docs hub
]

myst_enable_extensions = ["colon_fence", "deflist", "attrs_inline", "attrs_block", "fieldlist"]
myst_heading_anchors = 6

# the API reference comes from the Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# CLAUDE.md holds the rules for writing these pages; it isn't one
exclude_patterns = ["_build", "CLAUDE.md"]

html_theme = "shibuya"
html_title = "Nominal checks from Jama"  # browser tabs and search results
html_copy_source = False
html_context = {
    "source_type": "github",
    "source_user": "nominal-io",
    "source_repo": "nominal-jama-connector",
    "source_version": "main",
    "source_docs_path": "/docs/",
}
html_theme_options = theme_options(
    github_url="https://github.com/nominal-io/nominal-jama-connector",
    nav_links=[
        {"title": "Quickstart", "url": "index"},
        {"title": "Guides", "url": "guides/index"},
        {"title": "Reference", "url": "reference/index"},
    ],
)
