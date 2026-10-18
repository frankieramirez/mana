# Invoice totals

`invoice/totals.py` computes invoice totals in integer cents. A percentage discount is rounded half up to the nearest cent before it is subtracted.

Product verification:

    python3 checks/check_totals.py

Review page image: save the check output to a file, then

    python3 tools/render_check.py <saved-output> <output.svg>
