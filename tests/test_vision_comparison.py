"""Tests for vision-based comparison system."""

import pytest
from pathlib import Path
from backend.utils.vision_comparison import (
    compare_with_vision_api,
    _encode_image,
    _build_vision_comparison_prompt,
    _parse_vision_response,
)


# Sample test data
SAMPLE_DESIGN_DATA = {
    "name": "Test Design",
    "colors": [
        {"color": "#FF0000"},
        {"color": "#00FF00"},
        {"color": "#0000FF"},
    ],
    "fonts": [
        {"family": "Inter"},
        {"family": "Roboto"},
    ],
}


@pytest.mark.asyncio
async def test_vision_comparison_with_mock(tmp_path, monkeypatch):
    """Test vision comparison with mocked API response."""
    # Create dummy images
    figma_img = tmp_path / "figma.png"
    generated_img = tmp_path / "generated.png"

    # Create minimal PNG files (1x1 pixel)
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    figma_img.write_bytes(png_data)
    generated_img.write_bytes(png_data)

    # Mock the Anthropic client
    class MockMessage:
        def __init__(self):
            self.content = [MockTextBlock()]

    class MockTextBlock:
        text = """
        {
          "matches": true,
          "confidence": 0.95,
          "overall_assessment": "Images match well",
          "discrepancies": [],
          "accuracy_scores": {
            "layout": 0.95,
            "spacing": 0.92,
            "colors": 0.98,
            "typography": 0.94,
            "effects": 0.90
          },
          "visual_explanation": "Images are very similar with minor spacing differences"
        }
        """

    class MockClient:
        class messages:
            @staticmethod
            def create(*args, **kwargs):
                return MockMessage()

    # Mock the anthropic module
    class MockAnthropic:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            if name == "messages":
                return MockClient.messages
            return super().__getattr__(name)

    monkeypatch.setattr("backend.utils.vision_comparison.anthropic.Anthropic", MockAnthropic)

    # Run test
    result = await compare_with_vision_api(
        figma_screenshot_path=figma_img,
        generated_screenshot_path=generated_img,
        design_data=SAMPLE_DESIGN_DATA,
    )

    # Assertions
    assert result["matches"] == True
    assert result["confidence"] >= 0.9
    assert "accuracy_scores" in result
    assert result["accuracy_scores"]["layout"] >= 0.9


def test_encode_image(tmp_path):
    """Test image encoding to base64."""
    # Create test image
    test_img = tmp_path / "test.png"
    png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    test_img.write_bytes(png_data)

    # Encode
    encoded = _encode_image(test_img)

    assert encoded is not None
    assert isinstance(encoded, str)
    assert len(encoded) > 0


def test_build_vision_comparison_prompt():
    """Test prompt building for vision API."""
    prompt = _build_vision_comparison_prompt(SAMPLE_DESIGN_DATA, focus_areas=["header", "footer"])

    assert "pixel-perfect" in prompt.lower()
    assert "IMAGE 1" in prompt
    assert "IMAGE 2" in prompt
    assert "Test Design" in prompt
    assert "#FF0000" in prompt
    assert "Inter" in prompt
    assert "header" in prompt.lower()
    assert "JSON" in prompt


def test_parse_vision_response_valid():
    """Test parsing valid JSON response."""
    response = """
    Here's the comparison result:
    {
      "matches": false,
      "confidence": 0.85,
      "discrepancies": [
        {
          "type": "spacing",
          "severity": "high",
          "location": "Header",
          "expected": "24px padding",
          "actual": "16px padding",
          "coordinates": {"x": 0, "y": 0, "width": 100, "height": 50},
          "fix_instructions": {
            "target_file": "src/components/Header.tsx",
            "target_element": "header",
            "current_value": "p-4",
            "new_value": "p-6",
            "explanation": "Increase padding"
          }
        }
      ],
      "accuracy_scores": {
        "layout": 0.90,
        "spacing": 0.75,
        "colors": 0.95,
        "typography": 0.88,
        "effects": 0.85
      }
    }
    """

    result = _parse_vision_response(response)

    assert result["matches"] == False
    assert result["confidence"] == 0.85
    assert len(result["discrepancies"]) == 1
    assert result["discrepancies"][0]["type"] == "spacing"
    assert result["accuracy_scores"]["layout"] == 0.90


def test_parse_vision_response_malformed():
    """Test parsing malformed response."""
    response = "This is not JSON"

    result = _parse_vision_response(response)

    # Should return fallback result
    assert result["confidence"] == 0.0
    assert result["matches"] == False
    assert "discrepancies" in result


def test_parse_vision_response_missing_fields():
    """Test parsing response with missing fields."""
    response = """
    {
      "matches": true,
      "confidence": 0.95
    }
    """

    result = _parse_vision_response(response)

    # Should fill in default values
    assert result["matches"] == True
    assert result["confidence"] == 0.95
    assert "discrepancies" in result
    assert isinstance(result["discrepancies"], list)
    assert "accuracy_scores" in result


@pytest.mark.asyncio
async def test_vision_comparison_file_not_found():
    """Test handling of missing files."""
    result = await compare_with_vision_api(
        figma_screenshot_path=Path("/nonexistent/figma.png"),
        generated_screenshot_path=Path("/nonexistent/generated.png"),
        design_data=SAMPLE_DESIGN_DATA,
    )

    # Should return fallback result
    assert result["confidence"] == 0.0
    assert result["matches"] == False


def test_prompt_includes_all_design_elements():
    """Test that prompt includes all necessary design elements."""
    design_data = {
        "name": "Complex Design",
        "colors": [{"color": "#123456"}, {"color": "#ABCDEF"}],
        "fonts": [{"family": "Helvetica"}, {"family": "Arial"}],
    }

    prompt = _build_vision_comparison_prompt(design_data, None)

    # Check all elements are included
    assert "Complex Design" in prompt
    assert "#123456" in prompt
    assert "#ABCDEF" in prompt
    assert "Helvetica" in prompt
    assert "Arial" in prompt

    # Check analysis categories
    assert "Layout & Spacing" in prompt
    assert "Visual Effects" in prompt
    assert "Typography" in prompt
    assert "Colors" in prompt
    assert "Component Structure" in prompt


def test_prompt_with_focus_areas():
    """Test prompt generation with focus areas."""
    prompt = _build_vision_comparison_prompt(
        SAMPLE_DESIGN_DATA,
        focus_areas=["navigation", "hero section", "footer"]
    )

    assert "FOCUS AREAS" in prompt
    assert "navigation" in prompt
    assert "hero section" in prompt
    assert "footer" in prompt


def test_parse_multiple_discrepancies():
    """Test parsing response with multiple discrepancies."""
    response = """
    {
      "matches": false,
      "confidence": 0.70,
      "discrepancies": [
        {"type": "spacing", "severity": "high", "location": "Header"},
        {"type": "color", "severity": "medium", "location": "Button"},
        {"type": "shadow", "severity": "low", "location": "Card"}
      ],
      "accuracy_scores": {
        "layout": 0.75,
        "spacing": 0.65,
        "colors": 0.80,
        "typography": 0.90,
        "effects": 0.70
      }
    }
    """

    result = _parse_vision_response(response)

    assert len(result["discrepancies"]) == 3
    assert result["discrepancies"][0]["type"] == "spacing"
    assert result["discrepancies"][1]["type"] == "color"
    assert result["discrepancies"][2]["type"] == "shadow"
