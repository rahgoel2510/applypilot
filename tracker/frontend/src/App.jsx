import { lazy, Suspense, useContext } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import AppLayout from './layout/AppLayout';
import { ThemeContext } from './main';

// Lazy-loaded page components
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AgentControl = lazy(() => import('./pages/AgentControl'));
const Board = lazy(() => import('./pages/Board'));
const Scheduler = lazy(() => import('./pages/Scheduler'));
const Agents = lazy(() => import('./pages/Agents'));
const Settings = lazy(() => import('./pages/Settings'));
const ServiceManager = lazy(() => import('./pages/ServiceManager'));

function PageTransition({ children }) {
  return (
    <Box
      sx={{
        animation: 'fadeSlideIn 0.2s ease-out',
        '@keyframes fadeSlideIn': {
          from: { opacity: 0, transform: 'translateY(4px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
        height: '100%',
        overflow: 'auto',
      }}
    >
      {children}
    </Box>
  );
}

function MinimalFallback() {
  return <Box sx={{ minHeight: '100%' }} />;
}

export default function App() {
  const { mode, toggleMode } = useContext(ThemeContext);

  return (
    <Routes>
      <Route element={<AppLayout mode={mode} toggleMode={toggleMode} />}>
        <Route path="/" element={<Suspense fallback={<MinimalFallback />}><PageTransition><Dashboard /></PageTransition></Suspense>} />
        <Route path="/agent" element={<Suspense fallback={<MinimalFallback />}><PageTransition><AgentControl /></PageTransition></Suspense>} />
        <Route path="/board" element={<Suspense fallback={<MinimalFallback />}><PageTransition><Board /></PageTransition></Suspense>} />
        <Route path="/scheduler" element={<Suspense fallback={<MinimalFallback />}><PageTransition><Scheduler /></PageTransition></Suspense>} />
        <Route path="/agents" element={<Suspense fallback={<MinimalFallback />}><PageTransition><Agents /></PageTransition></Suspense>} />
        <Route path="/settings" element={<Suspense fallback={<MinimalFallback />}><PageTransition><Settings /></PageTransition></Suspense>} />
        <Route path="/service" element={<Suspense fallback={<MinimalFallback />}><PageTransition><ServiceManager /></PageTransition></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
