#!/usr/bin/env python3
"""
Export app vitals JSON data to BigQuery
Transforms the JSON structure to one row per app per collection
"""

import json
import sys
from typing import List, Dict, Any

try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("⚠️  BigQuery client not available. Install with: pip install google-cloud-bigquery")


def transform_google_play_vitals(vitals_data: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Transform Google Play Vitals to key-value metrics array"""
    if not vitals_data:
        return None
    
    # Convert the flat structure to key-value pairs
    metrics = []
    metric_fields = [
        'anr_rate',
        'user_perceived_anr_rate',
        'crash_rate',
        'user_perceived_crash_rate',
        'slow_start_rate',
        'excessive_wakeup_rate',
        'stuck_wakelock_rate',
        'user_perceived_lmk_rate'
    ]
    
    for field in metric_fields:
        if field in vitals_data and vitals_data[field] is not None:
            metrics.append({
                'metric_name': field,
                'metric_value': float(vitals_data[field])
            })
    
    return {
        'date': vitals_data.get('date'),
        'metrics': metrics
    }


def normalize_android_data(android_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Android data to match BigQuery schema exactly"""
    if not android_data:
        return {}
    
    normalized = {
        'crash_free_rates': android_data.get('crash_free_rates', {}),
        'total_installs': android_data.get('total_installs', {}),
        'p90_launch_time_seconds': android_data.get('p90_launch_time_seconds'),
        'dominant_release': android_data.get('dominant_release'),
        'top_crashes': android_data.get('top_crashes', []),
        'top_non_fatals': android_data.get('top_non_fatals', []),
        'all_anrs': android_data.get('all_anrs', []),
        'up_anrs': android_data.get('up_anrs', [])
    }
    
    return normalized


def normalize_ios_data(ios_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize iOS data to match BigQuery schema exactly"""
    if not ios_data:
        return {}
    
    normalized = {
        'crash_free_rates': ios_data.get('crash_free_rates', {}),
        'total_installs': ios_data.get('total_installs', {}),
        'dominant_release': ios_data.get('dominant_release'),
        'top_crashes': ios_data.get('top_crashes', []),
        'top_non_fatals': ios_data.get('top_non_fatals', [])
    }
    
    return normalized


def transform_json_to_bigquery_rows(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Transform JSON structure from:
    {timestamp, date_range_days, apps: {app_key: {...}}}
    
    To BigQuery rows (one per app):
    [{collection_timestamp, date_range_days, app_key, app_name, android, ios, google_play_vitals}, ...]
    """
    rows = []
    collection_timestamp = json_data.get('timestamp')
    date_range_days = json_data.get('date_range_days', 7)
    
    apps = json_data.get('apps', {})
    
    # App name mapping (since app_name is not in the output JSON)
    app_name_map = {
        'partner': 'Partner App',
        'customer': 'Customer App',
        'vendor': 'Vendor App',
        'owner': 'Owner App'
    }
    
    for app_key, app_data in apps.items():
        # Skip apps with errors
        if isinstance(app_data, dict) and 'error' in app_data:
            print(f"⚠️  Skipping {app_key} due to error: {app_data['error']}")
            continue
        
        # Get app name from mapping or use capitalized app_key
        app_name = app_data.get('app_name') or app_name_map.get(app_key) or app_key.capitalize()
        
        # Normalize Android and iOS data to ensure schema compliance
        android_data = normalize_android_data(app_data.get('android', {}))
        ios_data = normalize_ios_data(app_data.get('ios', {}))
        
        # Transform Google Play Vitals
        google_play_vitals = transform_google_play_vitals(
            app_data.get('google_play_vitals')
        )
        
        row = {
            'collection_timestamp': collection_timestamp,
            'date_range_days': date_range_days,
            'app_key': app_key,
            'app_name': app_name,
            'android': android_data,
            'ios': ios_data,
            'google_play_vitals': google_play_vitals
        }
        
        rows.append(row)
    
    return rows


def export_to_bigquery(
    json_file_path: str,
    project_id: str,
    dataset_id: str,
    table_id: str,
    credentials_path: str | None = None
):
    """Export JSON file to BigQuery"""
    if not BIGQUERY_AVAILABLE:
        print("❌ BigQuery client not available")
        sys.exit(1)
    
    # Load JSON data
    print(f"📄 Loading JSON from {json_file_path}...")
    with open(json_file_path, 'r') as f:
        json_data = json.load(f)
    
    # Transform to BigQuery rows
    print("🔄 Transforming data to BigQuery format...")
    rows = transform_json_to_bigquery_rows(json_data)
    
    if not rows:
        print("⚠️  No data to export")
        return
    
    print(f"✅ Prepared {len(rows)} rows for export")
    
    # Initialize BigQuery client
    if credentials_path:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )
        client = bigquery.Client(project=project_id, credentials=credentials)
    else:
        client = bigquery.Client(project=project_id)
    
    # Get table reference
    table_ref = client.dataset(dataset_id).table(table_id)
    table = client.get_table(table_ref)
    
    # Insert rows
    print(f"📤 Uploading to BigQuery: {project_id}.{dataset_id}.{table_id}...")
    errors = client.insert_rows_json(table, rows)
    
    if errors:
        print(f"❌ Errors occurred while inserting rows:")
        for error in errors:
            print(f"   {error}")
        sys.exit(1)
    else:
        print(f"✅ Successfully exported {len(rows)} rows to BigQuery!")
        print(f"   Collection timestamp: {json_data.get('timestamp')}")
        print(f"   Apps exported: {', '.join([r['app_key'] for r in rows])}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Export app vitals JSON to BigQuery'
    )
    parser.add_argument('json_file', help='Path to JSON file to export')
    parser.add_argument('--project', required=True, help='GCP Project ID')
    parser.add_argument('--dataset', required=True, help='BigQuery Dataset ID')
    parser.add_argument('--table', required=True, help='BigQuery Table ID')
    parser.add_argument('--credentials', help='Path to service account JSON file')
    
    args = parser.parse_args()
    
    export_to_bigquery(
        args.json_file,
        args.project,
        args.dataset,
        args.table,
        args.credentials
    )

