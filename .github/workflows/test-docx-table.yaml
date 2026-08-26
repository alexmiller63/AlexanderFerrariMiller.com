name: Test DOCX Table

on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install python-docx

      - name: Run minimal DOCX table test
        run: |
          python tools/test-docx-table.py

      - name: Upload test DOCX
        uses: actions/upload-artifact@v4
        with:
          name: test-docx-table
          path: test-docx-table.docx