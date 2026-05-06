// Page 1: Homepage
// Status: Created new -- Saved to component library

import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  onClick?: () => void;
}

const Button: React.FC<ButtonProps> = ({ children, variant = 'primary', onClick }) => {
  const styles = variant === 'primary'
    ? 'bg-[#1E40AF] text-white hover:bg-[#1E3A8A]'
    : 'bg-white text-[#1E40AF] border border-[#1E40AF] hover:bg-[#F3F4F6]';

  return (
    <button
      onClick={onClick}
      className={`${styles} text-sm font-semibold px-6 py-2.5 rounded-lg transition-colors`}
    >
      {children}
    </button>
  );
};

export default Button;
