# docs/

These pages build here, and the Nominal docs hub (nominal-io/pub-docs) will publish them. The
repo's CLAUDE.md brings in the hub's writing rules, and those apply here in full. This file adds
what is specific to the pages.

- Readers are systems engineers, or engineers implementing checks to a systems engineer's
  requirements, working from their Jama Connect projects. The Quickstart assumes no Python
  experience; the guides for changing the code assume Python.
- Three tabs: Quickstart (the root page and `quickstart/`), Guides (`guides/`) and Reference
  (`reference/`). The agent path is the main one; guides end with the next steps in Nominal.
- State only what the code shows or what has been run. Jama's own behavior, such as its paging
  limits, error codes and UI labels, is cited from Jama's documentation or tested before a page
  relies on it.
- Commands run the tool from the checkout: `python nominal-checks-from-jama.py <command>`.
- Link to other projects on the hub as `[text](site:/{project}/{page}/)`, never with an absolute
  URL, so the hub's offline copy works.
- Write "Jama Connect" for the product, and end each page with the trademark line:
  "Jama Connect® is a registered trademark of Jama Software, Inc."
- Describe the tool as reading from Jama Connect, never as a joint or endorsed product. The repo's
  CLAUDE.md lists the words to avoid. Use no Jama logo.
- Examples use placeholders for credentials and invented project names and keys.
