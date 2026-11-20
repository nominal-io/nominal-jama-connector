from nominal_checks_from_jama._jama import html_to_text


def test_lists_become_lines() -> None:
    assert html_to_text("<p>Hold 85&deg;C for:</p><ul><li>10 min</li><li>20 min</li></ul>") == (
        "Hold 85°C for:\n10 min\n20 min"
    )


def test_table_cells_stay_apart() -> None:
    assert html_to_text("<table><tr><td>10</td><td>20</td></tr></table>") == "10\n20"


def test_inline_tags_are_removed_and_entities_decoded() -> None:
    assert html_to_text("Max <b>5&nbsp;V</b> &plusmn; 0.1 &lt;limit&gt;") == "Max 5 V ± 0.1 <limit>"


def test_script_and_style_contents_are_dropped() -> None:
    assert html_to_text("<p>Text</p><script>alert(1)</script><style>p{}</style>") == "Text"


def test_br_and_blank_lines() -> None:
    assert html_to_text("one<br>two<br/><br/>three\r\n") == "one\ntwo\nthree"
