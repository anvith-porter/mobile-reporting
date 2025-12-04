#!/usr/bin/env python3

from browser_use import Browser
import asyncio
import os
import re
import json
import sys
from datetime import datetime, timedelta


# Google Play Vitals imports (optional)
try:
    import google.auth
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    import requests
    from collections import defaultdict
    import time
    GOOGLE_PLAY_AVAILABLE = True
except ImportError:
    GOOGLE_PLAY_AVAILABLE = False

# ============================================================================
# APP CONFIGURATION
# ============================================================================
# Configure all apps here with their Firebase and Google Play details
APPS_CONFIG = {
    "partner": {
        "name": "Partner App",
        "firebase_project": "driverapp-f56a2",
        "android": {
            "app_id": "android:com.theporter.android.driverapp",
            "package_name": "com.theporter.android.driverapp",
            "play_console": {
                "developer_id": "4707055851875633325",
                "app_id": "4972278085731896191"
            }
        },
        "has_ios": False,
        "has_p90_launch_time": True
    },
    "customer": {
        "name": "Customer App",
        "firebase_project": "portercustomerapp",
        "android": {
            "app_id": "android:com.theporter.android.customerapp",
            "package_name": "com.theporter.android.customerapp",
            "play_console": {
                "developer_id": "4707055851875633325",
                "app_id": "4975635893417729870"
            }
        },
        "ios": {
            "app_id": "ios:in.theporter.customerapp",
            "bundle_id": "in.theporter.customerapp"
        },
        "has_ios": True,
        "has_p90_launch_time": True
    },
    "vendor": {
        "name": "Vendor App",
        "firebase_project": "pnmvendorapp",
        "android": {
            "app_id": "android:in.porter.pnm.vendor.app",
            "package_name": "in.porter.pnm.vendor.app",
            "play_console": {
                "developer_id": "4707055851875633325",
                "app_id": "4975591217808574162"
            }
        },
        "has_ios": False,
        "has_p90_launch_time": True
    },
    "owner": {
        "name": "Owner App",
        "firebase_project": "owner-app-29e1d",
        "android": {
            "app_id": "android:com.porter.android.partnerownerapp",
            "package_name": "com.porter.android.partnerownerapp",
            "play_console": {
                "developer_id": "4707055851875633325",
                "app_id": "4974844181868761677"
            }
        },
        "ios": {
            "app_id": "ios:com.porter.partnerownerapp",
            "bundle_id": "com.porter.partnerownerapp"
        },
        "has_ios": True,
        "has_p90_launch_time": False
    }
}

# Google Play Vitals configuration
# Service account file path can be set via GOOGLE_PLAY_SERVICE_ACCOUNT environment variable
# Defaults to 'googleplaykey.json' if not set
SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_PLAY_SERVICE_ACCOUNT', 'googleplaykey.json')
SCOPES = [
    'https://www.googleapis.com/auth/playdeveloperreporting',
    'https://www.googleapis.com/auth/androidpublisher'
]

# Global date range configuration (defaults to 7 days)
DATE_RANGE_DAYS = 7

def _choose_report_days() -> int:
    # Prefer CLI arg: python script.py 7  OR  python script.py 30
    for arg in sys.argv[1:]:
        if arg.strip() in {"7", "30"}:
            return int(arg.strip())
        if arg.lower().startswith("--days="):
            val = arg.split("=", 1)[1].strip()
            if val in {"7", "30"}:
                return int(val)
    # Default to 7 days (no prompt)
    return 7

def _build_urls(report_days: int, app_key: str, app_config: dict):
    """
    Build URLs for a specific app based on configuration
    
    Args:
        report_days: Number of days for the report (7 or 30)
        app_key: Key of the app in APPS_CONFIG (e.g., "customer", "partner")
        app_config: App configuration dictionary from APPS_CONFIG
    """
    # Firebase time window
    firebase_time = "last-seven-days" if report_days == 7 else "last-thirty-days"
    # GA date option (GA4 often supports last28Days; use that for 30-day runs)
    ga_date_option = "last7Days" if report_days == 7 else "last28Days"
    # Play Console ANR days
    pc_days = 7 if report_days == 7 else 30
    # Android Performance trends
    perf_time = "7d" if report_days == 7 else "30d"

    firebase_project = app_config["firebase_project"]
    android_app = app_config["android"]["app_id"]
    
    # Firebase Crashlytics base
    base = f"https://console.firebase.google.com/u/0/project/{firebase_project}/crashlytics/app"

    firebase_url = f"{base}/{android_app}/issues?state=open&time={firebase_time}&tag=all&sort=userCount&types=crash%2Cerror"
    top_crashes_url = f"{base}/{android_app}/issues?state=open&time={firebase_time}&tag=all&sort=userCount&types=crash"
    top_non_fatals_url = f"{base}/{android_app}/issues?state=open&time={firebase_time}&tag=all&sort=userCount&types=error"
    top_anrs_url = f"{base}/{android_app}/issues?state=open&time={firebase_time}&tag=all&sort=userCount&types=ANR"

    # GA4 Dominant Release URLs (use encoded last7Days/last28Days)
    ios_dom = (
        "https://console.firebase.google.com/u/0/project/portercustomerapp/analytics/app/ios:in.theporter.customerapp/overview/"
        "reports~2Fexplorer%3Fparams%3D_r.explorerCard..selmet%253D%255B%2522activeUsers%2522%255D%2526_r.explorerCard..seldim%253D%255B%2522appVersion%2522%255D"
        "%2526_r..dataFilters%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%2522%253A%2522operatingSystem%2522%252C%2522evaluationType%2522%253A4%252C%2522expressionList%2522%253A%255B%2522iOS%2522%255D%252C%2522complement%2522%253Afalse%252C%2522isCaseSensitive%2522%253Atrue%252C%2522expression%2522%253A%2522%2522%257D%255D"
        f"%2526_u.dateOption%253D{ga_date_option}%2526_u.comparisonOption%253Ddisabled&r%3Duser-technology-detail&fpn%3D324301932190"
    )
    android_dom = (
        "https://console.firebase.google.com/u/0/project/portercustomerapp/analytics/app/ios:in.theporter.customerapp/overview/"
        "reports~2Fexplorer%3Fparams%3D_r.explorerCard..selmet%253D%255B%2522activeUsers%2522%255D%2526_r.explorerCard..seldim%253D%255B%2522appVersion%2522%255D"
        "%2526_r..dataFilters%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%2522%253A%2522operatingSystem%2522%252C%2522evaluationType%2522%253A3%252C%2522expressionList%2522%253A%255B%2522iOS%2522%255D%252C%2522complement%2522%253Atrue%252C%2522isCaseSensitive%2522%253Atrue%252C%2522expression%2522%253A%2522%2522%257D%255D"
        f"%2526_r.copa-filter-builder..filter-to-edit%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%2522%253A%2522operatingSystem%2522%252C%2522evaluationType%2522%253A4%252C%2522expressionList%2522%253A%255B%2522iOS%2522%255D%252C%2522complement%2522%253Afalse%252C%2522isCaseSensitive%2522%253Atrue%252C%2522expression%2522%253A%2522%2522%257D%255D%2526_u.comparisonOption%253Ddisabled%2526_u.dateOption%253D{ga_date_option}"
        "&r%3Duser-technology-detail&fpn%3D324301932190"
    )

    play_console = app_config["android"]["play_console"]
    play_console_anr_url = (
        f"https://play.google.com/console/u/0/developers/{play_console['developer_id']}/app/{play_console['app_id']}/vitals/crashes"
        f"?days={pc_days}&isUserPerceived=true&errorType=ANR"
    )

    urls = {
        "firebase_url": firebase_url,
        "top_crashes_url": top_crashes_url,
        "top_non_fatals_url": top_non_fatals_url,
        "top_anrs_url": top_anrs_url,
        "play_console_anr_url": play_console_anr_url,
    }
    
    # Add P90 launch URL only if app has P90 launch time trace
    if app_config.get("has_p90_launch_time", True):
        android_p90_launch_url = (
            f"https://console.firebase.google.com/u/0/project/{firebase_project}/performance/app/"
            f"{android_app}/trends?time={perf_time}"
        )
        urls["android_p90_launch_url"] = android_p90_launch_url
    
    # iOS URLs (only if app has iOS)
    if app_config.get("has_ios") and "ios" in app_config:
        ios_app = app_config["ios"]["app_id"]
        ios_crashes_url = f"{base}/{ios_app}/issues?state=open&time={firebase_time}&types=crash&tag=all&sort=userCount"
        ios_non_fatals_url = f"{base}/{ios_app}/issues?state=open&time={firebase_time}&types=error&tag=all&sort=eventCount"
        
        # GA4 Dominant Release URLs (use encoded last7Days/last28Days)
        # Note: The fpn parameter (324301932190) appears to be project number - may need to be configurable
        ios_dom = (
            f"https://console.firebase.google.com/u/0/project/{firebase_project}/analytics/app/{ios_app}/overview/"
            "reports~2Fexplorer%3Fparams%3D_r.explorerCard..selmet%253D%255B%2522activeUsers%2522%255D%2526_r.explorerCard..seldim%253D%255B%2522appVersion%2522%255D"
            "%2526_r..dataFilters%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%253A%2522operatingSystem%2522%252C%2522evaluationType%2522%253A4%252C%2522expressionList%253A%255B%2522iOS%2522%255D%252C%2522complement%2522%253Afalse%252C%2522isCaseSensitive%253Atrue%252C%2522expression%253A%2522%2522%257D%255D"
            f"%2526_u.dateOption%253D{ga_date_option}%2526_u.comparisonOption%253Ddisabled&r%3Duser-technology-detail&fpn%3D324301932190"
        )
        android_dom = (
            f"https://console.firebase.google.com/u/0/project/{firebase_project}/analytics/app/{ios_app}/overview/"
            "reports~2Fexplorer%3Fparams%3D_r.explorerCard..selmet%253D%255B%2522activeUsers%2522%255D%2526_r.explorerCard..seldim%253D%255B%2522appVersion%2522%255D"
            "%2526_r..dataFilters%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%253A%2522operatingSystem%2522%252C%2522evaluationType%253A3%252C%2522expressionList%253A%255B%2522iOS%2522%255D%252C%2522complement%253Atrue%252C%2522isCaseSensitive%253Atrue%252C%2522expression%253A%2522%2522%257D%255D"
            f"%2526_r.copa-filter-builder..filter-to-edit%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%253A%2522operatingSystem%2522%252C%2522evaluationType%253A4%252C%2522expressionList%253A%255B%2522iOS%2522%255D%252C%2522complement%253Afalse%252C%2522isCaseSensitive%253Atrue%252C%2522expression%253A%2522%2522%257D%255D%2526_u.comparisonOption%253Ddisabled%2526_u.dateOption%253D{ga_date_option}"
            "&r%3Duser-technology-detail&fpn%3D324301932190"
        )
        
        urls["ios_crashes_url"] = ios_crashes_url
        urls["ios_non_fatals_url"] = ios_non_fatals_url
        urls["ios_dominant_release_url"] = ios_dom
        urls["android_dominant_release_url"] = android_dom
    else:
        # Android dominant release URL for apps without iOS
        # Use Android app ID for analytics
        android_dom = (
            f"https://console.firebase.google.com/u/0/project/{firebase_project}/analytics/app/{android_app}/overview/"
            "reports~2Fexplorer%3Fparams%3D_r.explorerCard..selmet%253D%255B%2522activeUsers%2522%255D%2526_r.explorerCard..seldim%253D%255B%2522appVersion%2522%255D"
            "%2526_r..dataFilters%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%253A%2522operatingSystem%2522%252C%2522evaluationType%253A3%252C%2522expressionList%253A%255B%2522iOS%2522%255D%252C%2522complement%253Atrue%252C%2522isCaseSensitive%253Atrue%252C%2522expression%253A%2522%2522%257D%255D"
            f"%2526_r.copa-filter-builder..filter-to-edit%253D%255B%257B%2522type%2522%253A1%252C%2522fieldName%253A%2522operatingSystem%2522%252C%2522evaluationType%253A4%252C%2522expressionList%253A%255B%2522iOS%2522%255D%252C%2522complement%253Afalse%252C%2522isCaseSensitive%253Atrue%252C%2522expression%253A%2522%2522%257D%255D%2526_u.comparisonOption%253Ddisabled%2526_u.dateOption%253D{ga_date_option}"
            "&r%3Duser-technology-detail&fpn%3D324301932190"
        )
        urls["android_dominant_release_url"] = android_dom
    
    return urls

def get_google_play_vitals(report_days: int, package_name: str):
    """Fetch current Google Play Vitals data for a specific package"""
    if not GOOGLE_PLAY_AVAILABLE:
        return None
        
    try:
        # Check if service account file exists
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"⚠️  Google Play service account file not found: {SERVICE_ACCOUNT_FILE}")
            print(f"   Set GOOGLE_PLAY_SERVICE_ACCOUNT environment variable to specify the path")
            return None
        
        def get_access_token():
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            auth_req = Request()
            credentials.refresh(auth_req)
            return credentials.token

        def fetch_metrics_for_date(target_date, metrics_list):
            """Fetch specified metrics for a specific date"""
            def metric_to_endpoint(metric_name: str) -> str:
                if metric_name.startswith('anrRate') or metric_name.startswith('userPerceivedAnrRate'):
                    return 'anrRateMetricSet'
                if metric_name.startswith('crashRate') or metric_name.startswith('userPerceivedCrashRate'):
                    return 'crashRateMetricSet'
                if metric_name.startswith('slowStartRate'):
                    return 'slowStartRateMetricSet'
                if metric_name.startswith('userPerceivedLmkRate'):
                    return 'lmkRateMetricSet'
                if metric_name.startswith('excessiveWakeupRate'):
                    return 'excessiveWakeupRateMetricSet'
                if metric_name.startswith('stuckBgWakelockRate'):
                    return 'stuckBackgroundWakelockRateMetricSet'
                return ''

            endpoint_metrics = defaultdict(list)
            for metric in metrics_list:
                endpoint = metric_to_endpoint(metric)
                if endpoint:
                    endpoint_metrics[endpoint].append(metric)

            all_results = {}
            access_token = get_access_token()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }

            end_date = target_date + timedelta(days=1)

            for endpoint, endpoint_metric_list in endpoint_metrics.items():
                url = f"https://playdeveloperreporting.googleapis.com/v1beta1/apps/{package_name}/{endpoint}:query"

                body = {
                    "metrics": endpoint_metric_list,
                    "timelineSpec": {
                        "aggregationPeriod": "DAILY",
                        "startTime": {
                            "year": target_date.year,
                            "month": target_date.month,
                            "day": target_date.day
                        },
                        "endTime": {
                            "year": end_date.year,
                            "month": end_date.month,
                            "day": end_date.day
                        }
                    }
                }

                if endpoint == 'slowStartRateMetricSet':
                    body["dimensions"] = ["startType"]

                try:
                    response = requests.post(url, headers=headers, json=body)
                    if response.status_code == 200:
                        all_results[endpoint] = response.json()
                    time.sleep(0.1)
                except:
                    continue

            # Combine results
            combined_result = {"rows": []}
            all_metrics = []

            for endpoint, data in all_results.items():
                if data.get('rows'):
                    for row in data['rows']:
                        all_metrics.extend(row.get('metrics', []))

            if all_metrics:
                combined_result["rows"] = [{"metrics": all_metrics}]

            return combined_result

        def parse_metrics_from_response(data):
            """Extract metrics from API response"""
            if 'rows' not in data or not data['rows']:
                return {}

            metrics = {}
            for row in data.get('rows', []):
                for metric in row.get('metrics', []):
                    metric_name = metric['metric']

                    if 'decimalValue' in metric:
                        metric_value = float(metric['decimalValue']['value'])
                        if 'Rate' in metric_name:
                            metric_value *= 100
                        metrics[metric_name] = round(metric_value, 3)
                    elif 'intValue' in metric:
                        metrics[metric_name] = int(metric['intValue'])

            return metrics

        # Define key metrics to track based on selection
        if report_days == 7:
            suffix = "7dUserWeighted"
            lookback = 8
        else:
            suffix = "28dUserWeighted"  # GA metrics commonly expose 28d variant
            lookback = 31

        metrics_list = [
            f'anrRate{suffix}',
            f'userPerceivedAnrRate{suffix}',
            f'crashRate{suffix}',
            f'userPerceivedCrashRate{suffix}',
            f'slowStartRate{suffix}',
            f'excessiveWakeupRate{suffix}',
            f'stuckBgWakelockRate{suffix}',
            f'userPerceivedLmkRate{suffix}'
        ]

        # Find latest available date with data (look back up to selection window)
        base_date = datetime.now().date()
        latest_date = None
        current_data = None
        
        for days_back in range(1, lookback):
            test_date = base_date - timedelta(days=days_back)
            try:
                # Test with a simple metric first
                data = fetch_metrics_for_date(test_date, [f"anrRate{suffix}"])
                if data.get('rows'):
                    latest_date = test_date
                    # Fetch all metrics for this date
                    current_data = fetch_metrics_for_date(latest_date, metrics_list)
                    break
            except:
                continue
        
        if not latest_date or not current_data:
            raise Exception(f"No data available in the last {report_days} days")
        
        # Parse the metrics from the response
        current_metrics = parse_metrics_from_response(current_data)

        # Format for JSON output
        vitals_data = {
            "date": latest_date.isoformat(),
            "anr_rate": current_metrics.get(f'anrRate{suffix}'),
            "user_perceived_anr_rate": current_metrics.get(f'userPerceivedAnrRate{suffix}'),
            "crash_rate": current_metrics.get(f'crashRate{suffix}'),
            "user_perceived_crash_rate": current_metrics.get(f'userPerceivedCrashRate{suffix}'),
            "slow_start_rate": current_metrics.get(f'slowStartRate{suffix}'),
            "excessive_wakeup_rate": current_metrics.get(f'excessiveWakeupRate{suffix}'),
            "stuck_wakelock_rate": current_metrics.get(f'stuckBgWakelockRate{suffix}'),
            "user_perceived_lmk_rate": current_metrics.get(f'userPerceivedLmkRate{suffix}')
        }

        return vitals_data

    except Exception as e:
        print(f"⚠️  Failed to fetch Google Play Vitals data: {e}")
        return None

async def collect_app_data(report_days: int, app_key: str, app_config: dict, page):
    """
    Collect vitals data for a specific app using the provided page
    Returns the collected app data dictionary
    """
    print(f"\n{'='*60}")
    print(f"📱 Collecting data for {app_config['name']} ({app_key})")
    print(f"{'='*60}")
    
    urls = _build_urls(report_days, app_key, app_config)
    firebase_url = urls["firebase_url"]
    top_crashes_url = urls["top_crashes_url"]
    top_non_fatals_url = urls["top_non_fatals_url"]
    top_anrs_url = urls["top_anrs_url"]
    ios_crashes_url = urls.get("ios_crashes_url")
    ios_non_fatals_url = urls.get("ios_non_fatals_url")
    play_console_anr_url = urls["play_console_anr_url"]
    ios_dominant_release_url = urls.get("ios_dominant_release_url")
    android_dominant_release_url = urls.get("android_dominant_release_url")
    android_p90_launch_url = urls.get("android_p90_launch_url")
    
    try:
        # Set up request monitoring
        metrics_requests = []
        metrics_captured = False
        fatal_installs = 0
        non_fatal_installs = 0
        anr_installs = 0
        ios_fatal_installs = 0
        ios_non_fatal_installs = 0
        crashes_captured = False
        non_fatals_captured = False
        anr_metrics_captured = False
        ios_metrics_captured = False
        ios_crashes_captured = False
        ios_non_fatals_captured = False
        ios_crash_free_rate_captured = False
        play_console_anrs_captured = False
        ios_dominant_release_captured = False
        android_dominant_release_captured = False
        android_p90_launch_captured = False
        ios_nonfatal_issues_processed = False
        current_phase = "metrics"  # "metrics", "crashes", "non_fatals", "anrs", "anr_metrics", "ios_metrics", "ios_crashes", "ios_non_fatals", "play_console_anrs", "ios_dominant_release", "android_dominant_release", "android_p90_launch"
        
        # Initialize JSON data structure for this app
        app_data = {
        "app_key": app_key,
        "app_name": app_config["name"],
        "android": {
            "crash_free_rates": {},
            "total_installs": {},
            "top_crashes": [],
            "top_non_fatals": [],
            "all_anrs": [],
            "up_anrs": [],
            "p90_launch_time_seconds": None,
            "dominant_release": None
        },
        "ios": {
            "crash_free_rates": {},
            "total_installs": {},
            "top_crashes": [],
            "top_non_fatals": [],
            "dominant_release": None
        },
        "google_play_vitals": None
        }

        # Debug counters
        request_count = 0
        
        def is_valid_date_range(start_time_str, end_time_str):
            """Check if the date range matches our expected range"""
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                
                # Get today's date in UTC
                today = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
                expected_start = today - timedelta(days=DATE_RANGE_DAYS-1)
                expected_start = expected_start.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Check if end date is today and start date is DATE_RANGE_DAYS ago
                return (end_time.date() == today.date() and 
                        start_time.date() == expected_start.date())
            except:
                return False
        
        async def handle_response(response):
            url = response.url
            nonlocal metrics_captured
            nonlocal fatal_installs, non_fatal_installs
            nonlocal anr_installs, crashes_captured, non_fatals_captured
            nonlocal anr_metrics_captured, current_phase
            nonlocal ios_fatal_installs, ios_non_fatal_installs
            nonlocal ios_metrics_captured, ios_crashes_captured, ios_non_fatals_captured
            nonlocal ios_crash_free_rate_captured
            nonlocal play_console_anrs_captured
            nonlocal ios_dominant_release_captured, android_dominant_release_captured
            nonlocal ios_nonfatal_issues_processed
            nonlocal android_p90_launch_captured
            nonlocal app_data

            # Handle Android P90 Launch Time response
            if (current_phase == "android_p90_launch" and 
                "traces/_as:listTimelines" in url and
                "filter.appVersionValues" not in url):
                try:
                    json_response = await response.json()
                    timelines = json_response.get("timelines", [])
                    
                    if timelines and len(timelines) > 0:
                        projections = timelines[0].get("projections", [])
                        
                        # Get today's date for comparison
                        today = datetime.now().date()
                        yesterday = today - timedelta(days=1)
                        
                        # Find projection for today or yesterday
                        target_projection = None
                        for projection in projections:
                            start_time_str = projection.get("startTime", "")
                            if start_time_str:
                                try:
                                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00')).date()
                                    if start_time == today or start_time == yesterday:
                                        target_projection = projection
                                        break
                                except:
                                    continue
                        
                        if target_projection:
                            quantiles = target_projection.get("projection", {}).get("quantiles", [])
                            if len(quantiles) >= 19:
                                # P90 is at index 18, convert from microseconds to seconds
                                p90_microseconds = float(quantiles[18])  # Convert to float first
                                p90_seconds = round(p90_microseconds / 1000000, 2)
                                
                                print(f"⚡ Android P90 Launch Time: {p90_seconds}s")
                                app_data["android"]["p90_launch_time_seconds"] = p90_seconds
                                android_p90_launch_captured = True
                except Exception as e:
                    print(f"❌ Error parsing Android P90 launch time response: {e}")

            # Handle Dominant Release response
            if (current_phase in ["ios_dominant_release", "android_dominant_release"] and 
                "analytics.google.com/analytics/app/data/v2/venus?" in url and "reportId" in url):
                try:
                    response_text = await response.text()

                    # Strip the dangling `)]}',` prefix
                    if response_text.startswith(")]}',"):
                        response_text = response_text[5:]

                    json_response = json.loads(response_text)

                    # Extract dominant release data
                    dominant_releases = json_response.get("default", {}).get("responses", [])
                    if len(dominant_releases) >= 3 and dominant_releases[2].get("responseRows"):
                        release_data = dominant_releases[2]["responseRows"][0].get("dimensionCompoundValues", [])
                        if release_data:
                            # Extract version - handle both string and dict formats
                            version_data = release_data[0]
                            if isinstance(version_data, dict) and 'value' in version_data:
                                dominant_version = version_data['value']
                            else:
                                dominant_version = str(version_data)
                            platform = "iOS" if current_phase == "ios_dominant_release" else "Android"
                            print(f"📱 {platform} Dominant Release: {dominant_version}")

                            if current_phase == "ios_dominant_release":
                                ios_dominant_release_captured = True
                                app_data["ios"]["dominant_release"] = dominant_version
                            else:  # android_dominant_release
                                android_dominant_release_captured = True
                                app_data["android"]["dominant_release"] = dominant_version
                except Exception as e:
                    print(f"❌ Error parsing {current_phase} response: {e}")

            # Handle Play Console ANR response
            if (current_phase == "up_anrs" and
                "playconsolehealth-pa.clients6.google.com" in url and
                "errorClusters" in url and
                app_config["android"]["play_console"]["app_id"] in url):
                try:
                    # Check if request body contains the required criteria
                    request = response.request
                    request_body = request.post_data

                    if (request_body and
                        '"19":2' in request_body and
                        '"2":[3]' in request_body):
                        json_response = await response.json()
                        anr_data = json_response.get("1", [])

                        # Group ANRs by name and merge data
                        grouped_anrs = {}
                        for anr in anr_data:
                            anr_name = anr.get("2", {}).get("1", "Unknown")
                            affected_users = int(anr.get("6", "0"))
                            event_count = int(anr.get("7", "0"))
                            impact_percentage = float(anr.get("11", 0)) * 100  # Convert to percentage

                            if anr_name in grouped_anrs:
                                grouped_anrs[anr_name]["affected_users"] += affected_users
                                grouped_anrs[anr_name]["event_count"] += event_count
                                grouped_anrs[anr_name]["impact_percentage"] += impact_percentage
                            else:
                                grouped_anrs[anr_name] = {
                                    "affected_users": affected_users,
                                    "event_count": event_count,
                                    "impact_percentage": impact_percentage
                                }

                        # Sort by impact percentage and get top ANRs
                        sorted_anrs = sorted(grouped_anrs.items(),
                                           key=lambda x: x[1]["impact_percentage"], reverse=True)[:3]

                        # Store in JSON structure
                        anr_list = []
                        for name, data in sorted_anrs:
                            anr_list.append({
                                "name": name,
                                "impact_percentage": round(data["impact_percentage"], 2),
                                "affected_users": data["affected_users"],
                                "events": data["event_count"]
                            })
                        app_data["android"]["up_anrs"] = anr_list

                        print(f"🎯 Top 3 Play Console User Perceived ANRs:")
                        for i, (name, data) in enumerate(sorted_anrs, 1):
                            print(f"  {i}. {name}")
                            print(f"     Impact: {data['impact_percentage']:.2f}%")
                            print(f"     Affected Users: {data['affected_users']}, Events: {data['event_count']}")

                        play_console_anrs_captured = True
                        print("✅ Play Console ANR data captured!")
                except Exception as e:
                    print(f"❌ Error parsing Play Console ANR response: {e}")

            # Handle metrics report response
            if not metrics_captured and re.search(r'metrics:getMetricsReport', url):
                try:
                    json_response = await response.json()

                    # Check if this response has valid date range
                    grouped_metrics = json_response.get("groupedMetrics", [])
                    if (grouped_metrics and
                        grouped_metrics[0].get("intervalMetrics") and
                        is_valid_date_range(
                            grouped_metrics[0]["intervalMetrics"][0].get("startTime", ""),
                            grouped_metrics[0]["intervalMetrics"][0].get("endTime", ""))):

                        # Extract crash-free rates
                        non_fatal_rate = None
                        fatal_rate = None

                        for metric in grouped_metrics:
                            fatality = metric.get("fatality")
                            if fatality == "NON_FATAL" and metric.get("intervalMetrics"):
                                # Extract non-fatal crash-free rate
                                ratio = metric["intervalMetrics"][0].get("crashlyticsEventFreeUsersCombined", {}).get("ratio", 0)
                                non_fatal_rate = round(ratio * 100, 2)  # Round to 2 decimal places
                                non_fatal_installs = int(metric["intervalMetrics"][0].get("totalCrashlyticsInstalls", "0"))
                            elif fatality == "FATAL" and metric.get("intervalMetrics"):
                                ratio = metric["intervalMetrics"][0].get("crashlyticsEventFreeUsersCombined", {}).get("ratio", 0)
                                fatal_rate = round(ratio * 100, 2)  # Round to 2 decimal places
                                fatal_installs = int(metric["intervalMetrics"][0].get("totalCrashlyticsInstalls", "0"))

                        print(f"📊 NON_FATAL crash-free users rate: {non_fatal_rate}%")
                        print(f"📊 FATAL crash-free users rate: {fatal_rate}%")

                        # Store crash-free rates and install counts in JSON
                        app_data["android"]["crash_free_rates"] = {
                            "fatal": fatal_rate,
                            "non_fatal": non_fatal_rate
                        }
                        app_data["android"]["total_installs"] = {
                            "fatal": fatal_installs,
                            "non_fatal": non_fatal_installs
                        }

                        metrics_requests.append(url)
                        metrics_captured = True
                        print("✅ Metrics captured, moving to crashes...")
                    else:
                        print(f"⏭️  Skipping - invalid date range or missing data")
                except Exception as e:
                    print(f"❌ Error parsing JSON response: {e}")

            # Handle ANR metrics report response (separate call for ANR page)
            elif current_phase == "anr_metrics" and re.search(r'metrics:getMetricsReport', url):
                try:
                    json_response = await response.json()
                    grouped_metrics = json_response.get("groupedMetrics", [])
                    if (grouped_metrics and
                        grouped_metrics[0].get("intervalMetrics") and
                        is_valid_date_range(
                            grouped_metrics[0]["intervalMetrics"][0].get("startTime", ""),
                            grouped_metrics[0]["intervalMetrics"][0].get("endTime", ""))):
                        grouped_metrics = json_response.get("groupedMetrics", [])
                        for metric in grouped_metrics:
                            if metric.get("fatality") == "ANR" and metric.get("intervalMetrics"):
                                anr_installs = int(metric["intervalMetrics"][0].get("totalCrashlyticsInstalls", "0"))
                                anr_metrics_captured = True
                                # Don't change phase here - let main flow handle it
                                break
                except Exception as e:
                    print(f"❌ Error parsing ANR metrics JSON response: {e}")

            # Handle iOS metrics report response
            elif (current_phase == "ios_metrics" or current_phase == "ios_crashes" or current_phase == "ios_non_fatals") and re.search(r'metrics:getMetricsReport', url):
                try:
                    json_response = await response.json()
                    grouped_metrics = json_response.get("groupedMetrics", [])
                    if (grouped_metrics and
                        grouped_metrics[0].get("intervalMetrics") and
                        is_valid_date_range(
                            grouped_metrics[0]["intervalMetrics"][0].get("startTime", ""),
                            grouped_metrics[0]["intervalMetrics"][0].get("endTime", ""))):
                        grouped_metrics = json_response.get("groupedMetrics", [])
                        for metric in grouped_metrics:
                            fatality = metric.get("fatality")
                            if fatality == "FATAL" and metric.get("intervalMetrics"):
                                ios_fatal_installs = int(metric["intervalMetrics"][0].get("totalCrashlyticsInstalls", "0"))
                                # Capture fatal crash-free rate on both ios_crashes and ios_metrics phases
                                if (current_phase in ["ios_crashes", "ios_metrics"] and
                                    "fatal" not in app_data["ios"]["crash_free_rates"]):
                                    ratio = metric["intervalMetrics"][0].get("crashlyticsEventFreeUsersCombined", {}).get("ratio", 0)
                                    ios_fatal_rate = round(ratio * 100, 2)  # Round to 2 decimal places
                                    print(f"📊 iOS FATAL crash-free users rate: {ios_fatal_rate}%")

                                    app_data["ios"]["crash_free_rates"]["fatal"] = ios_fatal_rate
                                    app_data["ios"]["total_installs"]["fatal"] = ios_fatal_installs
                            elif fatality == "NON_FATAL" and metric.get("intervalMetrics"):
                                ios_non_fatal_installs = int(metric["intervalMetrics"][0].get("totalCrashlyticsInstalls", "0"))
                                # Capture non-fatal crash-free rate on both ios_non_fatals and ios_metrics phases
                                if (current_phase in ["ios_non_fatals", "ios_metrics"] and
                                    "non_fatal" not in app_data["ios"]["crash_free_rates"]):
                                    ratio = metric["intervalMetrics"][0].get("crashlyticsEventFreeUsersCombined", {}).get("ratio", 0)
                                    ios_non_fatal_rate = round(ratio * 100, 2)  # Round to 2 decimal places
                                    print(f"📊 iOS NON_FATAL crash-free users rate: {ios_non_fatal_rate}%")

                                    # Store iOS crash-free rates and installs
                                    if "non_fatal" not in app_data["ios"]["crash_free_rates"]:
                                        app_data["ios"]["crash_free_rates"]["non_fatal"] = ios_non_fatal_rate
                                        app_data["ios"]["total_installs"]["non_fatal"] = ios_non_fatal_installs

                        if current_phase == "ios_metrics":
                            ios_metrics_captured = True
                        elif current_phase == "ios_non_fatals":
                            # Capture installs when on non-fatals page
                            print(f"📊 Captured iOS non-fatal installs: {ios_non_fatal_installs}")
                            ios_metrics_captured = True  # Set flag so issues handler work

                            # Process any pending iOS non-fatal issues if they were captured before installs
                            if ios_nonfatal_issues_processed:
                                print("🔄 Reprocessing iOS non-fatal impact with correct install count...")
                except Exception as e:
                    error_msg = str(e)
                    # Don't print errors for responses that were already consumed
                    if "No resource with given identifier" not in error_msg and "Protocol error" not in error_msg:
                        print(f"❌ Error parsing iOS metrics JSON response: {e}")
                    # Still try to set the flag if we got fatal rate
                    if "fatal" in app_data["ios"]["crash_free_rates"]:
                        ios_metrics_captured = True

            # Handle top issues response
            elif re.search(r'metrics:listFirebaseTopOpenIssues', url):
                if current_phase == "crashes" and not crashes_captured:
                    issue_type = "Crashes"
                    total_installs = fatal_installs
                elif current_phase == "non_fatals" and not non_fatals_captured:
                    issue_type = "Non-Fatal Issues"
                    total_installs = non_fatal_installs
                elif current_phase == "anrs" and anr_metrics_captured:
                    issue_type = "ANRs"
                    total_installs = anr_installs
                elif current_phase == "ios_crashes" and ios_metrics_captured:
                    issue_type = "iOS Crashes"
                    total_installs = ios_fatal_installs
                elif current_phase == "ios_non_fatals" and ios_metrics_captured:
                    issue_type = "iOS Non-Fatal Issues"
                    total_installs = ios_non_fatal_installs  # Will be captured from metrics on this page
                elif current_phase == "ios_non_fatals" and not ios_metrics_captured:
                    # iOS non-fatal issues came before metrics - mark for later processing
                    ios_nonfatal_issues_processed = True
                    print("⏳ iOS non-fatal issues detected before install count available - will process after metrics")
                    return
                else:
                    return  # Skip if we're not in the right phase

                try:
                    json_response = await response.json()
                    top_issues = json_response.get("topIssues", [])

                    # Group issues by subtitle and sum their metrics
                    grouped_issues = {}
                    for issue in top_issues:
                        caption = issue.get("caption", {})
                        subtitle = caption.get("subtitle", "Unknown")
                        title = caption.get("title", "Unknown")

                        impacted_devices = int(issue.get("impactedDevicesCount", "0"))
                        events_count = int(issue.get("eventsCount", "0"))

                        # Group by title for ANRs, by subtitle for Android only
                        if current_phase == "anrs" or current_phase.startswith("ios"):
                            group_key = title
                            display_title = title
                        else:
                            group_key = subtitle
                            display_title = subtitle if subtitle != "Unknown" else title

                        # Skip grouping for iOS - treat each issue individually
                        if current_phase.startswith("ios"):
                            issue_key = f"{title}_{len(grouped_issues)}"  # Unique key for each issue
                            # For iOS non-fatals, use subtitle; for iOS crashes, use title
                            display_name = subtitle if current_phase == "ios_non_fatals" else title
                            grouped_issues[issue_key] = {
                                "title": display_name,
                                "original_title": title,
                                "subtitle": subtitle,
                                "impactedDevicesCount": impacted_devices,
                                "eventsCount": events_count
                            }
                        else:
                            if group_key in grouped_issues:
                                grouped_issues[group_key]["impactedDevicesCount"] += impacted_devices
                                grouped_issues[group_key]["eventsCount"] += events_count
                            else:
                                grouped_issues[group_key] = {
                                    "title": display_title,
                                    "original_title": title,
                                    "subtitle": subtitle,
                                    "impactedDevicesCount": impacted_devices,
                                    "eventsCount": events_count
                                }

                    # Sort by impacted devices count and get top 3
                    sorted_issues = sorted(grouped_issues.values(),
                                         key=lambda x: x["impactedDevicesCount"], reverse=True)[:3]

                    print(f"🏆 Top 3 {issue_type}:")
                    for i, issue in enumerate(sorted_issues, 1):
                        impact_percent = int(issue['impactedDevicesCount'] / total_installs * 100) if total_installs > 0 else 0

                        # Store in JSON structure
                        issue_data = {
                            "rank": i,
                            "name": issue['title'],
                            "impact_percentage": impact_percent,
                            "impacted_devices": issue['impactedDevicesCount'],
                            "events": issue['eventsCount']
                        }

                        # Add to appropriate category
                        if current_phase == "crashes":
                            app_data["android"]["top_crashes"].append(issue_data)
                        elif current_phase == "non_fatals":
                            app_data["android"]["top_non_fatals"].append(issue_data)
                        elif current_phase == "anrs":
                            app_data["android"]["all_anrs"].append(issue_data)
                        elif current_phase == "ios_crashes":
                            app_data["ios"]["top_crashes"].append(issue_data)
                        elif current_phase == "ios_non_fatals":
                            app_data["ios"]["top_non_fatals"].append(issue_data)

                        print(f"  {i}. {issue['title']}")
                        print(f"     Impact: {impact_percent}%")
                        print(f"     Impacted Devices: {issue['impactedDevicesCount']}, Events: {issue['eventsCount']}")

                    if current_phase == "crashes":
                        crashes_captured = True
                    elif current_phase == "non_fatals":
                        non_fatals_captured = True
                    elif current_phase == "anrs":
                        print("✅ Android data captured! Moving to iOS...")
                    elif current_phase == "ios_crashes":
                        ios_crashes_captured = True
                    elif current_phase == "ios_non_fatals":
                        ios_non_fatals_captured = True

                except Exception as e:
                    print(f"❌ Error parsing JSON response: {e}")

        page.on("response", handle_response)

        await page.goto(firebase_url, timeout=60000)


        # Wait for metrics to be captured
        while not metrics_captured:
            await asyncio.sleep(1)

        await asyncio.sleep(2)

        current_phase = "crashes"
        await page.goto(top_crashes_url)

        # Wait for crashes to be captured
        while not crashes_captured:
            await asyncio.sleep(1)

        current_phase = "non_fatals"
        await asyncio.sleep(3)  # Wait before navigation
        await page.goto(top_non_fatals_url)

        # Wait for non-fatals to be captured
        while not non_fatals_captured:
            await asyncio.sleep(1)

        current_phase = "anr_metrics"
        await asyncio.sleep(3)  # Wait before navigation
        await page.goto(top_anrs_url)

        # Wait for ANRs to be captured, then move to iOS
        while not anr_metrics_captured:
            await asyncio.sleep(1)
        
        # Change phase after metrics are captured
        current_phase = "anrs"

        # Start iOS data collection (only if app has iOS)
        if app_config.get("has_ios") and ios_crashes_url:
            print("\n📱 Starting iOS data collection...")
            await asyncio.sleep(3)
            current_phase = "ios_metrics"
            await page.goto(ios_crashes_url)


            # Multiple refresh attempts to ensure data loading
            await asyncio.sleep(3)
            await page.reload()

            await asyncio.sleep(2)
            await page.reload()

            # Clear any cached state by evaluating JavaScript
            await page.evaluate("() => { window.location.reload(true); }")

            # Wait for iOS metrics, then get crashes and non-fatals
            timeout_seconds = 120
            elapsed = 0
            while not ios_metrics_captured and elapsed < timeout_seconds:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed % 10 == 0:
                    print(f"   Still waiting for iOS metrics... ({elapsed}s)")
            if not ios_metrics_captured:
                print(f"⚠️  Timeout waiting for iOS metrics after {timeout_seconds}s, continuing...")
                # Set flag to continue even if metrics weren't captured
                ios_metrics_captured = True

            current_phase = "ios_crashes"
            
            elapsed = 0
            while not ios_crashes_captured and elapsed < timeout_seconds:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed % 10 == 0:
                    print(f"   Still waiting for iOS crashes... ({elapsed}s)")
            if not ios_crashes_captured:
                print(f"⚠️  Timeout waiting for iOS crashes after {timeout_seconds}s, continuing...")
                ios_crashes_captured = True

            current_phase = "ios_non_fatals"
            await asyncio.sleep(3)
            await page.goto(ios_non_fatals_url)

            # Wait for iOS non-fatals to be captured
            elapsed = 0
            while not ios_non_fatals_captured and elapsed < timeout_seconds:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed % 10 == 0:
                    print(f"   Still waiting for iOS non-fatals... ({elapsed}s)")
            if not ios_non_fatals_captured:
                print(f"⚠️  Timeout waiting for iOS non-fatals after {timeout_seconds}s, continuing...")
                ios_non_fatals_captured = True

        # Move to Play Console ANR collection
        print("\n🎯 Starting Play Console ANR data collection...")
        current_phase = "up_anrs"
        await asyncio.sleep(3)
        await page.goto(play_console_anr_url)

        # Wait for Play Console ANRs to be captured
        timeout_seconds = 120
        elapsed = 0
        while not play_console_anrs_captured and elapsed < timeout_seconds:
            await asyncio.sleep(1)
            elapsed += 1
            if elapsed % 10 == 0:
                print(f"   Still waiting for Play Console ANRs... ({elapsed}s)")
        if not play_console_anrs_captured:
            print(f"⚠️  Timeout waiting for Play Console ANRs after {timeout_seconds}s, continuing...")
            play_console_anrs_captured = True

        # Move to iOS Dominant Release collection (only if app has iOS)
        if app_config.get("has_ios") and ios_dominant_release_url:
            print("\n📱 Starting iOS Dominant Release data collection...")
            current_phase = "ios_dominant_release"
            await asyncio.sleep(3)
            await page.goto(ios_dominant_release_url)
            # Wait for iOS dominant release to be captured
            elapsed = 0
            while not ios_dominant_release_captured and elapsed < timeout_seconds:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed % 10 == 0:
                    print(f"   Still waiting for iOS dominant release... ({elapsed}s)")
            if not ios_dominant_release_captured:
                print(f"⚠️  Timeout waiting for iOS dominant release after {timeout_seconds}s, continuing...")
                ios_dominant_release_captured = True

        # Move to Android Dominant Release collection
        if android_dominant_release_url:
            print("\n🤖 Starting Android Dominant Release data collection...")
            current_phase = "android_dominant_release"
            await asyncio.sleep(3)
            await page.goto(android_dominant_release_url)

            # Wait for Android dominant release to be captured
            elapsed = 0
            while not android_dominant_release_captured and elapsed < timeout_seconds:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed % 10 == 0:
                    print(f"   Still waiting for Android dominant release... ({elapsed}s)")
            if not android_dominant_release_captured:
                print(f"⚠️  Timeout waiting for Android dominant release after {timeout_seconds}s, continuing...")
                android_dominant_release_captured = True

        # Move to Android P90 Launch Time collection (only if app has it)
        if app_config.get("has_p90_launch_time", True) and android_p90_launch_url:
            print("\n⚡ Starting Android P90 Launch Time data collection...")
            current_phase = "android_p90_launch"
            await asyncio.sleep(3)
            await page.goto(android_p90_launch_url)

            # Wait for Android P90 launch time to be captured
            elapsed = 0
            while not android_p90_launch_captured and elapsed < timeout_seconds:
                await asyncio.sleep(1)
                elapsed += 1
                if elapsed % 10 == 0:
                    print(f"   Still waiting for Android P90 launch time... ({elapsed}s)")
            if not android_p90_launch_captured:
                print(f"⚠️  Timeout waiting for Android P90 launch time after {timeout_seconds}s, continuing...")
                android_p90_launch_captured = True

        # Automatically fetch Google Play Vitals data
        if GOOGLE_PLAY_AVAILABLE:
            print("\n📊 Fetching Google Play Vitals data...")
            vitals_data = get_google_play_vitals(report_days, app_config["android"]["package_name"])
            if vitals_data:
                app_data["google_play_vitals"] = vitals_data
                print("✅ Google Play Vitals data added successfully!")
                print(f"   ANR Rate: {vitals_data.get('anr_rate', 'N/A')}")
                print(f"   User ANR Rate: {vitals_data.get('user_perceived_anr_rate', 'N/A')}")
                print(f"   Crash Rate: {vitals_data.get('crash_rate', 'N/A')}")
                print(f"   User Crash Rate: {vitals_data.get('user_perceived_crash_rate', 'N/A')}")
                print(f"   Slow Start Rate: {vitals_data.get('slow_start_rate', 'N/A')}")
            else:
                print("⚠️  Google Play Vitals data could not be retrieved")
        
        print(f"✅ Data collection complete for {app_config['name']}!")
        return app_data

    except Exception as e:
        print(f"❌ Error collecting data for {app_config['name']}: {e}")
        return None

async def open_firebase_console(report_days: int):
    """
    Collect vitals data for all apps in APPS_CONFIG
    """
    browser = None
    try:
        # Create a browser instance and get a page
        # Create user data directory for session persistence
        user_data_dir = os.path.expanduser("~/.browser_use_firebase")
        os.makedirs(user_data_dir, exist_ok=True)
        browser_config = {
            "user_data_dir": user_data_dir,
            "extensions": []  # Disable extensions to avoid download/extraction delays
        }
        browser = Browser(**browser_config)
        
        # Start the browser first
        print("🔧 Starting browser...")
        await browser.start()
        print("✅ Browser started")
        
        # Try to get page first - browser.start() might have created one
        print("📄 Getting page object...")
        page = await browser.get_current_page()
        
        # If no page exists, create one by navigating to about:blank
        # Use asyncio.wait_for to add a timeout in case navigate_to hangs
        if page is None:
            print("   No page found, creating one...")
            try:
                await asyncio.wait_for(
                    browser.navigate_to("about:blank"),
                    timeout=10.0  # 10 second timeout
                )
                page = await browser.get_current_page()
            except asyncio.TimeoutError:
                print("⚠️  Navigation timeout, trying to get page anyway...")
                page = await browser.get_current_page()
        
        if page is None:
            raise RuntimeError("Failed to get page from browser. Browser may not have started properly.")
        
        print("✅ Page obtained")
        
        # Set timeouts and disable heavy resources
        page.set_default_timeout(60000)  # 60 second timeout
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico}", lambda route: route.abort())  # Block images
        await page.route("**/*.{css,woff,woff2,ttf}", lambda route: route.abort())  # Block fonts/CSS
        print("✅ Page configured")
        
        # Initialize final data structure
        all_apps_data = {
            "timestamp": datetime.now().isoformat(),
            "date_range_days": DATE_RANGE_DAYS,
            "apps": {}
        }
        
        # Collect data for each app
        for app_key, app_config in APPS_CONFIG.items():
            app_data = await collect_app_data(report_days, app_key, app_config, page)
            if app_data:
                all_apps_data["apps"][app_key] = app_data
                # Reset flags for next app
                await asyncio.sleep(2)  # Brief pause between apps
        
        print("\n" + "="*60)
        print("✅ All data collection complete!")
        print("="*60)

        # Save data to JSON file
        output_filename = f"crash_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(output_filename, 'w') as f:
                json.dump(all_apps_data, f, indent=2)
            print(f"📄 Data saved to {output_filename}")
        except Exception as e:
            print(f"❌ Error saving data to file: {e}")

        # Print summary for all apps
        print(f"\n📋 Summary:")
        for app_key, app_data in all_apps_data["apps"].items():
            print(f"\n  {app_data.get('app_name', app_key)}:")
            print(f"    Android Fatal Crash-Free Rate: {app_data['android']['crash_free_rates'].get('fatal', 'N/A')}")
            print(f"    Android Non-Fatal Crash-Free Rate: {app_data['android']['crash_free_rates'].get('non_fatal', 'N/A')}")
            if app_data.get('ios', {}).get('crash_free_rates'):
                print(f"    iOS Fatal Crash-Free Rate: {app_data['ios']['crash_free_rates'].get('fatal', 'N/A')}")
                print(f"    iOS Non-Fatal Crash-Free Rate: {app_data['ios']['crash_free_rates'].get('non_fatal', 'N/A')}")
            print(f"    Android Dominant Release: {app_data['android']['dominant_release']}")
            if app_data.get('ios', {}).get('dominant_release'):
                print(f"    iOS Dominant Release: {app_data['ios']['dominant_release']}")
            if app_data['android'].get('p90_launch_time_seconds'):
                print(f"    Android P90 Launch Time: {app_data['android']['p90_launch_time_seconds']}s")

    except KeyboardInterrupt:
        print("\nClosing browser...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up browser
        if browser:
            try:
                await browser.close()
            except:
                pass

# Alternative: Even simpler with just opening the URL
async def simple_open_url():
    """
    Simplest approach - just open the URL
    """
    import webbrowser

    firebase_url = "https://console.firebase.google.com/u/0/project/portercustomerapp/crashlytics/app/android:com.theporter.android.customerapp/issues?state=open&time=last-thirty-days&tag=all&sort=eventCount"

    print(f"Opening Firebase console in default browser...")
    webbrowser.open(firebase_url)
    print("Done!")

if __name__ == "__main__":
      days = _choose_report_days()
      # Reflect selection globally for date validations
      DATE_RANGE_DAYS = days
      print(f"🚀 Starting App Vitals Collection ({days}-day period)")
      print(f"Opening Firebase Console with browser-use... (report window: {days} days)")
      asyncio.run(open_firebase_console(days))


