// Page 2: Contact Page
// Status: Reused from library (similarity: 0.92)
//
// The Figma design for Page 2 has a nearly identical header.
// Differences detected: nav links text changed ("Home" -> "Back to Home").
// Decision: Reuse Page 1 Header with minor text adaptation.

import React from 'react';

const Header: React.FC = () => {
  return (
    <header className="w-full bg-white shadow-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-8 py-4 flex items-center justify-between">
        <span className="text-2xl font-bold text-[#1E40AF]">Acme</span>
        <nav className="flex items-center space-x-8">
          <a href="/" className="text-base font-medium text-gray-700">Back to Home</a>
          <a href="/about" className="text-base font-medium text-gray-700">About</a>
          <a href="/contact" className="text-base font-medium text-[#1E40AF]">Contact</a>
        </nav>
        <button className="bg-[#1E40AF] text-white text-sm font-semibold px-6 py-2.5 rounded-lg">
          Get Started
        </button>
      </div>
    </header>
  );
};

export default Header;
