import React from 'react';

const Hero: React.FC = () => {
  return (
    <section
      data-figma-id="frame:hero"
      className="w-full bg-[#F3F4F6] py-24 px-16 flex flex-col items-center text-center"
    >
      {/* Heading — Figma: Inter 800, 56px, line-height 64px, tracking -1.5px, #111827 */}
      <h1 className="text-[56px] font-extrabold leading-[64px] tracking-[-1.5px] text-[#111827]">
        Build Beautiful Interfaces
      </h1>

      {/* Subtitle — Figma: Inter 400, 20px, line-height 32px, #5F697A, max-width 640px */}
      <p className="mt-6 text-[20px] leading-8 text-[#5F697A] max-w-[640px]">
        Transform your Figma designs into production-ready React code with pixel-perfect accuracy.
      </p>

      {/* Hero Image — Figma: 800x400, rounded-xl, shadow-lg */}
      <div className="mt-10 w-full max-w-[800px]">
        <img
          src="/images/hero-dashboard-preview.png"
          alt="Dashboard preview"
          className="w-full h-auto rounded-xl shadow-[0_8px_24px_rgba(0,0,0,0.1)]"
        />
      </div>
    </section>
  );
};

export default Hero;
