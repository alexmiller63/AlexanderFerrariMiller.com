# Development

## GitHub Actions Diagnostic Artifacts

GitHub Actions diagnostic output should be preserved as workflow artifacts whenever practical.

Diagnostic files should use predictable, stable names. The standard diagnostic filename is:

`debug.txt`

The workflow should upload `debug.txt` as an artifact so that it remains available after the workflow run completes.

The preferred diagnostic workflow is:

1. Run the GitHub Actions workflow.

2. Preserve diagnostic output in `debug.txt`.

3. Upload `debug.txt` as a workflow artifact with a predictable artifact name.

4. Heather retrieves and examines the workflow artifact directly through the connected GitHub tools.

Manual downloading, ZIP extraction, copying diagnostic output, and screenshots should not be required when the diagnostic information can be retrieved directly from GitHub.

This convention is intended to make diagnostic results machine-accessible and reproducible while minimizing manual transfer of information between GitHub and ChatGPT.

