"""Test plugin conversion flow step by step."""
import asyncio
import sys
sys.path.insert(0, 'E:/code/AI/Aura2')

from dotenv import load_dotenv
load_dotenv('E:/code/AI/Aura2/.env')

from pathlib import Path
from backend.config import settings

print("Step 1: Imports done")
print(f"  - LiteLLM API Key: {settings.litellm_api_key[:10]}...")
print(f"  - LiteLLM Base URL: {settings.litellm_base_url}")

# Test setup_project_from_template
print("\nStep 2: Testing setup_project_from_template...")
from backend.agents.figma_to_react import setup_project_from_template

output_dir = Path("E:/code/AI/Aura2/generated_projects")
project_name = "test-flow"
try:
    project_path = setup_project_from_template(project_name, output_dir, "tailwind")
    print(f"  ✅ Project created at: {project_path}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test component store
print("\nStep 3: Testing component store...")
try:
    from backend.rag.component_store import get_component_store
    store = get_component_store()
    count = store.count()
    print(f"  ✅ Component store initialized, count: {count}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test MCP server creation
print("\nStep 4: Testing MCP server creation...")
try:
    from backend.mcp_tools.component_library import create_component_library_server
    server = create_component_library_server()
    print(f"  ✅ MCP server created: {server}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test agent initialization
print("\nStep 5: Testing agent initialization...")
try:
    from backend.agents.figma_to_react import FigmaToReactAgent
    agent = FigmaToReactAgent(
        figma_token=settings.figma_token,
        litellm_api_key=settings.litellm_api_key,
    )
    print(f"  ✅ Agent created")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test LiteLLM configuration
print("\nStep 6: Testing LiteLLM configuration...")
import os
print(f"  ANTHROPIC_BASE_URL: {os.environ.get('ANTHROPIC_BASE_URL', 'NOT SET')}")
print(f"  ANTHROPIC_API_KEY: {os.environ.get('ANTHROPIC_API_KEY', 'NOT SET')[:10]}...")

print("\n✅ All steps completed!")
