import React from 'react';
import { motion } from 'framer-motion';

interface ShimmerButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary';
  className?: string;
}

export function ShimmerButton({
  children,
  onClick,
  variant = 'primary',
  className = ''
}: ShimmerButtonProps) {
  return (
    <motion.button
      onClick={onClick}
      className={`shimmer-button shimmer-button-${variant} ${className}`}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      <span className="shimmer-button-text">{children}</span>
      <div className="shimmer-animation" />
    </motion.button>
  );
}
