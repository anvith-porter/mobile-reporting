# GitHub Actions Automation Setup

This document explains how to set up and maintain the automated App Vitals collection via GitHub Actions.

## Overview

The automation collects app vitals data (crash-free rates, top crashes, ANRs, etc.) for all configured apps weekly using GitHub Actions. Browser session state is stored in the repository to maintain authentication.

## Initial Setup

### 1. Save Browser Session

First, you need to create an authenticated browser session:

```bash
python scripts/save_session.py
```

This will:
- Open a browser window
- Navigate to Firebase Console
- Wait for you to complete SSO login manually
- Save the browser state to `browser_state/storage_state.json`

### 2. Commit Session to Repository

After saving the session:

```bash
git add browser_state/storage_state.json
git commit -m "Add initial browser session"
git push
```

**Important**: The `browser_state/storage_state.json` file contains your authentication cookies. Since this is a private repository, it's safe to commit, but make sure the repo remains private.

## Workflow Schedule

The workflow runs:
- **Automatically**: Every Monday at 9 AM UTC (weekly)
- **Manually**: Via GitHub Actions UI → "Run workflow" button

## When SSO Session Expires

If the workflow fails with an SSO authentication error:

1. **Run the save script locally**:
   ```bash
   python scripts/save_session.py
   ```

2. **Complete SSO login** in the opened browser

3. **Commit and push** the updated session:
   ```bash
   git add browser_state/storage_state.json
   git commit -m "Update browser session"
   git push
   ```

4. **Trigger workflow rerun** in GitHub Actions UI (or wait for next scheduled run)

## Troubleshooting

### Workflow fails: "Browser state file not found"

**Solution**: Run `python scripts/save_session.py` and commit the generated file.

### Workflow fails: "SSO Authentication Required"

**Solution**: Your session has expired. Follow the steps in "When SSO Session Expires" above.

### Workflow fails: "Error loading storage state"

**Solution**: The storage state file might be corrupted. Delete it and run `save_session.py` again.

### Google Play Vitals not collected

**Solution**: Ensure `googleplaykey.json` service account file exists in the repository root (or set `GOOGLE_PLAY_SERVICE_ACCOUNT` environment variable).

## Manual Testing

To test the script locally:

```bash
python automate_vitals.py
```

This will:
- Use the saved browser session from `browser_state/storage_state.json`
- Collect data for all apps
- Save output to `crash_data_YYYYMMDD_HHMMSS.json`

## Output Files

The workflow generates JSON files with the following structure:

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "date_range_days": 7,
  "apps": {
    "customer": {
      "android": {...},
      "ios": {...},
      "google_play_vitals": {...}
    },
    "partner": {...},
    ...
  }
}
```

Output files are saved as GitHub Actions artifacts and can be downloaded from the workflow run page.

## Configuration

### Environment Variables

- `BROWSER_STORAGE_STATE`: Path to browser state file (default: `browser_state/storage_state.json`)
- `GOOGLE_PLAY_SERVICE_ACCOUNT`: Path to Google Play service account JSON (default: `googleplaykey.json`)

### App Configuration

Edit `APPS_CONFIG` in `automate_vitals.py` to add/remove/modify apps.

## Security Notes

- Browser session state contains authentication cookies - keep repository private
- Google Play service account key should be committed to private repo or stored as GitHub Secret
- Never commit sensitive credentials to public repositories




