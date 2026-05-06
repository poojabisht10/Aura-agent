// React import not needed
import { motion } from 'framer-motion';
import { CheckCircle2, Loader2, AlertCircle, Clock } from 'lucide-react';

interface StatusBadgeProps {
  status: 'completed' | 'processing' | 'failed' | 'pending';
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const statusConfig = {
    'completed': { icon: CheckCircle2, color: 'success', label: 'Completed' },
    'processing': { icon: Loader2, color: 'info', label: 'Processing' },
    'failed': { icon: AlertCircle, color: 'error', label: 'Failed' },
    'pending': { icon: Clock, color: 'warning', label: 'Pending' },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <motion.div
      className={`status-badge status-${config.color}`}
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Icon
        className={`status-icon ${status === 'processing' ? 'icon-spinning' : ''}`}
        size={14}
      />
      <span className="status-label">{config.label}</span>
    </motion.div>
  );
}
