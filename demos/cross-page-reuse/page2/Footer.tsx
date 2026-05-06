// Page 2: Contact Page
// Status: Reused from library (similarity: 0.88)
//
// The Figma design for Page 2 has a similar footer with one extra link.
// Differences detected: additional "Careers" link.
// Decision: Reuse Page 1 Footer with the extra link added.

import React from 'react';

const Footer: React.FC = () => {
  return (
    <footer className="w-full bg-[#111827] px-8 py-8">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <span className="text-sm text-[#9BA3B0]">
          2026 Acme Inc. All rights reserved.
        </span>
        <div className="flex items-center space-x-6">
          <a href="/privacy" className="text-sm text-[#9BA3B0] hover:text-white">Privacy</a>
          <a href="/terms" className="text-sm text-[#9BA3B0] hover:text-white">Terms</a>
          <a href="/careers" className="text-sm text-[#9BA3B0] hover:text-white">Careers</a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
