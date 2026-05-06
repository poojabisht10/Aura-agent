import React from 'react';

const Header: React.FC = () => {
  return (
    <header
      data-figma-id="frame:header"
      className="w-full bg-white shadow-sm sticky top-0 z-50"
    >
      <div className="max-w-[1440px] mx-auto px-16 py-4 flex items-center justify-between">
        {/* Logo — Figma: Inter 700, 24px, #1E40AF */}
        <span className="text-2xl font-bold tracking-tight text-[#1E40AF]">
          Acme
        </span>

        {/* Navigation Links — Figma: Inter 500, 16px, #3D4251, spacing 32px */}
        <nav className="hidden md:flex items-center space-x-8">
          <a href="#features" className="text-[16px] font-medium text-[#3D4251] hover:text-[#1E40AF] transition-colors">
            Features
          </a>
          <a href="#pricing" className="text-[16px] font-medium text-[#3D4251] hover:text-[#1E40AF] transition-colors">
            Pricing
          </a>
          <a href="#about" className="text-[16px] font-medium text-[#3D4251] hover:text-[#1E40AF] transition-colors">
            About
          </a>
        </nav>

        {/* CTA Button — Figma: bg #1E40AF, rounded-lg, px-6 py-2.5, Inter 600 14px white */}
        <button className="bg-[#1E40AF] text-white text-sm font-semibold px-6 py-2.5 rounded-lg hover:bg-[#1E3A8A] transition-colors">
          Get Started
        </button>
      </div>
    </header>
  );
};

export default Header;
