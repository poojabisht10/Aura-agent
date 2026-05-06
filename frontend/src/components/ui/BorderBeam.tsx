// React import not needed
import { motion } from 'framer-motion';

export function BorderBeam() {
  return (
    <div className="border-beam-container">
      <motion.div
        className="border-beam-effect"
        animate={{
          x: ['-100%', '100%'],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: 'linear',
        }}
      />
    </div>
  );
}
