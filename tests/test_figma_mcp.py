"""Test script to verify Figma MCP Server integration and rate limiting."""
import requests
import time
import json

BASE_URL = "http://localhost:8000"


def test_rate_limiting():
    """Test that rate limiting is working."""
    print("=" * 80)
    print("TEST: Rate Limiting & MCP Server Integration")
    print("=" * 80)

    # Test 1: Check if server is running
    print("\n1. Checking server status...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"   ✅ Server is running: {response.json()}")
    except Exception as e:
        print(f"   ❌ Server not running: {e}")
        return

    # Test 2: Check stats endpoint (component reuse tracking)
    print("\n2. Checking component reuse tracking...")
    try:
        response = requests.get(f"{BASE_URL}/api/stats")
        stats = response.json()
        print(f"   ✅ Stats endpoint working:")
        print(f"      - Total projects: {stats.get('total_projects', 0)}")
        print(f"      - Total components: {stats.get('total_components', 0)}")
        print(f"      - Component reuses: {stats.get('total_component_reuses', 0)}")
    except Exception as e:
        print(f"   ❌ Stats endpoint failed: {e}")

    # Test 3: List existing projects
    print("\n3. Listing existing projects...")
    try:
        response = requests.get(f"{BASE_URL}/api/projects")
        projects = response.json()
        print(f"   ✅ Found {projects.get('total', 0)} projects")
        if projects.get('projects'):
            print("   Recent projects:")
            for p in projects['projects'][:3]:
                print(f"      - {p['name']} ({p['status']})")
    except Exception as e:
        print(f"   ❌ Failed to list projects: {e}")

    # Test 4: Test project creation (with rate limiting)
    print("\n4. Testing project creation with rate limiting...")
    print("   Note: This will use REST API with rate limiting")
    print("   To use MCP Server, set USE_FIGMA_MCP=true in .env")
    
    test_figma_url = "https://www.figma.com/design/a577puJyvBsiQljgPCh4IA/Samsung-Website-Redesign"
    
    print(f"\n   Creating test project...")
    print(f"   Figma URL: {test_figma_url}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/projects/create",
            json={
                "figma_url": test_figma_url,
                "project_name": f"test-rate-limit-{int(time.time())}",
                "ui_library": "tailwind",
                "add_as": "new_project",
            },
            timeout=10,
        )
        
        if response.status_code == 200:
            result = response.json()
            project_id = result.get("project_id")
            print(f"   ✅ Project created: ID {project_id}")
            print(f"   Status: {result.get('status')}")
            print(f"   Message: {result.get('message')}")
            
            # Poll for status
            print(f"\n   Polling project status...")
            max_wait = 60  # 1 minute for quick test
            start = time.time()
            
            while time.time() - start < max_wait:
                time.sleep(5)
                status_response = requests.get(f"{BASE_URL}/api/projects/{project_id}/status")
                status = status_response.json()
                
                print(f"   [{int(time.time() - start)}s] Status: {status['status']}")
                
                if status["status"] in ["success", "failed", "completed_with_errors"]:
                    if status["status"] == "success":
                        print(f"   ✅ Project completed successfully!")
                        print(f"      - Components generated: {status['components_generated']}")
                        print(f"      - Components reused: {status['components_reused']}")
                    else:
                        error_msg = status.get("error_message", "Unknown error")
                        print(f"   ⚠️  Project status: {status['status']}")
                        print(f"      Error: {error_msg}")
                        
                        # Check if it's a rate limit error
                        if "429" in error_msg or "rate limit" in error_msg.lower():
                            print(f"\n   ⚠️  Rate limit detected!")
                            print(f"   💡 Suggestions:")
                            print(f"      - Wait for rate limit to reset")
                            print(f"      - Enable MCP Server (set USE_FIGMA_MCP=true)")
                            print(f"      - Upgrade Figma seat to Dev/Full")
                    break
        else:
            print(f"   ❌ Failed to create project: {response.status_code}")
            print(f"   Response: {response.text}")
    except requests.exceptions.Timeout:
        print(f"   ⚠️  Request timeout (server may be processing)")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Check if rate limiting is working (429 errors should retry)")
    print("2. Enable MCP Server by setting USE_FIGMA_MCP=true in .env")
    print("3. Verify component reuse tracking in stats")
    print("4. Monitor logs for rate limit retries")


if __name__ == "__main__":
    try:
        test_rate_limiting()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
