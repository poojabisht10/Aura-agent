/**
 * Aura Export - Figma Plugin
 * 
 * Extracts complete design data from Figma and sends it to the Aura backend
 * for React + Tailwind CSS conversion. Bypasses REST API rate limits entirely.
 * 
 * Note: Uses ES5/ES6 compatible syntax for Figma's plugin runtime.
 */

// Show the plugin UI
figma.showUI(__html__, { width: 400, height: 650 });

// Types for extracted design data
interface ExtractedNode {
  id: string;
  name: string;
  type: string;
  visible: boolean;
  opacity?: number;
  layout?: LayoutInfo;
  fills?: Paint[];
  strokes?: Paint[];
  effects?: Effect[];
  cornerRadius?: CornerRadius;
  text?: string;
  style?: TextStyle;
  children?: ExtractedNode[];
  absoluteBoundingBox?: { x: number; y: number; width: number; height: number };
}

interface LayoutInfo {
  layoutMode?: string;
  primaryAxisSizingMode?: string;
  counterAxisSizingMode?: string;
  primaryAxisAlignItems?: string;
  counterAxisAlignItems?: string;
  paddingLeft?: number;
  paddingRight?: number;
  paddingTop?: number;
  paddingBottom?: number;
  itemSpacing?: number;
  width?: number;
  height?: number;
  constraints?: { horizontal: string; vertical: string };
}

interface Paint {
  type: string;
  color?: { r: number; g: number; b: number; a: number };
  opacity?: number;
  imageRef?: string;
  gradientStops?: { position: number; color: { r: number; g: number; b: number; a: number } }[];
}

interface Effect {
  type: string;
  visible: boolean;
  radius?: number;
  color?: { r: number; g: number; b: number; a: number };
  offset?: { x: number; y: number };
  spread?: number;
}

interface CornerRadius {
  topLeft?: number;
  topRight?: number;
  bottomRight?: number;
  bottomLeft?: number;
  all?: number;
}

interface TextStyle {
  fontFamily?: string;
  fontWeight?: number;
  fontSize?: number;
  lineHeight?: number | string;
  letterSpacing?: number;
  textAlign?: string;
  textDecoration?: string;
}

interface ExportedImage {
  nodeId: string;
  name: string;
  data: string; // Base64 encoded
  format: string;
}

interface DesignData {
  fileName: string;
  pages: PageData[];
  colors: Record<string, ColorInfo>;
  fonts: FontInfo[];
  images: Record<string, string>; // imageRef -> base64 data
  stats: {
    pageCount: number;
    frameCount: number;
    colorCount: number;
    fontCount: number;
    imageCount: number;
  };
}

interface PageData {
  id: string;
  name: string;
  frames: ExtractedNode[];
}

interface ColorInfo {
  hex: string;
  rgba: { r: number; g: number; b: number; a: number };
  usage: string[];
}

interface FontInfo {
  family: string;
  weights: number[];
}

// Helper: Get value or default (replacement for ??)
function valueOr<T>(value: T | undefined | null, defaultValue: T): T {
  return (value !== undefined && value !== null) ? value : defaultValue;
}

// Helper: Convert Figma color to hex
function rgbToHex(r: number, g: number, b: number): string {
  var toHex = function(n: number) { 
    return Math.round(n * 255).toString(16).padStart(2, '0'); 
  };
  return '#' + toHex(r) + toHex(g) + toHex(b);
}

// Helper: Copy color object (replacement for spread)
function copyColor(color: RGB, alpha: number): { r: number; g: number; b: number; a: number } {
  return { r: color.r, g: color.g, b: color.b, a: alpha };
}

// Helper: Extract layout info from a node
function extractLayoutInfo(node: SceneNode): LayoutInfo | undefined {
  if (!('layoutMode' in node)) return undefined;
  
  var frameNode = node as FrameNode;
  var layout: LayoutInfo = {};
  
  if (frameNode.layoutMode && frameNode.layoutMode !== 'NONE') {
    layout.layoutMode = frameNode.layoutMode;
    layout.primaryAxisSizingMode = frameNode.primaryAxisSizingMode;
    layout.counterAxisSizingMode = frameNode.counterAxisSizingMode;
    layout.primaryAxisAlignItems = frameNode.primaryAxisAlignItems;
    layout.counterAxisAlignItems = frameNode.counterAxisAlignItems;
    layout.paddingLeft = frameNode.paddingLeft;
    layout.paddingRight = frameNode.paddingRight;
    layout.paddingTop = frameNode.paddingTop;
    layout.paddingBottom = frameNode.paddingBottom;
    layout.itemSpacing = frameNode.itemSpacing;
  }
  
  if ('width' in node && 'height' in node) {
    layout.width = node.width;
    layout.height = node.height;
  }
  
  if ('constraints' in node) {
    layout.constraints = {
      horizontal: (node as FrameNode).constraints.horizontal,
      vertical: (node as FrameNode).constraints.vertical,
    };
  }
  
  return Object.keys(layout).length > 0 ? layout : undefined;
}

// Helper: Extract fills from a node
function extractFills(node: SceneNode): Paint[] | undefined {
  if (!('fills' in node) || !node.fills || node.fills === figma.mixed) return undefined;
  
  var fills = node.fills as ReadonlyArray<any>;
  var result: Paint[] = [];
  
  for (var i = 0; i < fills.length; i++) {
    var fill = fills[i];
    if (fill.visible === false) continue;
    
    var paint: Paint = { type: fill.type };
    
    if (fill.type === 'SOLID' && fill.color) {
      var opacity = fill.opacity !== undefined ? fill.opacity : 1;
      paint.color = copyColor(fill.color, opacity);
    } else if (fill.type === 'IMAGE' && fill.imageHash) {
      paint.imageRef = fill.imageHash;
    } else if ((fill.type === 'GRADIENT_LINEAR' || fill.type === 'GRADIENT_RADIAL') && fill.gradientStops) {
      paint.gradientStops = fill.gradientStops.map(function(stop: any) {
        return {
          position: stop.position,
          color: copyColor(stop.color, 1),
        };
      });
    }
    
    if (fill.opacity !== undefined) {
      paint.opacity = fill.opacity;
    }
    
    result.push(paint);
  }
  
  return result.length > 0 ? result : undefined;
}

// Helper: Extract strokes from a node
function extractStrokes(node: SceneNode): Paint[] | undefined {
  if (!('strokes' in node) || !node.strokes) return undefined;
  
  var strokes = node.strokes as ReadonlyArray<any>;
  var result: Paint[] = [];
  
  for (var i = 0; i < strokes.length; i++) {
    var stroke = strokes[i];
    if (stroke.visible === false) continue;
    
    var paint: Paint = { type: stroke.type };
    
    if (stroke.type === 'SOLID' && stroke.color) {
      var opacity = stroke.opacity !== undefined ? stroke.opacity : 1;
      paint.color = copyColor(stroke.color, opacity);
    }
    
    result.push(paint);
  }
  
  return result.length > 0 ? result : undefined;
}

// Helper: Extract effects from a node
function extractEffects(node: SceneNode): Effect[] | undefined {
  if (!('effects' in node) || !node.effects) return undefined;
  
  var effects = node.effects;
  var result: Effect[] = [];
  
  for (var i = 0; i < effects.length; i++) {
    var effect = effects[i];
    if (!effect.visible) continue;
    
    var eff: Effect = {
      type: effect.type,
      visible: effect.visible,
    };
    
    if ('radius' in effect) eff.radius = (effect as any).radius;
    if ('color' in effect) eff.color = (effect as any).color;
    if ('offset' in effect) eff.offset = (effect as any).offset;
    if ('spread' in effect) eff.spread = (effect as any).spread;
    
    result.push(eff);
  }
  
  return result.length > 0 ? result : undefined;
}

// Helper: Extract corner radius
function extractCornerRadius(node: SceneNode): CornerRadius | undefined {
  if (!('cornerRadius' in node)) return undefined;
  
  var frameNode = node as FrameNode;
  
  if (frameNode.cornerRadius !== figma.mixed) {
    return { all: frameNode.cornerRadius };
  }
  
  if ('topLeftRadius' in frameNode) {
    return {
      topLeft: frameNode.topLeftRadius,
      topRight: frameNode.topRightRadius,
      bottomRight: frameNode.bottomRightRadius,
      bottomLeft: frameNode.bottomLeftRadius,
    };
  }
  
  return undefined;
}

// Helper: Extract text style
function extractTextStyle(node: TextNode): TextStyle {
  var style: TextStyle = {};
  
  if (node.fontName !== figma.mixed) {
    style.fontFamily = node.fontName.family;
    style.fontWeight = getFontWeight(node.fontName.style);
  }
  
  if (node.fontSize !== figma.mixed) {
    style.fontSize = node.fontSize;
  }
  
  if (node.lineHeight !== figma.mixed && node.lineHeight.unit !== 'AUTO') {
    style.lineHeight = node.lineHeight.unit === 'PERCENT' 
      ? node.lineHeight.value + '%'
      : node.lineHeight.value;
  }
  
  if (node.letterSpacing !== figma.mixed && node.letterSpacing.value !== 0) {
    style.letterSpacing = node.letterSpacing.value;
  }
  
  if (node.textAlignHorizontal) {
    style.textAlign = node.textAlignHorizontal.toLowerCase();
  }
  
  if (node.textDecoration !== 'NONE') {
    style.textDecoration = node.textDecoration.toLowerCase();
  }
  
  return style;
}

// Helper: Convert font style to weight
function getFontWeight(style: string): number {
  var weights: Record<string, number> = {
    'Thin': 100,
    'ExtraLight': 200,
    'Light': 300,
    'Regular': 400,
    'Medium': 500,
    'SemiBold': 600,
    'Bold': 700,
    'ExtraBold': 800,
    'Black': 900,
  };
  
  var keys = Object.keys(weights);
  for (var i = 0; i < keys.length; i++) {
    var name = keys[i];
    if (style.includes(name)) return weights[name];
  }
  
  return 400;
}

// Collect all colors used in the design
var collectedColors: Record<string, ColorInfo> = {};
var collectedFonts: Record<string, Set<number>> = {};
var collectedImageRefs: Set<string> = new Set();

function collectColorsAndFonts(node: SceneNode, context: string): void {
  context = context || 'fill';
  
  // Collect colors from fills
  if ('fills' in node && node.fills && node.fills !== figma.mixed) {
    var fills = node.fills as ReadonlyArray<any>;
    for (var i = 0; i < fills.length; i++) {
      var fill = fills[i];
      if (fill.type === 'SOLID' && fill.color) {
        var hex = rgbToHex(fill.color.r, fill.color.g, fill.color.b);
        if (!collectedColors[hex]) {
          var opacity = fill.opacity !== undefined ? fill.opacity : 1;
          collectedColors[hex] = {
            hex: hex,
            rgba: copyColor(fill.color, opacity),
            usage: [],
          };
        }
        if (collectedColors[hex].usage.indexOf(context) === -1) {
          collectedColors[hex].usage.push(context);
        }
      }
      if (fill.type === 'IMAGE' && fill.imageHash) {
        collectedImageRefs.add(fill.imageHash);
      }
    }
  }
  
  // Collect colors from strokes
  if ('strokes' in node && node.strokes) {
    var strokes = node.strokes as ReadonlyArray<any>;
    for (var j = 0; j < strokes.length; j++) {
      var stroke = strokes[j];
      if (stroke.type === 'SOLID' && stroke.color) {
        var strokeHex = rgbToHex(stroke.color.r, stroke.color.g, stroke.color.b);
        if (!collectedColors[strokeHex]) {
          var strokeOpacity = stroke.opacity !== undefined ? stroke.opacity : 1;
          collectedColors[strokeHex] = {
            hex: strokeHex,
            rgba: copyColor(stroke.color, strokeOpacity),
            usage: [],
          };
        }
        if (collectedColors[strokeHex].usage.indexOf('stroke') === -1) {
          collectedColors[strokeHex].usage.push('stroke');
        }
      }
    }
  }
  
  // Collect fonts from text nodes
  if (node.type === 'TEXT') {
    var textNode = node as TextNode;
    if (textNode.fontName !== figma.mixed) {
      var family = textNode.fontName.family;
      var weight = getFontWeight(textNode.fontName.style);
      if (!collectedFonts[family]) {
        collectedFonts[family] = new Set();
      }
      collectedFonts[family].add(weight);
    }
  }
  
  // Recurse into children
  if ('children' in node) {
    var children = (node as FrameNode).children;
    for (var k = 0; k < children.length; k++) {
      collectColorsAndFonts(children[k], context);
    }
  }
}

// Extract complete node data recursively
function extractNodeData(node: SceneNode): ExtractedNode {
  var data: ExtractedNode = {
    id: node.id,
    name: node.name,
    type: node.type,
    visible: node.visible,
  };
  
  // Add opacity if not default
  if ('opacity' in node && node.opacity !== 1) {
    data.opacity = node.opacity;
  }
  
  // Add bounding box
  if ('absoluteBoundingBox' in node && (node as any).absoluteBoundingBox) {
    var bbox = (node as any).absoluteBoundingBox;
    data.absoluteBoundingBox = {
      x: bbox.x,
      y: bbox.y,
      width: bbox.width,
      height: bbox.height,
    };
  }
  
  // Extract type-specific data
  if (node.type === 'TEXT') {
    var textNode = node as TextNode;
    data.text = textNode.characters;
    data.style = extractTextStyle(textNode);
    data.fills = extractFills(node);
  } else if (['FRAME', 'GROUP', 'COMPONENT', 'INSTANCE', 'SECTION'].indexOf(node.type) !== -1) {
    data.layout = extractLayoutInfo(node);
    data.fills = extractFills(node);
    data.strokes = extractStrokes(node);
    data.effects = extractEffects(node);
    data.cornerRadius = extractCornerRadius(node);
    
    // Recursively process children
    if ('children' in node) {
      var children = (node as FrameNode).children;
      var childNodes: ExtractedNode[] = [];
      for (var i = 0; i < children.length; i++) {
        if (children[i].visible) {
          childNodes.push(extractNodeData(children[i]));
        }
      }
      data.children = childNodes;
    }
  } else if (node.type === 'RECTANGLE') {
    data.layout = extractLayoutInfo(node);
    data.fills = extractFills(node);
    data.strokes = extractStrokes(node);
    data.effects = extractEffects(node);
    data.cornerRadius = extractCornerRadius(node);
  } else if (['VECTOR', 'ELLIPSE', 'LINE', 'POLYGON', 'STAR'].indexOf(node.type) !== -1) {
    data.fills = extractFills(node);
    data.strokes = extractStrokes(node);
    data.layout = extractLayoutInfo(node);
  }
  
  return data;
}

// Export images as base64
async function exportImages(imageRefs: Set<string>): Promise<Record<string, string>> {
  var images: Record<string, string> = {};
  var refs = Array.from(imageRefs);
  
  for (var i = 0; i < refs.length; i++) {
    var imageRef = refs[i];
    try {
      var image = figma.getImageByHash(imageRef);
      if (image) {
        var bytes = await image.getBytesAsync();
        var base64 = figma.base64Encode(bytes);
        images[imageRef] = 'data:image/png;base64,' + base64;
      }
    } catch (e) {
      console.error('Failed to export image ' + imageRef + ':', e);
    }
  }
  
  return images;
}

// Main extraction function
async function extractDesignData(): Promise<DesignData> {
  // Reset collectors (clean reassignment instead of manual delete loop)
  collectedColors = {};
  collectedFonts = {};
  collectedImageRefs = new Set();
  
  var pages: PageData[] = [];
  var frameCount = 0;
  
  // Load all pages first - required by Figma API
  figma.ui.postMessage({ type: 'progress', message: 'Loading all pages...' });
  await figma.loadAllPagesAsync();
  console.log('[Aura Plugin] All pages loaded');
  
  // Extract data from all pages
  var rootChildren = figma.root.children;
  figma.ui.postMessage({ type: 'progress', message: 'Processing ' + rootChildren.length + ' pages...' });
  
  for (var p = 0; p < rootChildren.length; p++) {
    var page = rootChildren[p];
    figma.ui.postMessage({ type: 'progress', message: 'Processing page ' + (p + 1) + '/' + rootChildren.length + ': ' + page.name });
    console.log('[Aura Plugin] Processing page:', page.name);
    
    var pageData: PageData = {
      id: page.id,
      name: page.name,
      frames: [],
    };
    
    var pageChildren = page.children;
    for (var n = 0; n < pageChildren.length; n++) {
      var node = pageChildren[n];
      if (!node.visible) continue;
      
      // Collect colors and fonts
      collectColorsAndFonts(node, 'fill');
      
      // Extract frame data
      var frameData = extractNodeData(node);
      pageData.frames.push(frameData);
      frameCount++;
    }
    
    pages.push(pageData);
  }
  
  // Export images
  figma.ui.postMessage({ type: 'progress', message: 'Exporting images...' });
  var images = await exportImages(collectedImageRefs);
  
  // Convert fonts to array
  var fonts: FontInfo[] = [];
  var fontFamilies = Object.keys(collectedFonts);
  for (var f = 0; f < fontFamilies.length; f++) {
    var family = fontFamilies[f];
    var weights = Array.from(collectedFonts[family]).sort(function(a, b) { return a - b; });
    fonts.push({ family: family, weights: weights });
  }
  
  return {
    fileName: figma.root.name,
    pages: pages,
    colors: collectedColors,
    fonts: fonts,
    images: images,
    stats: {
      pageCount: pages.length,
      frameCount: frameCount,
      colorCount: Object.keys(collectedColors).length,
      fontCount: fonts.length,
      imageCount: Object.keys(images).length,
    },
  };
}

// Fetch available projects from backend
async function fetchProjects(backendUrl: string): Promise<Array<{id: number, name: string, status: string}>> {
  try {
    console.log('[Aura Plugin] Fetching available projects from:', backendUrl + '/api/projects/available');
    var response = await fetch(backendUrl + '/api/projects/available', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      console.error('[Aura Plugin] Failed to fetch projects:', response.status);
      return [];
    }
    
    var data = await response.json();
    console.log('[Aura Plugin] Fetched projects:', data.projects.length);
    return data.projects || [];
  } catch (err) {
    console.error('[Aura Plugin] Error fetching projects:', err);
    return [];
  }
}

// Capture screenshot of the first frame for visual verification (primary reference)
async function captureDesignScreenshot(): Promise<string | null> {
  try {
    var currentPage = figma.currentPage;
    var firstFrame: FrameNode | null = null;

    for (var i = 0; i < currentPage.children.length; i++) {
      var child = currentPage.children[i];
      if (child.type === 'FRAME') {
        firstFrame = child as FrameNode;
        break;
      }
    }

    if (!firstFrame) {
      console.log('[Aura Plugin] No frame found for screenshot');
      return null;
    }

    console.log('[Aura Plugin] Capturing screenshot of frame:', firstFrame.name);

    var imageBytes = await firstFrame.exportAsync({
      format: 'PNG',
      constraint: { type: 'SCALE', value: 2 }
    });

    var base64 = figma.base64Encode(imageBytes);
    console.log('[Aura Plugin] Screenshot captured, size:', base64.length, 'chars');
    return base64;
  } catch (err) {
    console.error('[Aura Plugin] Error capturing screenshot:', err);
    return null;
  }
}

// Capture screenshots of ALL top-level frames for multi-page designs
async function captureAllFrameScreenshots(): Promise<Record<string, string>> {
  var screenshots: Record<string, string> = {};
  try {
    var currentPage = figma.currentPage;
    var frameCount = 0;

    for (var i = 0; i < currentPage.children.length; i++) {
      var child = currentPage.children[i];
      if (child.type === 'FRAME') {
        frameCount++;
        // Limit to 5 frames to avoid huge payloads
        if (frameCount > 5) {
          console.log('[Aura Plugin] Limiting screenshots to 5 frames');
          break;
        }
        try {
          var frame = child as FrameNode;
          console.log('[Aura Plugin] Capturing frame:', frame.name);
          var bytes = await frame.exportAsync({
            format: 'PNG',
            constraint: { type: 'SCALE', value: 1 }
          });
          screenshots[frame.name] = figma.base64Encode(bytes);
        } catch (frameErr) {
          console.error('[Aura Plugin] Error capturing frame', child.name, frameErr);
        }
      }
    }
    console.log('[Aura Plugin] Captured', Object.keys(screenshots).length, 'frame screenshots');
  } catch (err) {
    console.error('[Aura Plugin] Error capturing all screenshots:', err);
  }
  return screenshots;
}

// Send data to backend
async function sendToBackend(
  backendUrl: string,
  projectName: string,
  uiLibrary: string,
  addAs: string,
  parentProjectId: number | null
): Promise<void> {
  console.log('[Aura Plugin] sendToBackend called');

  try {
    figma.ui.postMessage({ type: 'progress', message: 'Extracting design data...' });
    console.log('[Aura Plugin] Extracting design data...');

    var designData = await extractDesignData();
    console.log('[Aura Plugin] Design data extracted:', designData.stats);

    // Capture screenshots for visual verification
    figma.ui.postMessage({ type: 'progress', message: 'Capturing design screenshots...' });
    var screenshot = await captureDesignScreenshot();
    if (screenshot) {
      (designData as any).designScreenshot = screenshot;
      console.log('[Aura Plugin] Primary screenshot added');
    }
    // Also capture all frames (1x scale, for multi-frame designs)
    var allScreenshots = await captureAllFrameScreenshots();
    if (Object.keys(allScreenshots).length > 0) {
      (designData as any).designScreenshots = allScreenshots;
      console.log('[Aura Plugin] All frame screenshots added:', Object.keys(allScreenshots).length);
    }
    
    figma.ui.postMessage({ 
      type: 'progress', 
      message: 'Extracted ' + designData.stats.frameCount + ' frames, ' + 
               designData.stats.colorCount + ' colors, ' + 
               designData.stats.fontCount + ' fonts, ' + 
               designData.stats.imageCount + ' images' 
    });
    
    figma.ui.postMessage({ type: 'progress', message: 'Sending to backend...' });
    console.log('[Aura Plugin] Sending to:', backendUrl + '/api/figma/plugin-upload');
    
    // Prepare request body
    var requestBody: any = {
      project_name: projectName,
      ui_library: uiLibrary,
      design_data: designData,
      add_as: addAs,
    };
    
    // Add parent_project_id if adding to existing project
    if (addAs === 'new_page' && parentProjectId !== null) {
      requestBody.parent_project_id = parentProjectId;
    }
    
    // Send to backend
    var response = await fetch(backendUrl + '/api/figma/plugin-upload', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });
    
    console.log('[Aura Plugin] Response status:', response.status);
    
    if (!response.ok) {
      var errorText = await response.text();
      console.error('[Aura Plugin] Backend error:', errorText);
      throw new Error('Backend error: ' + response.status + ' - ' + errorText);
    }
    
    var result = await response.json();
    console.log('[Aura Plugin] Success! Result:', result);
    figma.ui.postMessage({ type: 'success', result: result });
    
  } catch (err) {
    console.error('[Aura Plugin] Error in sendToBackend:', err);
    throw err;
  }
}

// Guard against double-submission
var isExporting = false;

// Handle messages from UI
figma.ui.onmessage = function(msg) {
  console.log('[Aura Plugin] Received message:', msg.type);

  if (msg.type === 'fetch-projects') {
    // Fetch available projects for dropdown
    fetchProjects(msg.backendUrl)
      .then(function(projects) {
        figma.ui.postMessage({ 
          type: 'projects-list', 
          projects: projects 
        });
      })
      .catch(function(error) {
        console.error('[Aura Plugin] Error fetching projects:', error);
        figma.ui.postMessage({ 
          type: 'projects-list', 
          projects: [] 
        });
      });
  } else if (msg.type === 'export') {
    // Prevent double-submission
    if (isExporting) {
      figma.ui.postMessage({ type: 'error', message: 'Export already in progress' });
      return;
    }
    isExporting = true;

    // Immediately acknowledge receipt
    figma.ui.postMessage({
      type: 'progress',
      message: 'Plugin received export request...'
    });

    console.log('[Aura Plugin] Starting export...');

    // Use Promise-based approach for better compatibility
    var addAs = msg.addAs || 'new_project';
    var parentProjectId = msg.parentProjectId || null;

    sendToBackend(msg.backendUrl, msg.projectName, msg.uiLibrary, addAs, parentProjectId)
      .then(function() {
        console.log('[Aura Plugin] Export completed successfully');
      })
      .catch(function(error) {
        console.error('[Aura Plugin] Export failed:', error);
        var errorMessage = 'Unknown error';
        if (error instanceof Error) {
          errorMessage = error.message;
        } else if (typeof error === 'string') {
          errorMessage = error;
        }
        figma.ui.postMessage({
          type: 'error',
          message: errorMessage
        });
      })
      .finally(function() {
        isExporting = false;
      });
  } else if (msg.type === 'cancel') {
    figma.closePlugin();
  }
};
