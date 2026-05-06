"""Test script for multi-page functionality."""
import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_multipage():
    """Test creating a project and adding a page to it."""

    # Test 1: Create first project (new_project mode)
    print("=" * 80)
    print("TEST 1: Creating first project (new_project mode)")
    print("=" * 80)

    response = requests.post(
        f"{BASE_URL}/api/projects/create",
        json={
            "figma_url": "https://www.figma.com/design/a577puJyvBsiQljgPCh4IA/Samsung-Website-Redesign",
            "project_name": "samsung-multipage-parent",
            "ui_library": "tailwind",
            "add_as": "new_project",
        }
    )

    print(f"Status: {response.status_code}")
    result1 = response.json()
    print(json.dumps(result1, indent=2))

    if response.status_code != 200:
        print("❌ Failed to create first project")
        return

    project_id_1 = int(result1["project_id"])
    print(f"\n✅ Project 1 created with ID: {project_id_1}")

    # Poll for completion
    print("\n" + "=" * 80)
    print("Waiting for first project to complete...")
    print("=" * 80)

    max_wait = 600  # 10 minutes
    start = time.time()

    while time.time() - start < max_wait:
        time.sleep(10)

        status_response = requests.get(f"{BASE_URL}/api/projects/{project_id_1}/status")
        status = status_response.json()

        print(f"[{int(time.time() - start)}s] Status: {status['status']}")

        if status["status"] in ["success", "failed", "completed_with_errors"]:
            print("\n" + json.dumps(status, indent=2))

            if status["status"] == "success":
                print(f"\n✅ Project 1 completed successfully!")
                print(f"   - Components generated: {status['components_generated']}")
                print(f"   - Components reused: {status['components_reused']}")
                print(f"   - Project path: {status['project_path']}")
                break
            else:
                print(f"\n❌ Project 1 failed: {status.get('error_message')}")
                return
    else:
        print("\n❌ Timeout waiting for project 1")
        return

    # Test 2: Add second Figma as NEW PAGE to the first project
    print("\n" + "=" * 80)
    print("TEST 2: Adding second Figma as NEW PAGE (new_page mode)")
    print("=" * 80)

    time.sleep(5)  # Brief pause

    response2 = requests.post(
        f"{BASE_URL}/api/projects/create",
        json={
            "figma_url": "https://www.figma.com/design/CT3jTGs5RJ5yQksZvhApof/Samsung-Website-Redesign",
            "project_name": "about-page",
            "ui_library": "tailwind",
            "add_as": "new_page",
            "parent_project_id": project_id_1,
        }
    )

    print(f"Status: {response2.status_code}")
    result2 = response2.json()
    print(json.dumps(result2, indent=2))

    if response2.status_code != 200:
        print(f"❌ Failed to add page: {result2}")
        return

    project_id_2 = int(result2["project_id"])
    print(f"\n✅ Page created with ID: {project_id_2}")

    # Poll for completion
    print("\n" + "=" * 80)
    print("Waiting for page addition to complete...")
    print("=" * 80)

    start = time.time()

    while time.time() - start < max_wait:
        time.sleep(10)

        status_response = requests.get(f"{BASE_URL}/api/projects/{project_id_2}/status")
        status = status_response.json()

        print(f"[{int(time.time() - start)}s] Status: {status['status']}")

        if status["status"] in ["success", "failed", "completed_with_errors"]:
            print("\n" + json.dumps(status, indent=2))

            if status["status"] == "success":
                print(f"\n✅ Page added successfully!")
                print(f"   - Components generated: {status['components_generated']}")
                print(f"   - Components reused: {status['components_reused']}")
                print(f"   - Is page: {status.get('is_page')}")
                print(f"   - Route path: {status.get('route_path')}")

                # Final verification
                print("\n" + "=" * 80)
                print("VERIFICATION")
                print("=" * 80)
                print(f"Check the project directory: {status.get('project_path', result1.get('project_path'))}")
                print("Expected structure:")
                print("  - src/pages/HomePage.tsx (from first Figma)")
                print("  - src/pages/AboutPage.tsx (from second Figma)")
                print("  - src/App.tsx (should have both routes)")
                print("  - src/components/ (shared components)")
                break
            else:
                print(f"\n❌ Page addition failed: {status.get('error_message')}")
                return
    else:
        print("\n❌ Timeout waiting for page addition")
        return

    print("\n" + "=" * 80)
    print("✅ MULTI-PAGE TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_multipage()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
