import React from 'react';

const Footer: React.FC = () => {
  return (
    <footer
      data-figma-id="frame:footer"
      className="w-full bg-[#111827] px-16 py-8"
    >
      <div className="max-w-[1440px] mx-auto flex items-center justify-between">
        {/* Copyright — Figma: Inter 400, 14px, #9BA3B0 */}
        <span className="text-sm text-[#9BA3B0]">
          2026 Acme Inc. All rights reserved.
        </span>

        {/* Footer Links — Figma: Inter 400, 14px, #9BA3B0, spacing 24px */}
        <div className="flex items-center space-x-6">
          <a href="/privacy" className="text-sm text-[#9BA3B0] hover:text-white transition-colors">
            Privacy Policy
          </a>
          <a href="/terms" className="text-sm text-[#9BA3B0] hover:text-white transition-colors">
            Terms of Service
          </a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
