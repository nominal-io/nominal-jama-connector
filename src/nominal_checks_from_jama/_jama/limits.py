"""Page sizes, ceilings and timings the Jama reader uses, each with the reason for its value."""

PAGE_SIZE = 50
"""Rows per page on Jama's offset-paged endpoints. Jama's default is 20 and its ceiling is 50."""

MAX_PAGES_PER_LIST = 2_000
"""Pages one listing reads before it stops and reports ``truncated``.

A guard against a server that keeps answering with pages; a page that doesn't move the cursor is
caught separately. At the page size above this is 100,000 items.
"""

REQUEST_TIMEOUT_SECONDS = 30.0
"""Seconds one request may take before it fails as a timeout."""

TOKEN_REFRESH_MARGIN_SECONDS = 60.0
"""Seconds before an OAuth token's stated expiry at which the client fetches a new one, so a long
listing doesn't start on a token about to expire."""
