#!/usr/bin/env python3
"""Helper script to save browser session after manual SSO login"""

import asyncio
import os
import json
from pathlib import Path
from browser_use import Browser

async def save_session():
    # Use the same user_data_dir as automate_vitals.py
    user_data_dir = os.path.expanduser("~/.browser_use_firebase")
    storage_path = 'browser_state/storage_state.json'
    
    print("🌐 Opening browser for manual login...")
    print("📝 Please complete SSO login, then press Enter here when done.")
    print("   Make sure you're logged into Firebase Console before pressing Enter.")
    print(f"\n💾 Session will be saved to: {user_data_dir}")
    print(f"   And exported to: {storage_path} for GitHub Actions")
    
    browser_config = {
        "user_data_dir": user_data_dir
    }
    
    browser = Browser(**browser_config)
    try:
        # Start the browser first
        await browser.start()
        
        # Navigate to initialize and get a page
        await browser.navigate_to("https://console.firebase.google.com")
        page = await browser.get_current_page()
        
        if page is None:
            raise RuntimeError("Failed to get page from browser. Browser may not have started properly.")
        
        # Navigate to Firebase Console (already done, but ensure page is ready)
        print("\n🌐 Navigating to Firebase Console...")
        try:
            await page.goto("https://console.firebase.google.com", wait_until="domcontentloaded", timeout=30000)
            print("✅ Page loaded (waiting for you to complete login)...")
        except Exception as e:
            print(f"⚠️  Navigation warning: {e}")
            print("   Continuing anyway - you can still login...")
        
        # Wait for user to complete login
        print("\n" + "="*60)
        print("📝 Please complete SSO login in the browser window")
        print("   Once you're logged into Firebase Console, come back here")
        input("✅ Press Enter after completing SSO login and ensuring you're on Firebase Console...")
        
        # Verify we're authenticated
        current_url = page.url
        print(f"\n🔍 Current URL: {current_url}")
        
        # Check for SSO/login redirects
        sso_patterns = [
            'jumpcloud.com',
            'sso.jumpcloud.com',
            '/login',
            'accounts.google.com/v3/signin',
            'accounts.google.com/signin'
        ]
        
        is_sso_redirect = any(pattern in current_url.lower() for pattern in sso_patterns)
        
        if is_sso_redirect:
            print("⚠️  Warning: Still on login/SSO page!")
            print(f"   Detected: {current_url}")
            response = input("Continue anyway? (y/n): ").strip().lower()
            if response != 'y':
                print("❌ Cancelled. Please login and run the script again.")
                return
        else:
            print("✅ Appears to be authenticated (not on login page)")
        
        # Save storage state using browser_use's built-in method
        try:
            # Convert string path to Path object (browser_use expects Path)
            storage_path_obj = Path(storage_path)
            storage_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Use browser_use's save_storage_state method
            await browser.save_storage_state(storage_path_obj)
            
            print(f"\n✅ Browser session saved!")
            print(f"   Local session: {user_data_dir} (automatically managed by browser_use)")
            print(f"   Export file: {storage_path} ({os.path.getsize(storage_path)} bytes)")
            print("\n📦 Next steps:")
            print("   1. git add browser_state/storage_state.json")
            print("   2. git commit -m 'Update browser session'")
            print("   3. git push")
            print("   4. Trigger GitHub Actions workflow rerun (if needed)")
            print("\n   Note: The user_data_dir session is used by automate_vitals.py locally.")
            print("   The storage_state.json file is for GitHub Actions (if you switch to Playwright).")
        except Exception as e:
            print(f"\n⚠️  Could not export storage state: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            print(f"   Session is still saved to: {user_data_dir}")
            print("   This is fine - browser_use will use this directory automatically.")
    finally:
        # Clean up browser
        try:
            await browser.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(save_session())



