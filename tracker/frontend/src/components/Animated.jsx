import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Fade-in from bottom (for cards appearing)
export const FadeInUp = ({ children, delay = 0, ...props }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.3, delay, ease: 'easeOut' }}
    {...props}
  >
    {children}
  </motion.div>
);

// Staggered list items
export const StaggerContainer = ({ children, staggerDelay = 0.08 }) => (
  <motion.div
    initial="hidden"
    animate="visible"
    variants={{
      visible: { transition: { staggerChildren: staggerDelay } },
      hidden: {},
    }}
  >
    {children}
  </motion.div>
);

export const StaggerItem = ({ children }) => (
  <motion.div
    variants={{
      hidden: { opacity: 0, y: 12 },
      visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
    }}
  >
    {children}
  </motion.div>
);

// Scale on hover (for cards)
export const HoverScale = ({ children, scale = 1.02 }) => (
  <motion.div whileHover={{ scale }} whileTap={{ scale: 0.98 }} transition={{ duration: 0.15 }}>
    {children}
  </motion.div>
);

// Number counter animation
export const AnimatedNumber = ({ value, duration = 1 }) => {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    const start = display;
    const end = value;
    const startTime = Date.now();
    const dur = duration * 1000;
    const animate = () => {
      const elapsed = Date.now() - startTime;
      if (elapsed >= dur) { setDisplay(end); return; }
      const progress = elapsed / dur;
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(start + (end - start) * eased));
      requestAnimationFrame(animate);
    };
    animate();
  }, [value]);
  return <span>{display}</span>;
};

// Pulse animation (for status dots)
export const PulseBox = ({ children, color = '#067D68' }) => (
  <motion.div
    animate={{ boxShadow: [`0 0 0 0px ${color}40`, `0 0 0 8px ${color}00`] }}
    transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
    style={{ display: 'inline-flex', borderRadius: '50%' }}
  >
    {children}
  </motion.div>
);
